"""Validation helpers for project code after AI edits."""

from __future__ import annotations

import os
import re
import subprocess
import tempfile
from typing import Dict, Optional

from projects.state import choose_primary_code_file


_NODE_PATH_LINE_RE = re.compile(r'^.+:(\d+)\s*$', re.MULTILINE)
_NODE_MESSAGE_RE = re.compile(r'^(SyntaxError: .+)$', re.MULTILINE)


def current_code_from_project_files(
    project_files: Optional[Dict[str, str]],
    language: str,
    fallback_current_code: str = '',
) -> str:
    """Return the current primary code content from a file map."""
    files = project_files or {}
    primary_file = choose_primary_code_file(language, files)
    if primary_file and primary_file in files:
        return files.get(primary_file, '') or ''
    return fallback_current_code or ''


def validate_javascript_files(
    project_files: Optional[Dict[str, str]],
    language: str = 'undecided',
) -> Optional[Dict[str, object]]:
    """Run a lightweight Node syntax check against project JavaScript files.

    Returns the first syntax error found, or None when files pass / Node is unavailable.
    """
    files = project_files or {}
    js_files = {
        filename: content
        for filename, content in files.items()
        if (filename or '').lower().endswith('.js') and (content or '').strip()
    }

    if not js_files:
        return None

    for filename in sorted(js_files):
        content = js_files[filename] or ''
        temp_path = None
        try:
            with tempfile.NamedTemporaryFile('w', suffix='.js', delete=False) as handle:
                handle.write(content)
                temp_path = handle.name

            result = subprocess.run(
                ['node', '--check', temp_path],
                capture_output=True,
                text=True,
                timeout=15,
            )
        except FileNotFoundError:
            return None
        except subprocess.TimeoutExpired:
            return {
                'filename': filename,
                'line': None,
                'column': None,
                'message': 'JavaScript syntax check timed out.',
                'stderr': 'JavaScript syntax check timed out.',
                'language': language,
            }
        finally:
            if temp_path and os.path.exists(temp_path):
                os.unlink(temp_path)

        if result.returncode == 0:
            continue

        stderr = (result.stderr or '').strip()
        line_match = _NODE_PATH_LINE_RE.search(stderr)
        message_match = _NODE_MESSAGE_RE.search(stderr)
        caret_column = None
        for stderr_line in stderr.splitlines():
            if '^' in stderr_line:
                caret_column = stderr_line.index('^') + 1
                break

        return {
            'filename': filename,
            'line': int(line_match.group(1)) if line_match else None,
            'column': caret_column,
            'message': message_match.group(1) if message_match else 'JavaScript syntax check failed.',
            'stderr': stderr,
            'language': language,
        }

    return None


def format_validation_error(error: Optional[Dict[str, object]]) -> str:
    """Turn a validation result into a compact human-readable sentence."""
    if not error:
        return 'Unknown validation error.'

    filename = error.get('filename') or 'unknown file'
    message = error.get('message') or 'Validation failed.'
    line = error.get('line')
    column = error.get('column')

    location_bits = []
    if line is not None:
        location_bits.append(f'line {line}')
    if column is not None:
        location_bits.append(f'col {column}')

    if location_bits:
        return f"{filename} ({', '.join(location_bits)}): {message}"
    return f"{filename}: {message}"
