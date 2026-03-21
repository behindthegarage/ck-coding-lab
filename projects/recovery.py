"""
projects/recovery.py - Shared hidden recovery checkpoint helpers
Club Kinawa Coding Lab
"""

from typing import Optional

from projects.state import build_project_state, serialize_files_snapshot


RECOVERY_VERSION_PREFIX = '__ckcl_recovery__:'


def is_recovery_version_description(description: Optional[str]) -> bool:
    """Return True when a version description marks a hidden recovery checkpoint."""
    return bool((description or '').startswith(RECOVERY_VERSION_PREFIX))


def get_recovery_version_reason(description: Optional[str]) -> Optional[str]:
    """Strip the hidden prefix from a recovery checkpoint description."""
    if not is_recovery_version_description(description):
        return None

    reason = (description or '')[len(RECOVERY_VERSION_PREFIX):].strip()
    return reason or 'Automatic recovery checkpoint'


def create_recovery_version(db, project_row, reason, *, dedupe_against_latest=True):
    """Persist a hidden recovery checkpoint for the project's current state."""
    language = project_row.get('language') or 'undecided'
    state = build_project_state(
        db,
        project_row['id'],
        language,
        fallback_current_code=project_row.get('current_code') or '',
        synthesize_primary_file=True,
    )

    current_code = state.get('current_code') or ''
    snapshot_files = state.get('snapshot_files') or {}
    primary_file = state.get('primary_file')
    serialized_snapshot = serialize_files_snapshot(snapshot_files)

    if not snapshot_files and not current_code.strip():
        return None

    if dedupe_against_latest:
        db.execute(
            '''
                SELECT id, code, description, files_snapshot, entry_filename
                FROM code_versions
                WHERE project_id = ?
                ORDER BY created_at DESC, id DESC
                LIMIT 1
            ''',
            (project_row['id'],),
        )
        latest_version = db.fetchone()
        if latest_version and is_recovery_version_description(latest_version['description']):
            latest_code = latest_version['code'] or ''
            latest_snapshot = latest_version['files_snapshot']
            latest_entry = latest_version['entry_filename']
            if (
                latest_code == current_code
                and latest_snapshot == serialized_snapshot
                and (latest_entry or '') == (primary_file or '')
            ):
                return latest_version['id']

    db.execute(
        '''
            INSERT INTO code_versions (project_id, code, description, files_snapshot, entry_filename)
            VALUES (?, ?, ?, ?, ?)
        ''',
        (
            project_row['id'],
            current_code,
            f'{RECOVERY_VERSION_PREFIX}{reason}',
            serialized_snapshot,
            primary_file,
        ),
    )
    return db.lastrowid
