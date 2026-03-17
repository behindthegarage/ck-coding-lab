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
            "success": False, 
            "error": f"Rate limit exceeded. Try again in {reset_after} seconds."
        }), 429
    
    data = request.get_json()
    
    if not data or 'message' not in data:
        return jsonify({"success": False, "error": "Message is required"}), 400
    
    message = data['message'].strip()
    model = data.get('model', 'kimi-k2.5')
    enable_tools = data.get('enable_tools', True)
    
    if len(message) > 2000:
        return jsonify({"success": False, "error": "Message too long (max 2000 chars)"}), 400
    
    with get_db() as db:
        # Verify ownership and derive current code from authoritative project files
        db.execute('''
            SELECT id, current_code, language FROM projects WHERE id = ? AND user_id = ?
        ''', (project_id, user_id))
        
        result = db.fetchone()
        if not result:
            return jsonify({"success": False, "error": "Project not found"}), 404
        
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
            {"role": row['role'], "content": row['content']}
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
            "success": False,
            "error": result.get('error', 'AI generation failed')
        }), 500
    
    # Build AI response content including tool call info
    ai_content = result['full_response']
    if result.get('tool_calls'):
        tool_summary = "\n\n---\n\n**Tool Calls:**\n"
        for tc in result['tool_calls']:
            tool_summary += f"- `{tc['tool']}`: {tc['input'].get('filename', '')} → {tc['result'].get('action', 'executed')}\n"
        ai_content += tool_summary
    
    # Save AI response and keep projects.current_code derived from project_files
    with get_db() as db:
        db.execute('''
            INSERT INTO conversations (project_id, role, content, model, tokens_used)
            VALUES (?, ?, ?, ?, ?)
        ''', (
            project_id,
            'assistant',
            ai_content,
            model,
            result['tokens_used']
        ))

        tool_calls = result.get('tool_calls', []) or []
        code_files_touched = any(
            is_code_file((tc.get('input') or {}).get('filename', ''))
            for tc in tool_calls
        )

        # For simple single-file responses without tool-based writes, persist the
        # generated code into project_files so files remain the source of truth.
        if result['code'] and not tool_calls:
            persist_generated_code(db, project_id, language, result['code'])
            code_files_touched = True

        project_state = sync_current_code_cache(
            db,
            project_id,
            language,
            fallback_current_code=current_code,
            touch_project=bool(result['code'] or tool_calls)
        )

    response_code = result['code']
    if result['code'] or code_files_touched:
        response_code = project_state['current_code']
    
    return jsonify({
        "success": True,
        "response": {
            "explanation": result['explanation'],
            "code": response_code,
            "suggestions": result['suggestions'],
            "model": result['model'],
            "tokens_used": result['tokens_used'],
            "tool_calls": result.get('tool_calls', []),
            "created_files": result.get('created_files', [])
        }
    })
