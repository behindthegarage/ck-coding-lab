"""
versions/routes.py - Code version management endpoints
Club Kinawa Coding Lab

Provides endpoints for:
- Saving code versions
- Listing versions
- Retrieving specific versions
"""

from flask import request, jsonify, g

from database import get_db, row_to_dict
from auth import require_auth
from versions import versions_bp


@versions_bp.route('/projects/<int:project_id>/versions', methods=['POST'])
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


@versions_bp.route('/projects/<int:project_id>/versions', methods=['GET'])
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


@versions_bp.route('/projects/<int:project_id>/versions/<int:version_id>', methods=['GET'])
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
