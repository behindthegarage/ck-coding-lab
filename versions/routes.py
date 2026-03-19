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
from projects.access import can_access_project_owner
from projects.state import (
    build_project_state,
    default_code_filename,
    deserialize_files_snapshot,
    materialize_version_files,
    restore_version_snapshot,
    serialize_files_snapshot,
)


def _build_version_summary(version, language, live_snapshot_files, live_entry_filename):
    """Return version metadata tailored for the history UI."""
    files, resolved_entry_filename = materialize_version_files(
        language,
        code=version.get('code') or '',
        files_snapshot=version.get('files_snapshot'),
        entry_filename=version.get('entry_filename'),
    )

    entry_filename = resolved_entry_filename or version.get('entry_filename') or default_code_filename(language)

    summary = {
        'id': version['id'],
        'description': version.get('description'),
        'created_at': version.get('created_at'),
        'entry_filename': entry_filename,
        'has_files_snapshot': 1 if version.get('files_snapshot') else 0,
        'file_count': len(files),
        'code_size': len(version.get('code') or ''),
        'matches_live_state': files == live_snapshot_files and entry_filename == live_entry_filename,
    }

    return summary


@versions_bp.route('/projects/<int:project_id>/versions', methods=['POST'])
@require_auth
def save_version(project_id):
    """Save a named version of the current code."""
    data = request.get_json()

    description = data.get('description', '').strip() if data else ''

    with get_db() as db:
        # Verify access and build a coherent snapshot from project files first
        db.execute('''
            SELECT user_id, current_code, language FROM projects WHERE id = ?
        ''', (project_id,))

        result = db.fetchone()
        if not result or not can_access_project_owner(g.current_user, result['user_id']):
            return jsonify({"success": False, "error": "Project not found"}), 404

        project_state = build_project_state(
            db,
            project_id,
            result['language'] or 'undecided',
            fallback_current_code=result['current_code'] or '',
            synthesize_primary_file=True
        )
        current_code = project_state['current_code']

        if not project_state['has_code']:
            return jsonify({"success": False, "error": "No code to save"}), 400

        # Save version
        db.execute('''
            INSERT INTO code_versions (project_id, code, description, files_snapshot, entry_filename)
            VALUES (?, ?, ?, ?, ?)
        ''', (
            project_id,
            current_code,
            description,
            serialize_files_snapshot(project_state['snapshot_files']),
            project_state['primary_file'] or default_code_filename(result['language'])
        ))

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

    with get_db() as db:
        # Verify access and fetch live state for version comparisons
        db.execute('''
            SELECT user_id, current_code, language
            FROM projects
            WHERE id = ?
        ''', (project_id,))
        project = db.fetchone()
        if not project or not can_access_project_owner(g.current_user, project['user_id']):
            return jsonify({"success": False, "error": "Project not found"}), 404

        language = project['language'] or 'undecided'
        live_state = build_project_state(
            db,
            project_id,
            language,
            fallback_current_code=project['current_code'] or '',
            synthesize_primary_file=True,
        )
        live_snapshot_files = live_state['snapshot_files']
        live_entry_filename = live_state['primary_file'] or default_code_filename(language)

        db.execute('''
            SELECT id, code, description, created_at, files_snapshot, entry_filename
            FROM code_versions
            WHERE project_id = ?
            ORDER BY created_at DESC, id DESC
        ''', (project_id,))

        versions = [
            _build_version_summary(row_to_dict(row), language, live_snapshot_files, live_entry_filename)
            for row in db.fetchall()
        ]

    return jsonify({"success": True, "versions": versions})


@versions_bp.route('/projects/<int:project_id>/versions/<int:version_id>/restore', methods=['POST'])
@require_auth
def restore_version(project_id, version_id):
    """Restore a saved version into the live project state."""

    with get_db() as db:
        db.execute('SELECT user_id, language FROM projects WHERE id = ?', (project_id,))
        project = db.fetchone()
        if not project or not can_access_project_owner(g.current_user, project['user_id']):
            return jsonify({"success": False, "error": "Project not found"}), 404

        db.execute('''
            SELECT code, description, files_snapshot, entry_filename
            FROM code_versions
            WHERE id = ? AND project_id = ?
        ''', (version_id, project_id))
        version = row_to_dict(db.fetchone())

        if not version:
            return jsonify({"success": False, "error": "Version not found"}), 404

        restored_state = restore_version_snapshot(
            db,
            project_id,
            project['language'] or 'undecided',
            code=version.get('code') or '',
            files_snapshot=version.get('files_snapshot'),
            entry_filename=version.get('entry_filename'),
        )

    return jsonify({
        "success": True,
        "version_id": version_id,
        "description": version.get('description', ''),
        "entry_filename": restored_state.get('restored_entry_filename'),
        "restored_files_count": len(restored_state.get('project_files', {})),
    })


@versions_bp.route('/projects/<int:project_id>/versions/<int:version_id>', methods=['GET'])
@require_auth
def get_version(project_id, version_id):
    """Get a specific version's code."""

    with get_db() as db:
        # Verify access and fetch project language for legacy snapshot fallback
        db.execute('SELECT user_id, language FROM projects WHERE id = ?', (project_id,))
        project = db.fetchone()
        if not project or not can_access_project_owner(g.current_user, project['user_id']):
            return jsonify({"success": False, "error": "Project not found"}), 404

        db.execute('''
            SELECT code, description, created_at, files_snapshot, entry_filename
            FROM code_versions
            WHERE id = ? AND project_id = ?
        ''', (version_id, project_id))

        version = row_to_dict(db.fetchone())

        if not version:
            return jsonify({"success": False, "error": "Version not found"}), 404

        files = deserialize_files_snapshot(version.pop('files_snapshot', None))
        if files is None and version.get('code'):
            entry_filename = version.get('entry_filename') or default_code_filename(project['language'])
            files = {entry_filename: version['code']}
            version['entry_filename'] = entry_filename

        version['files'] = files

    return jsonify({"success": True, "version": version})
