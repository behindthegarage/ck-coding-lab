"""
file_routes.py - Project File System API Routes
Club Kinawa Coding Lab - Agentic Workflow

Provides endpoints for:
- Project file CRUD operations
- File-based project memory (design.md, architecture.md, todo.md, notes.md, code files)
"""

from functools import wraps
from flask import Blueprint, request, jsonify, g

from database import get_db, row_to_dict
from auth import validate_session
from projects.access import can_access_project_owner
from projects.state import build_project_state, is_code_file, sync_current_code_cache
from projects.utils import create_default_files as create_project_default_files


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


def verify_project_access(project_id, current_user):
    """Verify that the current user can access the project."""
    with get_db() as db:
        db.execute('SELECT id, user_id FROM projects WHERE id = ?', (project_id,))
        row = db.fetchone()
        return bool(row and can_access_project_owner(current_user, row['user_id']))


def validate_filename(filename):
    """Validate a project filename or nested path."""
    filename = (filename or '').strip()

    if not filename or len(filename) > 255:
        return False, "Invalid filename"

    if '\\' in filename or filename.startswith('/') or filename.endswith('/'):
        return False, "Invalid filename"

    segments = filename.split('/')
    if any(not segment or segment in {'.', '..'} for segment in segments):
        return False, "Invalid filename"

    return True, filename


# ============ PROJECT FILE ROUTES ============

@file_bp.route('/projects/<int:project_id>/files', methods=['GET'])
@require_auth
def list_project_files(project_id):
    """Get all files for a project."""
    if not verify_project_access(project_id, g.current_user):
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
    data = request.get_json()
    
    if not data or 'filename' not in data:
        return jsonify({"success": False, "error": "Filename is required"}), 400
    
    is_valid, filename = validate_filename(data['filename'])
    content = data.get('content', '')

    if not is_valid:
        return jsonify({"success": False, "error": filename}), 400
    
    if not verify_project_access(project_id, g.current_user):
        return jsonify({"success": False, "error": "Project not found"}), 404
    
    with get_db() as db:
        try:
            db.execute('''
                INSERT INTO project_files (project_id, filename, content)
                VALUES (?, ?, ?)
            ''', (project_id, filename, content))
            
            file_id = db.lastrowid

            db.execute('SELECT language, current_code FROM projects WHERE id = ?', (project_id,))
            project = db.fetchone()
            sync_current_code_cache(
                db,
                project_id,
                project['language'] if project else 'undecided',
                fallback_current_code=(project['current_code'] if project else '') or '',
                touch_project=True
            )
            
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
        
        if not can_access_project_owner(g.current_user, row['project_owner_id']):
            return jsonify({"success": False, "error": "Access denied"}), 403
        
        file_data = row_to_dict(row)
        # Remove internal fields
        file_data.pop('project_owner_id', None)
    
    return jsonify({"success": True, "file": file_data})


@file_bp.route('/files/<int:file_id>', methods=['PUT'])
@require_auth
def update_file(file_id):
    """Update a file's content."""
    data = request.get_json()
    
    if not data or 'content' not in data:
        return jsonify({"success": False, "error": "Content is required"}), 400
    
    content = data['content']
    
    with get_db() as db:
        # Verify ownership through project
        db.execute('''
            SELECT pf.id, pf.project_id, p.user_id as project_owner_id,
                   p.language, p.current_code
            FROM project_files pf
            JOIN projects p ON pf.project_id = p.id
            WHERE pf.id = ?
        ''', (file_id,))
        
        row = db.fetchone()
        if not row:
            return jsonify({"success": False, "error": "File not found"}), 404
        
        if not can_access_project_owner(g.current_user, row['project_owner_id']):
            return jsonify({"success": False, "error": "Access denied"}), 403
        
        # Update file
        db.execute('''
            UPDATE project_files
            SET content = ?, updated_at = CURRENT_TIMESTAMP
            WHERE id = ?
        ''', (content, file_id))

        sync_current_code_cache(
            db,
            row['project_id'],
            row['language'] or 'undecided',
            fallback_current_code=row['current_code'] or '',
            touch_project=True
        )
        
        # Fetch updated file
        db.execute('SELECT * FROM project_files WHERE id = ?', (file_id,))
        file_data = row_to_dict(db.fetchone())
    
    return jsonify({"success": True, "file": file_data})


@file_bp.route('/files/<int:file_id>/rename', methods=['PUT'])
@require_auth
def rename_file(file_id):
    """Rename a file."""
    data = request.get_json()

    if not data or 'filename' not in data:
        return jsonify({"success": False, "error": "Filename is required"}), 400

    is_valid, new_filename = validate_filename(data['filename'])
    if not is_valid:
        return jsonify({"success": False, "error": new_filename}), 400

    with get_db() as db:
        db.execute('''
            SELECT pf.id, pf.filename, pf.project_id, p.user_id as project_owner_id,
                   p.language, p.current_code
            FROM project_files pf
            JOIN projects p ON pf.project_id = p.id
            WHERE pf.id = ?
        ''', (file_id,))

        row = db.fetchone()
        if not row:
            return jsonify({"success": False, "error": "File not found"}), 404

        if not can_access_project_owner(g.current_user, row['project_owner_id']):
            return jsonify({"success": False, "error": "Access denied"}), 403

        if row['filename'] == new_filename:
            db.execute('SELECT * FROM project_files WHERE id = ?', (file_id,))
            return jsonify({"success": True, "file": row_to_dict(db.fetchone())})

        db.execute('''
            SELECT id FROM project_files
            WHERE project_id = ? AND filename = ? AND id != ?
        ''', (row['project_id'], new_filename, file_id))
        if db.fetchone():
            return jsonify({"success": False, "error": "File already exists"}), 409

        db.execute('''
            UPDATE project_files
            SET filename = ?, updated_at = CURRENT_TIMESTAMP
            WHERE id = ?
        ''', (new_filename, file_id))

        sync_current_code_cache(
            db,
            row['project_id'],
            row['language'] or 'undecided',
            fallback_current_code=row['current_code'] or '',
            touch_project=True
        )

        db.execute('SELECT * FROM project_files WHERE id = ?', (file_id,))
        file_data = row_to_dict(db.fetchone())

    return jsonify({"success": True, "file": file_data})


@file_bp.route('/files/<int:file_id>', methods=['DELETE'])
@require_auth
def delete_file(file_id):
    """Delete a file."""
    
    with get_db() as db:
        # Verify ownership through project
        db.execute('''
            SELECT pf.id, pf.project_id, pf.filename, pf.content, p.user_id as project_owner_id,
                   p.language, p.current_code
            FROM project_files pf
            JOIN projects p ON pf.project_id = p.id
            WHERE pf.id = ?
        ''', (file_id,))
        
        row = db.fetchone()
        if not row:
            return jsonify({"success": False, "error": "File not found"}), 404
        
        if not can_access_project_owner(g.current_user, row['project_owner_id']):
            return jsonify({"success": False, "error": "Access denied"}), 403
        
        # Delete file
        db.execute('DELETE FROM project_files WHERE id = ?', (file_id,))

        sync_current_code_cache(
            db,
            row['project_id'],
            row['language'] or 'undecided',
            fallback_current_code='' if is_code_file(row['filename']) else (row['current_code'] or ''),
            touch_project=True
        )
    
    return jsonify({
        "success": True,
        "deleted_file": {
            "id": row['id'],
            "project_id": row['project_id'],
            "filename": row['filename'],
            "content": row['content'] or '',
        }
    })


@file_bp.route('/projects/<int:project_id>/files/<path:filename>', methods=['GET'])
@require_auth
def get_file_by_name(project_id, filename):
    """Get a file by project_id and filename."""

    is_valid, filename = validate_filename(filename)
    if not is_valid:
        return jsonify({"success": False, "error": filename}), 400
    
    if not verify_project_access(project_id, g.current_user):
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


@file_bp.route('/projects/<int:project_id>/files/<path:filename>', methods=['PUT'])
@require_auth
def update_file_by_name(project_id, filename):
    """Update or create a file by name (upsert)."""
    data = request.get_json()
    
    if not data or 'content' not in data:
        return jsonify({"success": False, "error": "Content is required"}), 400
    
    content = data['content']

    is_valid, filename = validate_filename(filename)
    if not is_valid:
        return jsonify({"success": False, "error": filename}), 400
    
    if not verify_project_access(project_id, g.current_user):
        return jsonify({"success": False, "error": "Project not found"}), 404
    
    with get_db() as db:
        db.execute('SELECT language, current_code FROM projects WHERE id = ?', (project_id,))
        project = db.fetchone()

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

        sync_current_code_cache(
            db,
            project_id,
            project['language'] if project else 'undecided',
            fallback_current_code=(project['current_code'] if project else '') or '',
            touch_project=True
        )
        
        # Fetch the file
        db.execute('SELECT * FROM project_files WHERE id = ?', (file_id,))
        file_data = row_to_dict(db.fetchone())
    
    return jsonify({"success": True, "file": file_data})


# ============ BULK OPERATIONS ============

@file_bp.route('/projects/<int:project_id>/files/bulk', methods=['GET'])
@require_auth
def get_all_files_content(project_id):
    """Get content of all files for context loading."""
    
    if not verify_project_access(project_id, g.current_user):
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
def seed_default_files(project_id):
    """Create any missing default planning docs plus a starter file for a project."""

    if not verify_project_access(project_id, g.current_user):
        return jsonify({"success": False, "error": "Project not found"}), 404

    with get_db() as db:
        db.execute('SELECT name, language, description FROM projects WHERE id = ?', (project_id,))
        row = db.fetchone()
        project_name = row['name'] if row else 'New Project'
        language = row['language'] if row else 'undecided'
        description = row['description'] if row else ''

        created_files = create_project_default_files(
            db,
            project_id,
            project_name,
            language=language,
            description=description,
        )

        if created_files:
            db.execute('SELECT current_code FROM projects WHERE id = ?', (project_id,))
            project_row = db.fetchone()
            sync_current_code_cache(
                db,
                project_id,
                language,
                fallback_current_code=(project_row['current_code'] if project_row else '') or '',
                touch_project=True,
            )

    created_count = len(created_files)

    return jsonify({
        "success": True,
        "created": created_files,
        "created_count": created_count,
        "message": f"Created {created_count} starter files"
    })


# ============ PREVIEW BUNDLE ROUTES ============



# ============ PREVIEW BUNDLE ROUTES ============

@file_bp.route('/projects/<int:project_id>/preview-bundle', methods=['GET'])
@require_auth
def get_preview_bundle(project_id):
    """Get all files bundled for preview (for multi-file projects)."""

    with get_db() as db:
        db.execute('''
            SELECT user_id, language, current_code
            FROM projects
            WHERE id = ?
        ''', (project_id,))
        project = db.fetchone()
        if not project or not can_access_project_owner(g.current_user, project['user_id']):
            return jsonify({"success": False, "error": "Project not found"}), 404

        project_state = build_project_state(
            db,
            project_id,
            project['language'] or 'undecided',
            fallback_current_code=project['current_code'] or '',
            synthesize_primary_file=True,
        )

    return jsonify({
        "success": True,
        "files": project_state['snapshot_files'],
        "entry_filename": project_state['primary_file'],
    })
