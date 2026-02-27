"""
project_routes.py - Project and Chat API Routes
Club Kinawa Coding Lab

Provides endpoints for:
- Project CRUD operations
- Chat/AI code generation
- Code version management
"""

from functools import wraps
from flask import Blueprint, request, jsonify, g
from datetime import datetime, timedelta
import secrets

from database import get_db, row_to_dict
from auth import validate_session
from ai_client import get_ai_client
from sandbox import CodeValidator, SandboxConfig


# Create blueprint
project_bp = Blueprint('projects', __name__, url_prefix='/api')


def require_auth(f):
    """Decorator to require valid session token."""
    @wraps(f)
    def decorated(*args, **kwargs):
        auth_header = request.headers.get('Authorization', '')
        if not auth_header.startswith('Bearer '):
            return jsonify({"success": False, "error": "Missing or invalid authorization header"}), 401
        
        token = auth_header[7:]  # Remove "Bearer "
        user = validate_session(token)
        
        if not user:
            return jsonify({"success": False, "error": "Invalid or expired session"}), 401
        
        # Store user in flask g for route access
        g.current_user = user
        g.current_token = token
        
        return f(*args, **kwargs)
    return decorated


# ============ PROJECT ROUTES ============

@project_bp.route('/projects', methods=['GET'])
@require_auth
def list_projects():
    """Get all projects for the current user."""
    user_id = g.current_user['id']
    
    with get_db() as db:
        db.execute('''
            SELECT id, name, description, created_at, updated_at, is_public, share_token, language
            FROM projects
            WHERE user_id = ?
            ORDER BY updated_at DESC
        ''', (user_id,))
        
        projects = [row_to_dict(row) for row in db.fetchall()]
    
    return jsonify({"success": True, "projects": projects})


@project_bp.route('/projects', methods=['POST'])
@require_auth
def create_project():
    """Create a new project."""
    data = request.get_json()
    
    if not data or 'name' not in data:
        return jsonify({"success": False, "error": "Project name is required"}), 400
    
    name = data['name'].strip()
    description = data.get('description', '').strip()
    language = data.get('language', 'p5js')  # Default to p5js
    user_id = g.current_user['id']
    
    if len(name) < 1 or len(name) > 100:
        return jsonify({"success": False, "error": "Project name must be 1-100 characters"}), 400
    
    with get_db() as db:
        db.execute('''
            INSERT INTO projects (user_id, name, description, current_code, language)
            VALUES (?, ?, ?, ?, ?)
        ''', (user_id, name, description, '', language))
        
        project_id = db.lastrowid
        
        # Fetch the created project
        db.execute('SELECT * FROM projects WHERE id = ?', (project_id,))
        project = row_to_dict(db.fetchone())
    
    return jsonify({"success": True, "project": project}), 201


@project_bp.route('/projects/<int:project_id>', methods=['GET'])
@require_auth
def get_project(project_id):
    """Get a single project with conversation history."""
    user_id = g.current_user['id']
    
    with get_db() as db:
        # Get project
        db.execute('''
            SELECT * FROM projects WHERE id = ? AND user_id = ?
        ''', (project_id, user_id))
        
        project = row_to_dict(db.fetchone())
        
        if not project:
            return jsonify({"success": False, "error": "Project not found"}), 404
        
        # Get conversation history
        db.execute('''
            SELECT id, role, content, model, tokens_used, created_at
            FROM conversations
            WHERE project_id = ?
            ORDER BY created_at ASC
        ''', (project_id,))
        
        conversations = [row_to_dict(row) for row in db.fetchall()]
    
    return jsonify({
        "success": True,
        "project": project,
        "conversations": conversations
    })


@project_bp.route('/projects/<int:project_id>', methods=['PUT'])
@require_auth
def update_project(project_id):
    """Update project name/description."""
    user_id = g.current_user['id']
    data = request.get_json()
    
    with get_db() as db:
        # Verify ownership
        db.execute('SELECT id FROM projects WHERE id = ? AND user_id = ?', (project_id, user_id))
        if not db.fetchone():
            return jsonify({"success": False, "error": "Project not found"}), 404
        
        # Build update
        updates = []
        params = []
        
        if 'name' in data:
            name = data['name'].strip()
            if len(name) < 1 or len(name) > 100:
                return jsonify({"success": False, "error": "Project name must be 1-100 characters"}), 400
            updates.append('name = ?')
            params.append(name)
        
        if 'description' in data:
            description = data['description'].strip()
            if len(description) > 500:
                return jsonify({"success": False, "error": "Description must be under 500 characters"}), 400
            updates.append('description = ?')
            params.append(description)
        
        if not updates:
            return jsonify({"success": False, "error": "No fields to update"}), 400
        
        updates.append('updated_at = CURRENT_TIMESTAMP')
        params.append(project_id)
        
        db.execute(f'''
            UPDATE projects
            SET {', '.join(updates)}
            WHERE id = ?
        ''', params)
        
        # Fetch updated project
        db.execute('SELECT * FROM projects WHERE id = ?', (project_id,))
        project = row_to_dict(db.fetchone())
    
    return jsonify({"success": True, "project": project})


@project_bp.route('/projects/<int:project_id>', methods=['DELETE'])
@require_auth
def delete_project(project_id):
    """Delete a project and all its data."""
    user_id = g.current_user['id']
    
    with get_db() as db:
        # Verify ownership and delete
        db.execute('DELETE FROM projects WHERE id = ? AND user_id = ?', (project_id, user_id))
        
        if db.rowcount == 0:
            return jsonify({"success": False, "error": "Project not found"}), 404
    
    return jsonify({"success": True})


# ============ CHAT/AI ROUTES ============

@project_bp.route('/projects/<int:project_id>/chat', methods=['POST'])
@require_auth
def chat_with_ai(project_id):
    """
    Send a message to AI and get code response.
    Stores conversation history.
    """
    user_id = g.current_user['id']
    data = request.get_json()
    
    if not data or 'message' not in data:
        return jsonify({"success": False, "error": "Message is required"}), 400
    
    message = data['message'].strip()
    model = data.get('model', 'kimi-k2.5')  # Default to Kimi
    
    if len(message) > 2000:
        return jsonify({"success": False, "error": "Message too long (max 2000 chars)"}), 400
    
    with get_db() as db:
        # Verify ownership and get current code AND language
        db.execute('''
            SELECT id, current_code, language FROM projects WHERE id = ? AND user_id = ?
        ''', (project_id, user_id))
        
        result = db.fetchone()
        if not result:
            return jsonify({"success": False, "error": "Project not found"}), 404
        
        current_code = result['current_code'] or ''
        language = result['language'] or 'p5js'  # Default to p5js
        
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
    
    # Call AI with the project's language
    ai = get_ai_client()
    result = ai.generate_code(
        message=message,
        conversation_history=conversation_history,
        current_code=current_code,
        language=language,  # Pass the project language!
        model=model
    )
    
    if not result['success']:
        return jsonify({
            "success": False,
            "error": result.get('error', 'AI generation failed')
        }), 500
    
    # Save AI response
    with get_db() as db:
        db.execute('''
            INSERT INTO conversations (project_id, role, content, model, tokens_used)
            VALUES (?, ?, ?, ?, ?)
        ''', (
            project_id,
            'assistant',
            result['full_response'],
            model,
            result['tokens_used']
        ))
        
        # Update project code if code was generated
        if result['code']:
            db.execute('''
                UPDATE projects
                SET current_code = ?, updated_at = CURRENT_TIMESTAMP
                WHERE id = ?
            ''', (result['code'], project_id))
    
    return jsonify({
        "success": True,
        "response": {
            "explanation": result['explanation'],
            "code": result['code'],
            "suggestions": result['suggestions'],
            "model": result['model'],
            "tokens_used": result['tokens_used']
        }
    })


# ============ CODE VERSION ROUTES ============

@project_bp.route('/projects/<int:project_id>/versions', methods=['POST'])
@require_auth
def save_version(project_id):
    """Save a named version of the current code."""
    user_id = g.current_user['id']
    data = request.get_json()
    
    description = data.get('description', '').strip() if data else ''
    
    with get_db() as db:
        # Verify ownership and get current code
        db.execute('''
            SELECT current_code FROM projects WHERE id = ? AND user_id = ?
        ''', (project_id, user_id))
        
        result = db.fetchone()
        if not result:
            return jsonify({"success": False, "error": "Project not found"}), 404
        
        current_code = result['current_code'] or ''
        
        if not current_code:
            return jsonify({"success": False, "error": "No code to save"}), 400
        
        # Save version
        db.execute('''
            INSERT INTO code_versions (project_id, code, description)
            VALUES (?, ?, ?)
        ''', (project_id, current_code, description))
        
        version_id = db.lastrowid
    
    return jsonify({
        "success": True,
        "version_id": version_id,
        "description": description
    })


@project_bp.route('/projects/<int:project_id>/versions', methods=['GET'])
@require_auth
def list_versions(project_id):
    """List all saved versions for a project."""
    user_id = g.current_user['id']
    
    with get_db() as db:
        # Verify ownership
        db.execute('SELECT id FROM projects WHERE id = ? AND user_id = ?', (project_id, user_id))
        if not db.fetchone():
            return jsonify({"success": False, "error": "Project not found"}), 404
        
        db.execute('''
            SELECT id, description, created_at
            FROM code_versions
            WHERE project_id = ?
            ORDER BY created_at DESC
        ''', (project_id,))
        
        versions = [row_to_dict(row) for row in db.fetchall()]
    
    return jsonify({"success": True, "versions": versions})


@project_bp.route('/projects/<int:project_id>/versions/<int:version_id>', methods=['GET'])
@require_auth
def get_version(project_id, version_id):
    """Get a specific version's code."""
    user_id = g.current_user['id']
    
    with get_db() as db:
        # Verify ownership
        db.execute('SELECT id FROM projects WHERE id = ? AND user_id = ?', (project_id, user_id))
        if not db.fetchone():
            return jsonify({"success": False, "error": "Project not found"}), 404
        
        db.execute('''
            SELECT code, description, created_at
            FROM code_versions
            WHERE id = ? AND project_id = ?
        ''', (version_id, project_id))
        
        version = row_to_dict(db.fetchone())
        
        if not version:
            return jsonify({"success": False, "error": "Version not found"}), 404
    
    return jsonify({"success": True, "version": version})


# ============ SANDBOX VALIDATION ============

@project_bp.route('/projects/<int:project_id>/validate', methods=['POST'])
@require_auth
def validate_code(project_id):
    """Validate code for security issues before running."""
    user_id = g.current_user['id']
    data = request.get_json()
    
    if not data or 'code' not in data:
        return jsonify({"success": False, "error": "Code is required"}), 400
    
    code = data['code']
    language = data.get('language', 'p5js')
    
    # Verify ownership
    with get_db() as db:
        db.execute('SELECT id FROM projects WHERE id = ? AND user_id = ?', (project_id, user_id))
        if not db.fetchone():
            return jsonify({"success": False, "error": "Project not found"}), 404
    
    # Validate code
    validator = CodeValidator()
    is_valid, issues = validator.validate(code, language)
    
    return jsonify({
        "success": True,
        "valid": is_valid,
        "issues": issues
    })
