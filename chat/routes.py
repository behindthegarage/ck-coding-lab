"""
chat/routes.py - Chat/AI endpoints
Club Kinawa Coding Lab

Provides endpoints for:
- Chat/AI code generation with tool use
"""

import difflib

from flask import request, jsonify, g

from database import get_db
from auth import require_auth
from ai import get_ai_client
from chat import chat_bp
from chat.rate_limit import check_chat_rate_limit
from projects.state import is_code_file, persist_generated_code, sync_current_code_cache

WRITE_TOOL_NAMES = {'write_file', 'append_file'}
MAX_REVIEW_FILES = 3
MAX_REVIEW_DIFF_LINES = 18
MAX_REVIEW_CHARS = 1800


def _collect_changed_file_entries(tool_calls, created_files):
    """Combine file changes from tool execution and parsed filename blocks."""
    changed = {}

    for file_info in created_files or []:
        filename = (file_info or {}).get('filename')
        if not filename:
            continue
        changed[filename] = {
            'filename': filename,
            'action': file_info.get('action', 'updated'),
            'before_content': file_info.get('before_content'),
            'after_content': file_info.get('after_content')
        }

    for tool_call in tool_calls or []:
        tool_name = tool_call.get('tool') or tool_call.get('name')
        tool_input = tool_call.get('input') or {}
        tool_result = tool_call.get('result') or {}
        filename = tool_input.get('filename')
        if tool_name not in WRITE_TOOL_NAMES or not filename or tool_result.get('success') is False:
            continue
        entry = changed.setdefault(filename, {'filename': filename})
        entry['action'] = tool_result.get('action', entry.get('action', 'updated'))

    return list(changed.values())


def _hydrate_changed_file_contents(project_id, changed_files):
    """Fill in post-change file contents from the database when available."""
    filenames = [file_info.get('filename') for file_info in changed_files if file_info.get('filename')]
    if not filenames:
        return changed_files

    placeholders = ','.join('?' for _ in filenames)
    with get_db() as db:
        db.execute(
            f'''
                SELECT filename, content FROM project_files
                WHERE project_id = ? AND filename IN ({placeholders})
            ''',
            (project_id, *filenames)
        )
        file_contents = {row['filename']: row['content'] for row in db.fetchall()}

    hydrated = []
    for file_info in changed_files:
        filename = file_info.get('filename')
        entry = dict(file_info)
        if entry.get('after_content') is None and filename in file_contents:
            entry['after_content'] = file_contents[filename]
        hydrated.append(entry)

    return hydrated


def _trim_review_text(text):
    trimmed = (text or '').strip('\n')
    if len(trimmed) <= MAX_REVIEW_CHARS:
        return trimmed, False
    return trimmed[:MAX_REVIEW_CHARS].rstrip() + '\n…', True


def _format_line_count(count):
    return f'{count} line' if count == 1 else f'{count} lines'


def _build_diff_excerpt(before_content, after_content, action):
    before_lines = (before_content or '').splitlines()
    after_lines = (after_content or '').splitlines()
    normalized_action = (action or 'updated').lower()

    if normalized_action == 'created':
        diff_lines = [f'+ {line}' for line in after_lines[:MAX_REVIEW_DIFF_LINES]] or ['+ (empty file)']
        truncated = len(after_lines) > MAX_REVIEW_DIFF_LINES
        return '\n'.join(diff_lines + (['…'] if truncated else [])), truncated

    if not before_lines and after_lines:
        snapshot_lines = [f'  {line}' for line in after_lines[:MAX_REVIEW_DIFF_LINES]]
        truncated = len(after_lines) > MAX_REVIEW_DIFF_LINES
        return '\n'.join(snapshot_lines + (['…'] if truncated else [])), truncated

    diff_lines = list(difflib.unified_diff(before_lines, after_lines, fromfile='before', tofile='after', n=1, lineterm=''))
    filtered_lines = [line for line in diff_lines if not line.startswith('---') and not line.startswith('+++')]

    if not filtered_lines:
        fallback = '  File was rewritten, but the line diff is empty.'
        return fallback, False

    truncated = len(filtered_lines) > MAX_REVIEW_DIFF_LINES
    excerpt = filtered_lines[:MAX_REVIEW_DIFF_LINES]
    if truncated:
        excerpt.append('…')

    return '\n'.join(excerpt), truncated


def _build_review_summary(before_content, after_content, action):
    normalized_action = (action or 'updated').lower()
    before_lines = (before_content or '').splitlines()
    after_lines = (after_content or '').splitlines()

    if normalized_action == 'created':
        return f'New file • {_format_line_count(len(after_lines))}'

    diff_lines = list(difflib.unified_diff(before_lines, after_lines, fromfile='before', tofile='after', n=1, lineterm=''))
    added = sum(1 for line in diff_lines if line.startswith('+') and not line.startswith('+++'))
    removed = sum(1 for line in diff_lines if line.startswith('-') and not line.startswith('---'))

    if normalized_action == 'appended':
        return f'Appended • {added} added'

    if added or removed:
        parts = []
        if added:
            parts.append(f'{added} added')
        if removed:
            parts.append(f'{removed} removed')
        return ' • '.join(parts)

    return f'Updated • {_format_line_count(len(after_lines))}'


def _build_change_review(changed_files):
    """Build a lightweight diff-ish review surface for the latest AI edits."""
    review_entries = []

    for file_info in changed_files[:MAX_REVIEW_FILES]:
        filename = file_info.get('filename')
        after_content = file_info.get('after_content')
        if not filename or after_content is None:
            continue

        action = file_info.get('action', 'updated')
        before_content = file_info.get('before_content') or ''
        diff_excerpt, diff_truncated = _build_diff_excerpt(before_content, after_content, action)
        diff_excerpt, char_truncated = _trim_review_text(diff_excerpt)

        review_entries.append({
            'filename': filename,
            'action': action,
            'summary': _build_review_summary(before_content, after_content, action),
            'diff_excerpt': diff_excerpt,
            'truncated': bool(diff_truncated or char_truncated)
        })

    return review_entries


def _normalize_changed_files(changed_entries):
    return [
        {
            'filename': file_info.get('filename'),
            'action': file_info.get('action', 'updated')
        }
        for file_info in changed_entries
        if file_info.get('filename')
    ]


def _build_assistant_message(explanation, changed_files, primary_file, suggestions, tool_calls, change_review):
    """Create a consistent markdown transcript for assistant messages."""
    lines = []
    summary = (explanation or '').strip() or 'I updated the project.'
    lines.append(summary)

    if changed_files:
        lines.extend(['', '## What changed'])
        for file_info in changed_files:
            action = (file_info.get('action') or 'updated').capitalize()
            filename = file_info.get('filename', 'unknown file')
            lines.append(f"- {action} `{filename}`")

    if change_review:
        lines.extend(['', '## Review'])
        for review in change_review:
            lines.append(f"### `{review['filename']}`")
            lines.append(f"- Action: {(review.get('action') or 'updated').capitalize()}")
            lines.append(f"- Summary: {review.get('summary', 'Updated file')}")
            if review.get('truncated'):
                lines.append('- Note: Preview trimmed for readability.')
            lines.extend([
                '```diff',
                review.get('diff_excerpt', '').rstrip() or '  No preview available.',
                '```'
            ])

    if primary_file and (len(changed_files) > 1 or not changed_files or changed_files[0].get('filename') != primary_file):
        lines.extend(['', '## Start here', f"- Entry file: `{primary_file}`"])

    if tool_calls:
        lines.extend(['', '## Tools used'])
        for tool_call in tool_calls:
            tool_name = tool_call.get('tool') or tool_call.get('name') or 'tool'
            tool_input = tool_call.get('input') or {}
            tool_result = tool_call.get('result') or {}
            filename = tool_input.get('filename')
            action = tool_result.get('action')
            if filename and action:
                lines.append(f"- `{tool_name}` on `{filename}` → {action}")
            elif filename:
                lines.append(f"- `{tool_name}` on `{filename}`")
            else:
                lines.append(f"- `{tool_name}`")

    if suggestions:
        lines.extend(['', '## Next ideas'])
        for suggestion in suggestions[:5]:
            if suggestion and suggestion.strip():
                lines.append(f"- {suggestion.strip()}")

    return '\n'.join(lines).strip()


@chat_bp.route('/projects/<int:project_id>/chat', methods=['POST'])
@require_auth
def chat_with_ai(project_id):
    """
    Send a message to AI and get code response.
    Stores conversation history and tracks tool calls.
    """
    user_id = g.current_user['id']

    # Check rate limit
    allowed, remaining, reset_after = check_chat_rate_limit(user_id)
    if not allowed:
        return jsonify({
            'success': False,
            'error': f'Rate limit exceeded. Try again in {reset_after} seconds.'
        }), 429

    data = request.get_json()

    if not data or 'message' not in data:
        return jsonify({'success': False, 'error': 'Message is required'}), 400

    message = data['message'].strip()
    model = data.get('model', 'kimi-k2.5')
    enable_tools = data.get('enable_tools', True)

    if len(message) > 2000:
        return jsonify({'success': False, 'error': 'Message too long (max 2000 chars)'}), 400

    with get_db() as db:
        # Verify ownership and derive current code from authoritative project files
        db.execute('''
            SELECT id, current_code, language FROM projects WHERE id = ? AND user_id = ?
        ''', (project_id, user_id))

        result = db.fetchone()
        if not result:
            return jsonify({'success': False, 'error': 'Project not found'}), 404

        language = result['language'] or 'undecided'
        project_state = sync_current_code_cache(
            db,
            project_id,
            language,
            fallback_current_code=result['current_code'] or '',
            touch_project=False
        )
        current_code = project_state['current_code']

        # Get conversation history for context
        db.execute('''
            SELECT role, content FROM conversations
            WHERE project_id = ?
            ORDER BY created_at ASC
            LIMIT 20
        ''', (project_id,))

        conversation_history = [
            {'role': row['role'], 'content': row['content']}
            for row in db.fetchall()
        ]

    # Save user message
    with get_db() as db:
        db.execute('''
            INSERT INTO conversations (project_id, role, content)
            VALUES (?, ?, ?)
        ''', (project_id, 'user', message))

    # Call AI with the project's language and tool support
    ai = get_ai_client()
    result = ai.generate_code(
        message=message,
        conversation_history=conversation_history,
        current_code=current_code,
        language=language,
        model=model,
        project_id=project_id,
        enable_tools=enable_tools
    )

    if not result['success']:
        return jsonify({
            'success': False,
            'error': result.get('error', 'AI generation failed')
        }), 500

    tool_calls = result.get('tool_calls', []) or []
    changed_file_entries = _hydrate_changed_file_contents(
        project_id,
        _collect_changed_file_entries(tool_calls, result.get('created_files', []))
    )
    changed_files = _normalize_changed_files(changed_file_entries)
    change_review = _build_change_review(changed_file_entries)
    write_tools_used = any(
        (tool_call.get('tool') or tool_call.get('name')) in WRITE_TOOL_NAMES
        and (tool_call.get('result') or {}).get('success') is not False
        for tool_call in tool_calls
    )

    # Save AI response and keep projects.current_code derived from project_files
    with get_db() as db:
        code_files_touched = any(is_code_file((file_info or {}).get('filename', '')) for file_info in changed_files)

        # For simple single-file responses without explicit file writes, persist the
        # generated code into project_files so files remain the source of truth.
        if result['code'] and not code_files_touched and not write_tools_used:
            persist_generated_code(db, project_id, language, result['code'])
            code_files_touched = True

        project_state = sync_current_code_cache(
            db,
            project_id,
            language,
            fallback_current_code=current_code,
            touch_project=bool(result['code'] or tool_calls or changed_files)
        )

        assistant_content = _build_assistant_message(
            result.get('explanation', ''),
            changed_files,
            project_state.get('primary_file'),
            result.get('suggestions', []),
            tool_calls,
            change_review
        )

        db.execute('''
            INSERT INTO conversations (project_id, role, content, model, tokens_used)
            VALUES (?, ?, ?, ?, ?)
        ''', (
            project_id,
            'assistant',
            assistant_content,
            model,
            result['tokens_used']
        ))

    response_code = result['code']
    if result['code'] or code_files_touched:
        response_code = project_state['current_code']

    return jsonify({
        'success': True,
        'response': {
            'explanation': result['explanation'],
            'code': response_code,
            'suggestions': result['suggestions'],
            'model': result['model'],
            'tokens_used': result['tokens_used'],
            'tool_calls': tool_calls,
            'created_files': changed_files,
            'changed_files': changed_files,
            'change_review': change_review,
            'primary_file': project_state.get('primary_file')
        }
    })
