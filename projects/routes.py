"""
projects/routes.py - Project CRUD operations
Club Kinawa Coding Lab

Provides endpoints for:
- Project CRUD operations
"""

from flask import request, jsonify, g

from database import get_db, row_to_dict
from auth import require_auth
from projects import project_bp
from projects.utils import create_default_files
from sandbox import CodeValidator


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
    """Create a new project with default files."""
    data = request.get_json()
    
    if not data or 'name' not in data:
        return jsonify({"success": False, "error": "Project name is required"}), 400
    
    name = data['name'].strip()
    description = data.get('description', '').strip()
    language = data.get('language', 'undecided')
    user_id = g.current_user['id']
    
    if len(name) < 1 or len(name) > 100:
        return jsonify({"success": False, "error": "Project name must be 1-100 characters"}), 400
    
    with get_db() as db:
        db.execute('''
            INSERT INTO projects (user_id, name, description, current_code, language)
            VALUES (?, ?, ?, ?, ?)
        ''', (user_id, name, description, '', language))
        
        project_id = db.lastrowid
        
        # Create default files for the project
        create_default_files(db, project_id, name)
        
        # Fetch the created project
        db.execute('SELECT * FROM projects WHERE id = ?', (project_id,))
        project = row_to_dict(db.fetchone())
    
    return jsonify({"success": True, "project": project}), 201


@project_bp.route('/projects/<int:project_id>', methods=['GET'])
@require_auth
def get_project(project_id):
    """Get a single project with conversation history and files."""
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
        
        # Get project files
        db.execute('''
            SELECT id, filename, created_at, updated_at
            FROM project_files
            WHERE project_id = ?
            ORDER BY 
                CASE filename
                    WHEN 'design.md' THEN 1
                    WHEN 'architecture.md' THEN 2
                    WHEN 'todo.md' THEN 3
                    WHEN 'notes.md' THEN 4
                    ELSE 5
                END,
                filename ASC
        ''', (project_id,))
        
        files = [row_to_dict(row) for row in db.fetchall()]
    
    return jsonify({
        "success": True,
        "project": project,
        "conversations": conversations,
        "files": files
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


@project_bp.route('/projects/<int:project_id>/validate', methods=['POST'])
@require_auth
def validate_code(project_id):
    """Validate code for security issues before running."""
    user_id = g.current_user['id']
    data = request.get_json()
    
    if not data or 'code' not in data:
        return jsonify({"success": False, "error": "Code is required"}), 400
    
    code = data['code']
    language = data.get('language', 'undecided')
    
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
