"""
file_routes.py - Project File System API Routes
Club Kinawa Coding Lab - Agentic Workflow

Provides endpoints for:
- Project file CRUD operations
- File-based project memory (design.md, architecture.md, todo.md, notes.md, code files)
"""

from functools import wraps
from flask import Blueprint, request, jsonify, g
from datetime import datetime

from database import get_db, row_to_dict
from auth import validate_session


# Create blueprint
file_bp = Blueprint('files', __name__, url_prefix='/api')


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


def verify_project_access(project_id, user_id):
    """Verify user owns the project. Returns True if access granted."""
    with get_db() as db:
        db.execute('SELECT id FROM projects WHERE id = ? AND user_id = ?', (project_id, user_id))
        return db.fetchone() is not None


# ============ PROJECT FILE ROUTES ============

@file_bp.route('/projects/<int:project_id>/files', methods=['GET'])
@require_auth
def list_project_files(project_id):
    """Get all files for a project."""
    user_id = g.current_user['id']
    
    if not verify_project_access(project_id, user_id):
        return jsonify({"success": False, "error": "Project not found"}), 404
    
    with get_db() as db:
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
    
    return jsonify({"success": True, "files": files})


@file_bp.route('/projects/<int:project_id>/files', methods=['POST'])
@require_auth
def create_project_file(project_id):
    """Create a new file in the project."""
    user_id = g.current_user['id']
    data = request.get_json()
    
    if not data or 'filename' not in data:
        return jsonify({"success": False, "error": "Filename is required"}), 400
    
    filename = data['filename'].strip()
    content = data.get('content', '')
    
    # Validate filename
    if not filename or len(filename) > 255:
        return jsonify({"success": False, "error": "Invalid filename"}), 400
    
    # Prevent path traversal
    if '/' in filename or '\\' in filename or '..' in filename:
        return jsonify({"success": False, "error": "Invalid filename"}), 400
    
    if not verify_project_access(project_id, user_id):
        return jsonify({"success": False, "error": "Project not found"}), 404
    
    with get_db() as db:
        try:
            db.execute('''
                INSERT INTO project_files (project_id, filename, content)
                VALUES (?, ?, ?)
            ''', (project_id, filename, content))
            
            file_id = db.lastrowid
            
            # Fetch the created file
            db.execute('SELECT * FROM project_files WHERE id = ?', (file_id,))
            file_data = row_to_dict(db.fetchone())
            
            return jsonify({"success": True, "file": file_data}), 201
            
        except Exception as e:
            if "UNIQUE constraint failed" in str(e):
                return jsonify({"success": False, "error": "File already exists"}), 409
            raise


@file_bp.route('/files/<int:file_id>', methods=['GET'])
@require_auth
def get_file(file_id):
    """Get a single file's content."""
    user_id = g.current_user['id']
    
    with get_db() as db:
        # Join with projects to verify ownership
        db.execute('''
            SELECT pf.*, p.user_id as project_owner_id, p.id as project_id
            FROM project_files pf
            JOIN projects p ON pf.project_id = p.id
            WHERE pf.id = ?
        ''', (file_id,))
        
        row = db.fetchone()
        if not row:
            return jsonify({"success": False, "error": "File not found"}), 404
        
        if row['project_owner_id'] != user_id:
            return jsonify({"success": False, "error": "Access denied"}), 403
        
        file_data = row_to_dict(row)
        # Remove internal fields
        file_data.pop('project_owner_id', None)
    
    return jsonify({"success": True, "file": file_data})


@file_bp.route('/files/<int:file_id>', methods=['PUT'])
@require_auth
def update_file(file_id):
    """Update a file's content."""
    user_id = g.current_user['id']
    data = request.get_json()
    
    if not data or 'content' not in data:
        return jsonify({"success": False, "error": "Content is required"}), 400
    
    content = data['content']
    
    with get_db() as db:
        # Verify ownership through project
        db.execute('''
            SELECT pf.id, p.user_id as project_owner_id
            FROM project_files pf
            JOIN projects p ON pf.project_id = p.id
            WHERE pf.id = ?
        ''', (file_id,))
        
        row = db.fetchone()
        if not row:
            return jsonify({"success": False, "error": "File not found"}), 404
        
        if row['project_owner_id'] != user_id:
            return jsonify({"success": False, "error": "Access denied"}), 403
        
        # Update file
        db.execute('''
            UPDATE project_files
            SET content = ?, updated_at = CURRENT_TIMESTAMP
            WHERE id = ?
        ''', (content, file_id))
        
        # Fetch updated file
        db.execute('SELECT * FROM project_files WHERE id = ?', (file_id,))
        file_data = row_to_dict(db.fetchone())
    
    return jsonify({"success": True, "file": file_data})


@file_bp.route('/files/<int:file_id>', methods=['DELETE'])
@require_auth
def delete_file(file_id):
    """Delete a file."""
    user_id = g.current_user['id']
    
    with get_db() as db:
        # Verify ownership through project
        db.execute('''
            SELECT pf.id, p.user_id as project_owner_id
            FROM project_files pf
            JOIN projects p ON pf.project_id = p.id
            WHERE pf.id = ?
        ''', (file_id,))
        
        row = db.fetchone()
        if not row:
            return jsonify({"success": False, "error": "File not found"}), 404
        
        if row['project_owner_id'] != user_id:
            return jsonify({"success": False, "error": "Access denied"}), 403
        
        # Delete file
        db.execute('DELETE FROM project_files WHERE id = ?', (file_id,))
    
    return jsonify({"success": True})


@file_bp.route('/projects/<int:project_id>/files/<string:filename>', methods=['GET'])
@require_auth
def get_file_by_name(project_id, filename):
    """Get a file by project_id and filename."""
    user_id = g.current_user['id']
    
    if not verify_project_access(project_id, user_id):
        return jsonify({"success": False, "error": "Project not found"}), 404
    
    with get_db() as db:
        db.execute('''
            SELECT * FROM project_files
            WHERE project_id = ? AND filename = ?
        ''', (project_id, filename))
        
        row = db.fetchone()
        if not row:
            return jsonify({"success": False, "error": "File not found"}), 404
        
        file_data = row_to_dict(row)
    
    return jsonify({"success": True, "file": file_data})


@file_bp.route('/projects/<int:project_id>/files/<string:filename>', methods=['PUT'])
@require_auth
def update_file_by_name(project_id, filename):
    """Update or create a file by name (upsert)."""
    user_id = g.current_user['id']
    data = request.get_json()
    
    if not data or 'content' not in data:
        return jsonify({"success": False, "error": "Content is required"}), 400
    
    content = data['content']
    
    if not verify_project_access(project_id, user_id):
        return jsonify({"success": False, "error": "Project not found"}), 404
    
    with get_db() as db:
        # Check if file exists
        db.execute('''
            SELECT id FROM project_files
            WHERE project_id = ? AND filename = ?
        ''', (project_id, filename))
        
        existing = db.fetchone()
        
        if existing:
            # Update existing
            db.execute('''
                UPDATE project_files
                SET content = ?, updated_at = CURRENT_TIMESTAMP
                WHERE id = ?
            ''', (content, existing['id']))
            file_id = existing['id']
        else:
            # Create new
            db.execute('''
                INSERT INTO project_files (project_id, filename, content)
                VALUES (?, ?, ?)
            ''', (project_id, filename, content))
            file_id = db.lastrowid
        
        # Fetch the file
        db.execute('SELECT * FROM project_files WHERE id = ?', (file_id,))
        file_data = row_to_dict(db.fetchone())
    
    return jsonify({"success": True, "file": file_data})


# ============ BULK OPERATIONS ============

@file_bp.route('/projects/<int:project_id>/files/bulk', methods=['GET'])
@require_auth
def get_all_files_content(project_id):
    """Get content of all files for context loading."""
    user_id = g.current_user['id']
    
    if not verify_project_access(project_id, user_id):
        return jsonify({"success": False, "error": "Project not found"}), 404
    
    with get_db() as db:
        db.execute('''
            SELECT filename, content
            FROM project_files
            WHERE project_id = ?
            ORDER BY filename
        ''', (project_id,))
        
        files = {}
        for row in db.fetchall():
            files[row['filename']] = row['content']
    
    return jsonify({"success": True, "files": files})


@file_bp.route('/projects/<int:project_id>/files/bulk', methods=['POST'])
@require_auth
def create_default_files(project_id):
    """Create default files for a new project (design.md, architecture.md, todo.md, notes.md)."""
    user_id = g.current_user['id']
    
    if not verify_project_access(project_id, user_id):
        return jsonify({"success": False, "error": "Project not found"}), 404
    
    # Get project name for templates
    with get_db() as db:
        db.execute('SELECT name FROM projects WHERE id = ?', (project_id,))
        row = db.fetchone()
        project_name = row['name'] if row else 'New Project'
    
    # Default file templates
    default_files = {
        'design.md': f"""# Design: {project_name}

## Elevator Pitch

[One sentence describing what this project does]

## Core Features

- Feature 1
- Feature 2
- Feature 3

## Stretch Goals

- [ ] Stretch feature 1
- [ ] Stretch feature 2

## Open Questions

- What technology stack should we use?
- What's the simplest version we can build first?
""",
        'architecture.md': f"""# Architecture: {project_name}

## Technology Stack

- Language: [p5.js / HTML/CSS/JS / Python]
- Key Libraries: 
- Target Platform: [Browser / Desktop / Mobile]

## File Structure

```
{project_name}/
├── main.js (or main.py, index.html)
└── [other files]
```

## Key Components

1. **Component 1** - Description
2. **Component 2** - Description

## Dependencies

- None yet

## Notes

[Any technical decisions or constraints]
""",
        'todo.md': f"""# Todo: {project_name}

## Current

- [ ] Initial setup
- [ ] Define core features

## Completed

_None yet_

## Blocked

_None yet_

## Ideas

- Future improvement 1
- Future improvement 2
""",
        'notes.md': f"""# Notes: {project_name}

## Session Log

### {datetime.now().strftime('%Y-%m-%d')}

- Project created
- Initial ideas:

## Research

[Links, references, things to remember]

## Questions to Ask

- 

## Decisions Made

- 
"""
    }
    
    created_files = []
    
    with get_db() as db:
        for filename, content in default_files.items():
            try:
                db.execute('''
                    INSERT INTO project_files (project_id, filename, content)
                    VALUES (?, ?, ?)
                ''', (project_id, filename, content))
                created_files.append(filename)
            except Exception as e:
                if "UNIQUE constraint failed" in str(e):
                    # File already exists, skip
                    pass
                else:
                    raise
    
    return jsonify({
        "success": True,
        "created": created_files,
        "message": f"Created {len(created_files)} default files"
    })
