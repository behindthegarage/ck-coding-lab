"""
projects/state.py - Project source-of-truth helpers
Club Kinawa Coding Lab

Keeps project code, files, and version snapshots aligned.

Model:
- project_files is the authoritative source for multi-file project state
- projects.current_code is a derived compatibility/cache field for simple previews
- version snapshots persist the full file map plus a primary code file/content
"""

import json
from typing import Dict, Optional


CODE_FILE_EXTENSIONS = ('.js', '.html', '.css', '.py')
DEFAULT_CODE_FILENAMES = {
    'html': 'index.html',
    'python': 'main.py',
    'p5js': 'sketch.js',
    'undecided': 'sketch.js',
}
PRIMARY_FILE_CANDIDATES = {
    'html': ['index.html', 'main.js', 'script.js', 'styles.css'],
    'python': ['main.py', 'app.py'],
    'p5js': ['sketch.js', 'main.js'],
    'undecided': ['sketch.js', 'main.js', 'index.html', 'main.py'],
}


def is_code_file(filename: str) -> bool:
    """Return True when a filename is considered runnable/source code."""
    if not filename:
        return False
    return filename.endswith(CODE_FILE_EXTENSIONS)


def default_code_filename(language: Optional[str]) -> str:
    """Pick the default primary code filename for a language."""
    return DEFAULT_CODE_FILENAMES.get(language or 'undecided', 'sketch.js')


def load_project_files(db, project_id: int) -> Dict[str, str]:
    """Load all project files into a filename -> content mapping."""
    db.execute('''
        SELECT filename, content
        FROM project_files
        WHERE project_id = ?
        ORDER BY filename
    ''', (project_id,))
    return {row['filename']: row['content'] for row in db.fetchall()}


def choose_primary_code_file(language: Optional[str], project_files: Dict[str, str]) -> Optional[str]:
    """Choose the file whose contents should be mirrored into current_code."""
    if not project_files:
        return None

    for filename in PRIMARY_FILE_CANDIDATES.get(language or 'undecided', PRIMARY_FILE_CANDIDATES['undecided']):
        if filename in project_files and is_code_file(filename):
            return filename

    code_files = sorted(filename for filename in project_files if is_code_file(filename))
    if len(code_files) == 1:
        return code_files[0]
    if 'index.html' in project_files:
        return 'index.html'
    if code_files:
        return code_files[0]
    return None


def build_project_state(
    db,
    project_id: int,
    language: Optional[str],
    fallback_current_code: str = '',
    synthesize_primary_file: bool = False,
) -> Dict:
    """
    Build a coherent project state from authoritative files plus legacy fallback code.

    If synthesize_primary_file is True and there is legacy current_code but no code file,
    include a synthetic primary file in the returned snapshot without mutating the DB.
    """
    project_files = load_project_files(db, project_id)
    primary_file = choose_primary_code_file(language, project_files)

    if primary_file:
        current_code = project_files.get(primary_file, '') or ''
    else:
        current_code = fallback_current_code or ''
        if current_code.strip():
            primary_file = default_code_filename(language)

    snapshot_files = dict(project_files)
    if synthesize_primary_file and primary_file and current_code.strip() and primary_file not in snapshot_files:
        snapshot_files[primary_file] = current_code

    code_files = sorted(filename for filename in snapshot_files if is_code_file(filename))
    has_code = any((snapshot_files.get(filename) or '').strip() for filename in code_files) or bool(current_code.strip())

    return {
        'project_id': project_id,
        'language': language or 'undecided',
        'current_code': current_code,
        'primary_file': primary_file,
        'project_files': project_files,
        'snapshot_files': snapshot_files,
        'code_files': code_files,
        'has_code': has_code,
    }


def upsert_project_file(db, project_id: int, filename: str, content: str) -> None:
    """Create or update a project file by filename."""
    db.execute('''
        SELECT id FROM project_files
        WHERE project_id = ? AND filename = ?
    ''', (project_id, filename))
    existing = db.fetchone()

    if existing:
        db.execute('''
            UPDATE project_files
            SET content = ?, updated_at = CURRENT_TIMESTAMP
            WHERE id = ?
        ''', (content, existing['id']))
    else:
        db.execute('''
            INSERT INTO project_files (project_id, filename, content)
            VALUES (?, ?, ?)
        ''', (project_id, filename, content))


def persist_generated_code(db, project_id: int, language: Optional[str], code: str) -> str:
    """Persist single-file generated code into the authoritative project_files set."""
    state = build_project_state(db, project_id, language)
    filename = state['primary_file'] or default_code_filename(language)
    upsert_project_file(db, project_id, filename, code)
    return filename


def sync_current_code_cache(
    db,
    project_id: int,
    language: Optional[str],
    fallback_current_code: str = '',
    touch_project: bool = False,
) -> Dict:
    """Recompute and store the derived current_code field from project files."""
    state = build_project_state(db, project_id, language, fallback_current_code=fallback_current_code)

    if touch_project:
        db.execute('''
            UPDATE projects
            SET current_code = ?, updated_at = CURRENT_TIMESTAMP
            WHERE id = ?
        ''', (state['current_code'], project_id))
    else:
        db.execute('''
            UPDATE projects
            SET current_code = ?
            WHERE id = ?
        ''', (state['current_code'], project_id))

    return state


def serialize_files_snapshot(files: Dict[str, str]) -> Optional[str]:
    """Serialize a version file snapshot for storage."""
    if not files:
        return None
    return json.dumps(files, sort_keys=True)


def deserialize_files_snapshot(files_snapshot: Optional[str]) -> Optional[Dict[str, str]]:
    """Deserialize a stored version file snapshot."""
    if not files_snapshot:
        return None
    try:
        data = json.loads(files_snapshot)
        if isinstance(data, dict):
            return data
    except (TypeError, ValueError):
        pass
    return None
