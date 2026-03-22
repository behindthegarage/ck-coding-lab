"""
chat/routes.py - Chat/AI endpoints
Club Kinawa Coding Lab

Provides endpoints for:
- Chat/AI code generation with tool use
"""

import difflib
import posixpath
import re

from flask import request, jsonify, g

from database import get_db
from auth import require_auth
from ai import get_ai_client
from ai.parser import compact_assistant_transcript, sanitize_response_text
from ai.workflow import analyze_workflow_context
from chat import chat_bp
from chat.rate_limit import check_chat_rate_limit
from projects.access import can_access_project_owner
from projects.recovery import create_recovery_version, create_recovery_version_from_state
from projects.state import is_code_file, persist_generated_code, sync_current_code_cache

WRITE_TOOL_NAMES = {'write_file', 'append_file'}
DOC_FILENAMES = {'design.md', 'architecture.md', 'todo.md', 'notes.md'}
DOC_UPDATE_PREFIXES = {
    'design.md': 'Captured the latest project direction:',
    'architecture.md': 'Recorded the current build structure:',
    'todo.md': 'Reset the working checklist around:',
    'notes.md': 'Logged the latest session decisions about:',
}
MAX_REVIEW_FILES = 3
MAX_REVIEW_DIFF_LINES = 18
MAX_REVIEW_CHARS = 1800
MAX_DOC_HIGHLIGHTS = 3
GENERIC_DOC_LINE_PATTERN = re.compile(
    r'^(?:feature\s+\d+|stretch feature\s+\d+|initial setup|define core features|add your own twist)$',
    re.IGNORECASE,
)


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


def _is_doc_file(filename):
    return posixpath.basename(filename or '').lower() in DOC_FILENAMES


def _normalize_doc_highlight(line):
    cleaned = (line or '').strip()
    cleaned = re.sub(r'^#+\s*', '', cleaned)
    cleaned = re.sub(r'^[-*•]\s*', '', cleaned)
    cleaned = re.sub(r'^\d+\.\s*', '', cleaned)
    cleaned = re.sub(r'^\[\s?[xX]?\]\s*', '', cleaned)
    cleaned = cleaned.strip('` ').strip()
    cleaned = re.sub(r'\s+', ' ', cleaned)
    return cleaned


def _should_skip_doc_highlight(line):
    normalized = _normalize_doc_highlight(line)
    lowered = normalized.lower()
    if not normalized:
        return True
    if lowered in {
        'idea',
        'starter path',
        'core features',
        'stretch goals',
        'open questions',
        'technology stack',
        'file structure',
        'key components',
        'notes',
        'first moves',
        'current',
        'completed',
        'ideas',
        'session log',
        'questions to ask',
        'decisions made',
        '_none yet_',
    }:
        return True
    return bool(GENERIC_DOC_LINE_PATTERN.match(lowered))


def _extract_doc_highlights(before_content, after_content, action):
    if (action or '').lower() == 'created' or not (before_content or '').strip():
        candidate_lines = (after_content or '').splitlines()
    else:
        diff_lines = list(
            difflib.unified_diff(
                (before_content or '').splitlines(),
                (after_content or '').splitlines(),
                fromfile='before',
                tofile='after',
                n=0,
                lineterm=''
            )
        )
        candidate_lines = [line[1:] for line in diff_lines if line.startswith('+') and not line.startswith('+++')]

    highlights = []
    seen = set()
    for line in candidate_lines:
        normalized = _normalize_doc_highlight(line)
        if _should_skip_doc_highlight(normalized):
            continue
        key = normalized.lower()
        if key in seen:
            continue
        seen.add(key)
        highlights.append(normalized.rstrip('.'))
        if len(highlights) >= MAX_DOC_HIGHLIGHTS:
            break

    return highlights


def _build_doc_update_text(filename, before_content, after_content, action):
    basename = posixpath.basename(filename or '').lower()
    prefix = DOC_UPDATE_PREFIXES.get(basename, 'Updated the project notes around:')
    highlights = _extract_doc_highlights(before_content, after_content, action)

    if highlights:
        return f"{prefix} {'; '.join(highlights)}."

    fallback = {
        'design.md': 'Updated the project direction and feature plan.',
        'architecture.md': 'Updated the technical plan and file structure.',
        'todo.md': 'Updated the next tasks and progress checklist.',
        'notes.md': 'Updated the running session notes.',
    }
    return fallback.get(basename, 'Updated the project notes.')


def _build_doc_updates(changed_entries):
    doc_updates = []
    for file_info in changed_entries:
        filename = file_info.get('filename')
        if not _is_doc_file(filename):
            continue
        doc_updates.append({
            'filename': filename,
            'action': file_info.get('action', 'updated'),
            'summary': _build_doc_update_text(
                filename,
                file_info.get('before_content') or '',
                file_info.get('after_content') or '',
                file_info.get('action', 'updated')
            )
        })
    return doc_updates


def _append_section(lines, title, items):
    cleaned_items = [item.strip() for item in (items or []) if item and item.strip()]
    if not cleaned_items:
        return

    lines.extend(['', title])
    for item in cleaned_items[:5]:
        lines.append(f"- {item}")


def _build_assistant_message(
    explanation,
    changed_files,
    primary_file,
    suggestions,
    tool_calls,
    change_review,
    doc_updates=None,
    decision_notes=None,
    assumptions=None,
    follow_up_questions=None,
):
    """Create a consistent markdown transcript for assistant messages."""
    lines = []
    summary = sanitize_response_text(explanation).strip() or 'I updated the project.'
    lines.append(summary)

    _append_section(lines, '## Why this approach', decision_notes)
    _append_section(lines, '## Assumptions', assumptions)

    if doc_updates:
        lines.extend(['', '## Doc updates'])
        for update in doc_updates[:4]:
            filename = update.get('filename', 'doc.md')
            summary_text = (update.get('summary') or 'Updated this planning doc.').strip()
            lines.append(f"- `{filename}` — {summary_text}")

    visible_changed_files = [
        file_info for file_info in (changed_files or [])
        if file_info.get('filename') and (not doc_updates or not _is_doc_file(file_info.get('filename')))
    ]

    if visible_changed_files:
        lines.extend(['', '## What changed'])
        for file_info in visible_changed_files:
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

    _append_section(lines, '## Questions for you', follow_up_questions)

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
        # Verify access and derive current code from authoritative project files
        db.execute('''
            SELECT id, user_id, current_code, language FROM projects WHERE id = ?
        ''', (project_id,))

        result = db.fetchone()
        if not result or not can_access_project_owner(g.current_user, result['user_id']):
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

    model_ready_history = []
    for entry in conversation_history:
        role = entry.get('role')
        content = entry.get('content') or ''
        if role == 'assistant':
            content = compact_assistant_transcript(content)
        else:
            content = sanitize_response_text(content)
        if content:
            model_ready_history.append({'role': role, 'content': content})

    workflow_context = analyze_workflow_context(
        message=message,
        conversation_history=model_ready_history,
        project_files=project_state.get('project_files') or {},
        language=language,
        current_code=current_code,
    )
    pre_ai_state = {
        'current_code': project_state.get('current_code') or '',
        'snapshot_files': dict(project_state.get('snapshot_files') or {}),
        'primary_file': project_state.get('primary_file'),
    }

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
        conversation_history=model_ready_history,
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

    workflow_context = result.get('workflow') or workflow_context

    tool_calls = result.get('tool_calls', []) or []
    changed_file_entries = _hydrate_changed_file_contents(
        project_id,
        _collect_changed_file_entries(tool_calls, result.get('created_files', []))
    )
    changed_files = _normalize_changed_files(changed_file_entries)
    doc_updates = _build_doc_updates(changed_file_entries)
    change_review = _build_change_review(changed_file_entries)
    write_tools_used = any(
        (tool_call.get('tool') or tool_call.get('name')) in WRITE_TOOL_NAMES
        and (tool_call.get('result') or {}).get('success') is not False
        for tool_call in tool_calls
    )

    # Save AI response and keep projects.current_code derived from project_files
    recovery_version_id = None
    pre_update_recovery_version_id = None
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

        if code_files_touched or changed_files or write_tools_used:
            state_changed = any([
                (pre_ai_state.get('current_code') or '') != (project_state.get('current_code') or ''),
                (pre_ai_state.get('snapshot_files') or {}) != (project_state.get('snapshot_files') or {}),
                (pre_ai_state.get('primary_file') or '') != (project_state.get('primary_file') or ''),
            ])
            if state_changed:
                pre_update_recovery_version_id = create_recovery_version_from_state(
                    db,
                    project_id,
                    language,
                    current_code=pre_ai_state.get('current_code') or '',
                    snapshot_files=pre_ai_state.get('snapshot_files') or {},
                    primary_file=pre_ai_state.get('primary_file'),
                    reason='Before AI update',
                )

            recovery_version_id = create_recovery_version(
                db,
                {
                    'id': project_id,
                    'language': language,
                    'current_code': project_state.get('current_code') or current_code,
                },
                'After AI update',
            )

        assistant_content = _build_assistant_message(
            result.get('explanation', ''),
            changed_files,
            project_state.get('primary_file'),
            result.get('suggestions', []),
            tool_calls,
            change_review,
            doc_updates=doc_updates,
            decision_notes=result.get('decision_notes', []),
            assumptions=result.get('assumptions', []),
            follow_up_questions=result.get('follow_up_questions', []),
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

    explanation = sanitize_response_text(result.get('explanation', ''))

    return jsonify({
        'success': True,
        'response': {
            'explanation': explanation,
            'decision_notes': result.get('decision_notes', []),
            'assumptions': result.get('assumptions', []),
            'follow_up_questions': result.get('follow_up_questions', []),
            'workflow': workflow_context,
            'code': response_code,
            'suggestions': result['suggestions'],
            'model': result['model'],
            'tokens_used': result['tokens_used'],
            'tool_calls': tool_calls,
            'created_files': changed_files,
            'changed_files': changed_files,
            'doc_updates': doc_updates,
            'change_review': change_review,
            'primary_file': project_state.get('primary_file'),
            'recovery_version_id': recovery_version_id,
            'pre_update_recovery_version_id': pre_update_recovery_version_id,
        }
    })
