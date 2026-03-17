"""
chat/routes.py - Chat/AI endpoints
Club Kinawa Coding Lab

Provides endpoints for:
- Chat/AI code generation with tool use
"""

from flask import request, jsonify, g

from database import get_db
from auth import require_auth
from ai import get_ai_client
from chat import chat_bp
from chat.rate_limit import check_chat_rate_limit
from projects.state import is_code_file, persist_generated_code, sync_current_code_cache

WRITE_TOOL_NAMES = {'write_file', 'append_file'}


def _normalize_changed_files(tool_calls, created_files):
    """Combine file changes from tool execution and parsed filename blocks."""
    changed = {}

    for file_info in created_files or []:
        filename = (file_info or {}).get('filename')
        if not filename:
            continue
        changed[filename] = {
            'filename': filename,
            'action': file_info.get('action', 'updated')
        }

    for tool_call in tool_calls or []:
        tool_name = tool_call.get('tool') or tool_call.get('name')
        tool_input = tool_call.get('input') or {}
        tool_result = tool_call.get('result') or {}
        filename = tool_input.get('filename')
        if tool_name not in WRITE_TOOL_NAMES or not filename or tool_result.get('success') is False:
            continue
        changed[filename] = {
            'filename': filename,
            'action': tool_result.get('action', 'updated')
        }

    return list(changed.values())


def _build_assistant_message(explanation, changed_files, primary_file, suggestions, tool_calls):
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
    changed_files = _normalize_changed_files(tool_calls, result.get('created_files', []))
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
            tool_calls
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
            'primary_file': project_state.get('primary_file')
        }
    })
