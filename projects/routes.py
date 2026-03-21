"""
projects/routes.py - Project CRUD operations and teacher/admin oversight tools
Club Kinawa Coding Lab
"""

import re
from datetime import UTC, datetime, timedelta

from flask import request, jsonify, g

from database import get_db, row_to_dict
from auth import require_auth
from ai.parser import sanitize_response_text
from projects import project_bp
from projects.access import can_access_project_owner, is_admin_user
from projects.recovery import RECOVERY_VERSION_PREFIX, create_recovery_version
from projects.state import (
    build_project_state,
    replace_project_files,
    sync_current_code_cache,
)
from projects.utils import (
    MAX_PROJECT_DESCRIPTION_LENGTH,
    create_default_files,
    normalize_project_language,
)
from sandbox import CodeValidator


LATEST_PREVIEW_LIMIT = 140
ATTENTION_ACTIVITY_GRACE = timedelta(hours=24)
REVIEW_FILE_PATTERN = re.compile(r"^###\s+`([^`]+)`", re.MULTILINE)
REVIEW_SUMMARY_PATTERN = re.compile(r"^- Summary:\s*(.+)$", re.MULTILINE)


LIST_PROJECTS_SQL = f'''
    SELECT
        p.id,
        p.user_id,
        p.name,
        p.description,
        p.current_code,
        p.created_at,
        p.updated_at,
        p.is_public,
        p.share_token,
        p.language,
        p.archived_at,
        u.username AS owner_username,
        u.role AS owner_role,
        (
            SELECT COUNT(*)
            FROM project_files pf
            WHERE pf.project_id = p.id
        ) AS file_count,
        (
            SELECT COUNT(*)
            FROM project_files pf
            WHERE pf.project_id = p.id
              AND (
                pf.filename LIKE '%.js'
                OR pf.filename LIKE '%.html'
                OR pf.filename LIKE '%.css'
                OR pf.filename LIKE '%.py'
              )
        ) AS code_file_count,
        (
            SELECT MAX(pf.updated_at)
            FROM project_files pf
            WHERE pf.project_id = p.id
        ) AS latest_file_update_at,
        (
            SELECT COUNT(*)
            FROM code_versions cv
            WHERE cv.project_id = p.id
              AND (cv.description IS NULL OR cv.description NOT LIKE '{RECOVERY_VERSION_PREFIX}%')
        ) AS version_count,
        (
            SELECT MAX(cv.created_at)
            FROM code_versions cv
            WHERE cv.project_id = p.id
              AND (cv.description IS NULL OR cv.description NOT LIKE '{RECOVERY_VERSION_PREFIX}%')
        ) AS latest_version_at,
        (
            SELECT COUNT(*)
            FROM code_versions cv
            WHERE cv.project_id = p.id
              AND cv.description LIKE '{RECOVERY_VERSION_PREFIX}%'
        ) AS recovery_version_count,
        (
            SELECT MAX(cv.created_at)
            FROM code_versions cv
            WHERE cv.project_id = p.id
              AND cv.description LIKE '{RECOVERY_VERSION_PREFIX}%'
        ) AS latest_recovery_version_at,
        (
            SELECT COUNT(*)
            FROM conversations c
            WHERE c.project_id = p.id
        ) AS conversation_count,
        (
            SELECT MAX(c.created_at)
            FROM conversations c
            WHERE c.project_id = p.id
        ) AS latest_conversation_at,
        (
            SELECT c2.content
            FROM conversations c2
            WHERE c2.project_id = p.id AND c2.role = 'user'
            ORDER BY c2.created_at DESC, c2.id DESC
            LIMIT 1
        ) AS latest_user_message,
        (
            SELECT c3.content
            FROM conversations c3
            WHERE c3.project_id = p.id AND c3.role = 'assistant'
            ORDER BY c3.created_at DESC, c3.id DESC
            LIMIT 1
        ) AS latest_assistant_message
    FROM projects p
    JOIN users u ON u.id = p.user_id
'''


PROJECT_WITH_OWNER_SQL = '''
    SELECT p.*, u.username AS owner_username, u.role AS owner_role
    FROM projects p
    JOIN users u ON u.id = p.user_id
    WHERE p.id = ?
'''



def _safe_preview(text, limit=LATEST_PREVIEW_LIMIT):
    cleaned = ' '.join((text or '').strip().split())
    if len(cleaned) <= limit:
        return cleaned
    return cleaned[: limit - 1].rstrip() + '…'



def _extract_latest_review(assistant_message):
    content = assistant_message or ''
    filenames = REVIEW_FILE_PATTERN.findall(content)
    summaries = REVIEW_SUMMARY_PATTERN.findall(content)

    if not filenames:
        return None

    review_items = []
    for index, filename in enumerate(filenames[:3]):
        review_items.append({
            'filename': filename,
            'summary': summaries[index] if index < len(summaries) else 'Updated file'
        })

    return {
        'file_count': len(filenames),
        'items': review_items,
        'headline': f"{review_items[0]['filename']} • {review_items[0]['summary']}"
    }



def _parse_timestamp(value):
    if not value:
        return None
    if isinstance(value, datetime):
        return value

    for fmt in ('%Y-%m-%d %H:%M:%S', '%Y-%m-%dT%H:%M:%S'):
        try:
            return datetime.strptime(str(value), fmt)
        except ValueError:
            continue
    return None



def _latest_timestamp(*values):
    parsed = [_parse_timestamp(value) for value in values if value]
    return max(parsed) if parsed else None



def _is_recent_timestamp(value, grace=ATTENTION_ACTIVITY_GRACE):
    parsed = _parse_timestamp(value)
    if not parsed:
        return False
    return datetime.now(UTC).replace(tzinfo=None) - parsed <= grace



def _compute_latest_activity(project):
    latest = _latest_timestamp(
        project.get('updated_at'),
        project.get('latest_file_update_at'),
        project.get('latest_version_at'),
        project.get('latest_recovery_version_at'),
        project.get('latest_conversation_at'),
    )
    if latest is None:
        return project.get('updated_at')
    return latest.strftime('%Y-%m-%d %H:%M:%S')



def _build_attention_reasons(project):
    if project.get('archived_at'):
        return []

    reasons = []
    version_count = int(project.get('version_count') or 0)
    recovery_version_count = int(project.get('recovery_version_count') or 0)
    conversation_count = int(project.get('conversation_count') or 0)
    code_file_count = int(project.get('code_file_count') or 0)
    has_current_code = bool((project.get('current_code') or '').strip())
    latest_review = project.get('latest_review') or {}

    created_at = _parse_timestamp(project.get('created_at'))
    latest_file_update_at = _parse_timestamp(project.get('latest_file_update_at'))
    latest_checkpoint_at = _latest_timestamp(
        project.get('latest_version_at'),
        project.get('latest_recovery_version_at'),
    )
    latest_activity_at = project.get('latest_activity_at') or project.get('updated_at')

    has_runnable_code = has_current_code or code_file_count > 0
    has_checkpoint = version_count > 0 or recovery_version_count > 0
    has_post_create_file_edits = bool(
        latest_file_update_at
        and created_at
        and latest_file_update_at > created_at
    )
    has_meaningful_progress = bool(latest_review) or conversation_count > 0 or has_post_create_file_edits
    latest_changes_unprotected = bool(
        has_post_create_file_edits
        and (latest_checkpoint_at is None or latest_file_update_at > latest_checkpoint_at)
    )
    recently_active = _is_recent_timestamp(latest_activity_at)

    if has_meaningful_progress and not has_runnable_code:
        reasons.append('No runnable code yet')

    if has_meaningful_progress and latest_changes_unprotected and not recently_active:
        reasons.append(
            'Progress has no save or recovery point yet'
            if not has_checkpoint
            else 'Latest changes are newer than the last checkpoint'
        )

    return reasons[:3]



def _build_project_overview(row):
    project = row_to_dict(row)
    latest_review = _extract_latest_review(project.get('latest_assistant_message'))
    latest_activity_at = _compute_latest_activity(project)

    project['latest_review'] = latest_review
    project['latest_activity_at'] = latest_activity_at
    project['latest_user_message_preview'] = _safe_preview(project.get('latest_user_message'))
    project['latest_assistant_preview'] = _safe_preview(project.get('latest_assistant_message'))
    project['is_archived'] = bool(project.get('archived_at'))
    project['attention_reasons'] = _build_attention_reasons({**project, 'latest_review': latest_review})
    project['needs_attention'] = bool(project['attention_reasons'])
    project['status'] = (
        'archived'
        if project['is_archived']
        else 'needs-attention'
        if project['needs_attention']
        else 'active'
    )
    project['can_administer'] = True
    return project



def _load_project_with_owner(db, project_id):
    db.execute(PROJECT_WITH_OWNER_SQL, (project_id,))
    row = db.fetchone()
    return row_to_dict(row) if row else None



def _get_accessible_project(project_id):
    with get_db() as db:
        project = _load_project_with_owner(db, project_id)

    if not project or not can_access_project_owner(g.current_user, project['user_id']):
        return None

    return project


def _copy_project_versions(db, source_project_id, target_project_id):
    db.execute(
        '''
            SELECT code, description, files_snapshot, entry_filename
            FROM code_versions
            WHERE project_id = ?
            ORDER BY created_at ASC, id ASC
        ''',
        (source_project_id,),
    )
    versions = db.fetchall()

    copied = 0
    for version in versions:
        db.execute(
            '''
                INSERT INTO code_versions (project_id, code, description, files_snapshot, entry_filename)
                VALUES (?, ?, ?, ?, ?)
            ''',
            (
                target_project_id,
                version['code'],
                version['description'],
                version['files_snapshot'],
                version['entry_filename'],
            ),
        )
        copied += 1

    return copied


@project_bp.route('/projects', methods=['GET'])
@require_auth
def list_projects():
    """Get accessible projects with richer oversight metadata."""
    current_user = g.current_user
    scope = (request.args.get('scope') or '').strip().lower()

    where_clause = 'WHERE p.user_id = ?'
    params = [current_user['id']]

    if is_admin_user(current_user) and scope != 'mine':
        where_clause = ''
        params = []

    with get_db() as db:
        db.execute(
            f'''
                {LIST_PROJECTS_SQL}
                {where_clause}
                ORDER BY p.updated_at DESC, p.id DESC
            ''',
            params,
        )
        projects = [_build_project_overview(row) for row in db.fetchall()]

    summary = {
        'total_projects': len(projects),
        'archived_projects': sum(1 for project in projects if project.get('is_archived')),
        'needs_attention_projects': sum(1 for project in projects if project.get('needs_attention')),
        'active_projects': sum(1 for project in projects if not project.get('is_archived')),
        'recent_projects': sum(1 for project in projects if project.get('latest_activity_at') == project.get('updated_at')),
    }

    return jsonify({
        'success': True,
        'projects': projects,
        'summary': summary,
        'scope': 'all' if is_admin_user(current_user) and scope != 'mine' else 'mine',
    })


@project_bp.route('/projects', methods=['POST'])
@require_auth
def create_project():
    """Create a new project with default files."""
    data = request.get_json(silent=True) or {}

    if 'name' not in data:
        return jsonify({"success": False, "error": "Project name is required"}), 400

    name = data['name'].strip()
    description = data.get('description', '').strip()
    language = normalize_project_language(data.get('language', 'undecided'))
    user_id = g.current_user['id']

    if len(name) < 1 or len(name) > 100:
        return jsonify({"success": False, "error": "Project name must be 1-100 characters"}), 400
    if len(description) > MAX_PROJECT_DESCRIPTION_LENGTH:
        return jsonify({"success": False, "error": f"Description must be under {MAX_PROJECT_DESCRIPTION_LENGTH} characters"}), 400

    with get_db() as db:
        db.execute(
            '''
                INSERT INTO projects (user_id, name, description, current_code, language)
                VALUES (?, ?, ?, ?, ?)
            ''',
            (user_id, name, description, '', language),
        )

        project_id = db.lastrowid

        create_default_files(db, project_id, name, language=language, description=description)

        db.execute('SELECT * FROM projects WHERE id = ?', (project_id,))
        project = row_to_dict(db.fetchone())

    return jsonify({"success": True, "project": project}), 201


@project_bp.route('/projects/<int:project_id>', methods=['GET'])
@require_auth
def get_project(project_id):
    """Get a single project with conversation history and files."""
    current_user = g.current_user

    with get_db() as db:
        project = _load_project_with_owner(db, project_id)
        if not project or not can_access_project_owner(current_user, project['user_id']):
            return jsonify({"success": False, "error": "Project not found"}), 404

        project_state = sync_current_code_cache(
            db,
            project_id,
            project.get('language') or 'undecided',
            fallback_current_code=project.get('current_code', '') or '',
            touch_project=False,
        )
        project['current_code'] = project_state['current_code']
        project['is_archived'] = bool(project.get('archived_at'))
        project['can_administer'] = True

        db.execute(
            '''
                SELECT id, role, content, model, tokens_used, created_at
                FROM conversations
                WHERE project_id = ?
                ORDER BY created_at ASC, id ASC
            ''',
            (project_id,),
        )
        conversations = []
        for row in db.fetchall():
            item = row_to_dict(row)
            if item.get('role') == 'assistant':
                item['content'] = sanitize_response_text(item.get('content') or '')
            conversations.append(item)

        db.execute(
            '''
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
            ''',
            (project_id,),
        )
        files = [row_to_dict(row) for row in db.fetchall()]

    return jsonify({
        "success": True,
        "project": project,
        "conversations": conversations,
        "files": files,
    })


@project_bp.route('/projects/<int:project_id>', methods=['PUT'])
@require_auth
def update_project(project_id):
    """Update project name/description."""
    data = request.get_json(silent=True) or {}

    with get_db() as db:
        project = _load_project_with_owner(db, project_id)
        if not project or not can_access_project_owner(g.current_user, project['user_id']):
            return jsonify({"success": False, "error": "Project not found"}), 404

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
            if len(description) > MAX_PROJECT_DESCRIPTION_LENGTH:
                return jsonify({"success": False, "error": f"Description must be under {MAX_PROJECT_DESCRIPTION_LENGTH} characters"}), 400
            updates.append('description = ?')
            params.append(description)

        if not updates:
            return jsonify({"success": False, "error": "No fields to update"}), 400

        updates.append('updated_at = CURRENT_TIMESTAMP')
        params.append(project_id)

        db.execute(
            f'''
                UPDATE projects
                SET {', '.join(updates)}
                WHERE id = ?
            ''',
            params,
        )

        db.execute('SELECT * FROM projects WHERE id = ?', (project_id,))
        project = row_to_dict(db.fetchone())

    return jsonify({"success": True, "project": project})


@project_bp.route('/projects/<int:project_id>', methods=['DELETE'])
@require_auth
def delete_project(project_id):
    """Delete a project and all its data."""
    with get_db() as db:
        project = _load_project_with_owner(db, project_id)
        if not project or not can_access_project_owner(g.current_user, project['user_id']):
            return jsonify({"success": False, "error": "Project not found"}), 404

        db.execute('DELETE FROM projects WHERE id = ?', (project_id,))

    return jsonify({"success": True})


@project_bp.route('/projects/<int:project_id>/duplicate', methods=['POST'])
@require_auth
def duplicate_project(project_id):
    """Create a safe duplicate of a project for experimentation or recovery."""
    data = request.get_json(silent=True) or {}

    with get_db() as db:
        project = _load_project_with_owner(db, project_id)
        if not project or not can_access_project_owner(g.current_user, project['user_id']):
            return jsonify({"success": False, "error": "Project not found"}), 404

        name = (data.get('name') or f"{project['name']} Copy").strip()
        if len(name) < 1 or len(name) > 100:
            return jsonify({"success": False, "error": "Project name must be 1-100 characters"}), 400

        description = (project.get('description') or '').strip()
        language = normalize_project_language(project.get('language') or 'undecided')
        project_state = build_project_state(
            db,
            project_id,
            language,
            fallback_current_code=project.get('current_code') or '',
            synthesize_primary_file=True,
        )

        db.execute(
            '''
                INSERT INTO projects (user_id, name, description, current_code, language, archived_at)
                VALUES (?, ?, ?, ?, ?, NULL)
            ''',
            (
                project['user_id'],
                name,
                description,
                project_state.get('current_code') or '',
                language,
            ),
        )
        duplicate_id = db.lastrowid

        replace_project_files(db, duplicate_id, project_state.get('snapshot_files') or {})
        sync_current_code_cache(db, duplicate_id, language, fallback_current_code='', touch_project=True)
        copied_versions = _copy_project_versions(db, project_id, duplicate_id)

        db.execute('SELECT * FROM projects WHERE id = ?', (duplicate_id,))
        duplicate = row_to_dict(db.fetchone())

    return jsonify({
        "success": True,
        "project": duplicate,
        "copied_versions": copied_versions,
        "copied_files": len(project_state.get('snapshot_files') or {}),
    }), 201


@project_bp.route('/projects/<int:project_id>/archive', methods=['POST'])
@require_auth
def archive_project(project_id):
    """Archive or unarchive a project without deleting its data."""
    data = request.get_json(silent=True) or {}

    with get_db() as db:
        project = _load_project_with_owner(db, project_id)
        if not project or not can_access_project_owner(g.current_user, project['user_id']):
            return jsonify({"success": False, "error": "Project not found"}), 404

        archived = data.get('archived')
        if archived is None:
            archived = not bool(project.get('archived_at'))

        if archived:
            db.execute(
                '''
                    UPDATE projects
                    SET archived_at = CURRENT_TIMESTAMP, updated_at = CURRENT_TIMESTAMP
                    WHERE id = ?
                ''',
                (project_id,),
            )
        else:
            db.execute(
                '''
                    UPDATE projects
                    SET archived_at = NULL, updated_at = CURRENT_TIMESTAMP
                    WHERE id = ?
                ''',
                (project_id,),
            )

        db.execute('SELECT * FROM projects WHERE id = ?', (project_id,))
        updated_project = row_to_dict(db.fetchone())

    return jsonify({
        "success": True,
        "project": {
            **updated_project,
            'is_archived': bool(updated_project.get('archived_at')),
        },
    })


@project_bp.route('/projects/<int:project_id>/reset', methods=['POST'])
@require_auth
def reset_project(project_id):
    """Reset the live project files back to the starter state with an automatic recovery point."""

    with get_db() as db:
        project = _load_project_with_owner(db, project_id)
        if not project or not can_access_project_owner(g.current_user, project['user_id']):
            return jsonify({"success": False, "error": "Project not found"}), 404

        recovery_version_id = create_recovery_version(db, project, 'Before reset to starter')

        db.execute('DELETE FROM project_files WHERE project_id = ?', (project_id,))

        created_files = create_default_files(
            db,
            project_id,
            project['name'],
            language=project.get('language') or 'undecided',
            description=project.get('description') or '',
        )
        sync_current_code_cache(
            db,
            project_id,
            project.get('language') or 'undecided',
            fallback_current_code='',
            touch_project=True,
        )

    return jsonify({
        "success": True,
        "created_files": created_files,
        "recovery_version_id": recovery_version_id,
        "message": 'Project reset to its starter files.',
    })


@project_bp.route('/projects/<int:project_id>/validate', methods=['POST'])
@require_auth
def validate_code(project_id):
    """Validate code for security issues before running."""
    data = request.get_json()

    if not data or 'code' not in data:
        return jsonify({"success": False, "error": "Code is required"}), 400

    code = data['code']

    with get_db() as db:
        project = _load_project_with_owner(db, project_id)
        if not project or not can_access_project_owner(g.current_user, project['user_id']):
            return jsonify({"success": False, "error": "Project not found"}), 404

    validator = CodeValidator()
    is_valid, issues = validator.validate(code)

    return jsonify({
        "success": True,
        "valid": is_valid,
        "issues": issues,
    })
