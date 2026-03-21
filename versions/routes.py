"""
versions/routes.py - Code version management endpoints
Club Kinawa Coding Lab

Provides endpoints for:
- Saving code versions
- Listing versions
- Retrieving specific versions
"""

from flask import request, jsonify, g

from auth import require_auth
from database import get_db, row_to_dict
from projects.access import can_access_project_owner
from projects.recovery import (
    create_recovery_version,
    get_recovery_version_reason,
    is_recovery_version_description,
)
from projects.state import (
    build_project_state,
    default_code_filename,
    deserialize_files_snapshot,
    materialize_version_files,
    restore_version_snapshot,
    serialize_files_snapshot,
)
from versions import versions_bp


BASELINE_RECOVERY_REASON = 'Current project when version history was first opened'


def build_checkpoint_metadata(description):
    """Return consistent recovery/manual labels for API consumers and the UI."""
    recovery_reason = get_recovery_version_reason(description)
    is_recovery = is_recovery_version_description(description)
    checkpoint_kind = 'recovery' if is_recovery else 'manual'
    checkpoint_label = 'Automatic checkpoint' if is_recovery else 'Save point'
    checkpoint_detail = recovery_reason if is_recovery else None
    checkpoint_origin = 'baseline' if recovery_reason == BASELINE_RECOVERY_REASON else ('automatic' if is_recovery else 'manual')
    display_description = checkpoint_label if is_recovery else ((description or '').strip() or 'Manual save')

    return {
        'is_recovery': is_recovery,
        'version_type': checkpoint_kind,
        'checkpoint_kind': checkpoint_kind,
        'checkpoint_label': checkpoint_label,
        'checkpoint_detail': checkpoint_detail,
        'checkpoint_origin': checkpoint_origin,
        'recovery_reason': recovery_reason,
        'display_description': display_description,
    }


def _build_version_summary(version, language, live_snapshot_files, live_entry_filename):
    """Return version metadata tailored for the history UI."""
    files, resolved_entry_filename = materialize_version_files(
        language,
        code=version.get('code') or '',
        files_snapshot=version.get('files_snapshot'),
        entry_filename=version.get('entry_filename'),
    )

    entry_filename = resolved_entry_filename or version.get('entry_filename') or default_code_filename(language)
    description = version.get('description')

    summary = {
        'id': version['id'],
        'description': description,
        'created_at': version.get('created_at'),
        'entry_filename': entry_filename,
        'has_files_snapshot': 1 if version.get('files_snapshot') else 0,
        'file_count': len(files),
        'code_size': len(version.get('code') or ''),
        'matches_live_state': files == live_snapshot_files and entry_filename == live_entry_filename,
    }
    summary.update(build_checkpoint_metadata(description))
    return summary


def _project_needs_history_backfill(db, project, live_state):
    """Seed a baseline recovery point only for projects that show meaningful progress."""
    if not live_state.get('has_code'):
        return False

    db.execute(
        '''
            SELECT COUNT(*) AS conversation_count
            FROM conversations
            WHERE project_id = ?
        ''',
        (project['id'],),
    )
    conversation_row = row_to_dict(db.fetchone()) or {}
    conversation_count = int(conversation_row.get('conversation_count') or 0)

    db.execute(
        '''
            SELECT MAX(updated_at) AS latest_file_update_at
            FROM project_files
            WHERE project_id = ?
        ''',
        (project['id'],),
    )
    file_row = row_to_dict(db.fetchone()) or {}
    latest_file_update_at = file_row.get('latest_file_update_at')

    created_at = project.get('created_at') or ''
    updated_at = project.get('updated_at') or ''
    has_project_updates = bool(created_at and updated_at and updated_at > created_at)
    has_file_updates = bool(created_at and latest_file_update_at and latest_file_update_at > created_at)

    return conversation_count > 0 or has_project_updates or has_file_updates


@versions_bp.route('/projects/<int:project_id>/versions', methods=['POST'])
@require_auth
def save_version(project_id):
    """Save a named version of the current code."""
    data = request.get_json()
    description = data.get('description', '').strip() if data else ''

    with get_db() as db:
        db.execute(
            '''
            SELECT user_id, current_code, language FROM projects WHERE id = ?
        ''',
            (project_id,),
        )

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

        if not project_state['has_code']:
            return jsonify({"success": False, "error": "No code to save"}), 400

        db.execute(
            '''
            INSERT INTO code_versions (project_id, code, description, files_snapshot, entry_filename)
            VALUES (?, ?, ?, ?, ?)
        ''',
            (
                project_id,
                project_state['current_code'],
                description,
                serialize_files_snapshot(project_state['snapshot_files']),
                project_state['primary_file'] or default_code_filename(project['language']),
            ),
        )
        version_id = db.lastrowid

    payload = {
        "success": True,
        "version_id": version_id,
        "description": description,
    }
    payload.update(build_checkpoint_metadata(description))
    return jsonify(payload)


@versions_bp.route('/projects/<int:project_id>/versions', methods=['GET'])
@require_auth
def list_versions(project_id):
    """List all saved versions for a project."""

    with get_db() as db:
        db.execute(
            '''
            SELECT id, user_id, current_code, language, created_at, updated_at
            FROM projects
            WHERE id = ?
        ''',
            (project_id,),
        )
        project = row_to_dict(db.fetchone())
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

        baseline_recovery_version_id = None
        created_baseline_recovery = False
        db.execute(
            '''
            SELECT COUNT(*) AS checkpoint_count
            FROM code_versions
            WHERE project_id = ?
        ''',
            (project_id,),
        )
        checkpoint_row = row_to_dict(db.fetchone()) or {}
        checkpoint_count = int(checkpoint_row.get('checkpoint_count') or 0)

        if checkpoint_count == 0 and _project_needs_history_backfill(db, project, live_state):
            baseline_recovery_version_id = create_recovery_version(
                db,
                project,
                BASELINE_RECOVERY_REASON,
            )
            created_baseline_recovery = bool(baseline_recovery_version_id)

        db.execute(
            '''
            SELECT id, code, description, created_at, files_snapshot, entry_filename
            FROM code_versions
            WHERE project_id = ?
            ORDER BY created_at DESC, id DESC
        ''',
            (project_id,),
        )

        versions = [
            _build_version_summary(row_to_dict(row), language, live_snapshot_files, live_entry_filename)
            for row in db.fetchall()
        ]

    return jsonify({
        "success": True,
        "versions": versions,
        "seeded_recovery_version_id": baseline_recovery_version_id,
        "baseline_recovery_version_id": baseline_recovery_version_id,
        "created_baseline_recovery": created_baseline_recovery,
    })


@versions_bp.route('/projects/<int:project_id>/versions/<int:version_id>/restore', methods=['POST'])
@require_auth
def restore_version(project_id, version_id):
    """Restore a saved version into the live project state."""

    with get_db() as db:
        db.execute('SELECT user_id, language FROM projects WHERE id = ?', (project_id,))
        project = db.fetchone()
        if not project or not can_access_project_owner(g.current_user, project['user_id']):
            return jsonify({"success": False, "error": "Project not found"}), 404

        db.execute(
            '''
            SELECT code, description, files_snapshot, entry_filename
            FROM code_versions
            WHERE id = ? AND project_id = ?
        ''',
            (version_id, project_id),
        )
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

    payload = {
        "success": True,
        "version_id": version_id,
        "description": version.get('description', ''),
        "entry_filename": restored_state.get('restored_entry_filename'),
        "restored_files_count": len(restored_state.get('project_files', {})),
    }
    payload.update(build_checkpoint_metadata(version.get('description')))
    return jsonify(payload)


@versions_bp.route('/projects/<int:project_id>/versions/<int:version_id>', methods=['GET'])
@require_auth
def get_version(project_id, version_id):
    """Get a specific version's code."""

    with get_db() as db:
        db.execute('SELECT user_id, language FROM projects WHERE id = ?', (project_id,))
        project = db.fetchone()
        if not project or not can_access_project_owner(g.current_user, project['user_id']):
            return jsonify({"success": False, "error": "Project not found"}), 404

        db.execute(
            '''
            SELECT code, description, created_at, files_snapshot, entry_filename
            FROM code_versions
            WHERE id = ? AND project_id = ?
        ''',
            (version_id, project_id),
        )
        version = row_to_dict(db.fetchone())

        if not version:
            return jsonify({"success": False, "error": "Version not found"}), 404

        files = deserialize_files_snapshot(version.pop('files_snapshot', None))
        if files is None and version.get('code'):
            entry_filename = version.get('entry_filename') or default_code_filename(project['language'])
            files = {entry_filename: version['code']}
            version['entry_filename'] = entry_filename

        version['files'] = files
        version.update(build_checkpoint_metadata(version.get('description')))

    return jsonify({"success": True, "version": version})
