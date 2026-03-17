# ai/parser.py - Response Parsing for AI Output
"""
Parse AI responses to extract code, explanations, suggestions, and file declarations.
"""

import re
from typing import Dict, List, Optional

from ai.tools import FileTools
from projects.state import choose_primary_code_file

FILE_START_PATTERN = re.compile(
    r'```([A-Za-z0-9_+#.-]+)\s+\[?([^\]\n]+)\]?\s*\n',
    re.DOTALL
)
FILE_PREFIX_PATTERN = re.compile(
    r'(?:File|file):\s*([\w.\-/]+)\s*\n```([A-Za-z0-9_+#.-]+)?\s*\n(.*?)```',
    re.DOTALL
)
TOOL_SUMMARY_MARKER = '\n---\n\n**Tool Calls:**'
SECTION_HEADING_PATTERN = re.compile(r'(?im)^##+\s+')
SUGGESTION_PATTERNS = [
    r'(?:^|\n)(?:##+\s*)?(?:Next ideas|Next steps|Suggestions|Ideas to try|What you could add|Try adding)[\s:]*\n((?:[-*•\d.]\s*.*?(?:\n|$))+)',
    r'(?:\*\*)?(?:What you could add|Suggestions)[\s:]*(?:\*\*)?\n((?:[-*•\d.]\s*.*?(?:\n|$))+)',
    r'\n((?:[-*•]\s*.*?\n)+)',
]


def _strip_tool_summary(text: str) -> str:
    if TOOL_SUMMARY_MARKER in text:
        return text.split(TOOL_SUMMARY_MARKER, 1)[0]
    return text


def _extract_declared_files(content: str) -> List[Dict[str, str]]:
    """Extract filename-tagged code blocks, tolerating clipped responses."""
    all_files: List[Dict[str, str]] = []
    cleaned_content = _strip_tool_summary(content)
    file_starts = list(FILE_START_PATTERN.finditer(cleaned_content))

    for i, match in enumerate(file_starts):
        lang = match.group(1)
        filename = match.group(2).strip().strip('`')
        content_start = match.end()
        next_start = file_starts[i + 1].start() if i + 1 < len(file_starts) else len(cleaned_content)
        segment = cleaned_content[content_start:next_start]

        closing_match = re.search(r'\n```\s*(?:\n|$)', segment)
        file_content = segment[:closing_match.start()] if closing_match else segment

        if filename and file_content.strip():
            all_files.append({
                'filename': filename,
                'content': file_content.strip(),
                'language': lang,
            })

    for filename, lang, file_content in FILE_PREFIX_PATTERN.findall(cleaned_content):
        filename = filename.strip().strip('`')
        if filename and file_content.strip():
            all_files.append({
                'filename': filename,
                'content': file_content.strip(),
                'language': lang or 'text',
            })

    deduped: Dict[str, Dict[str, str]] = {}
    for file_info in all_files:
        deduped[file_info['filename']] = file_info

    return list(deduped.values())


def _extract_primary_code(content: str, language: str, declared_files: List[Dict[str, str]]) -> str:
    """Extract the primary code block for compatibility with single-file flows."""
    lang_identifiers = {
        'p5js': ['javascript', 'js', ''],
        'html': ['html', ''],
        'python': ['python', 'py', ''],
        'undecided': ['javascript', 'js', 'html', 'python', 'py', ''],
    }
    identifiers = lang_identifiers.get(language, [''])

    code_matches = []
    for ident in identifiers:
        if ident:
            pattern = rf'```{ident}\s*\n(?!.*index\.html|.*style\.css|.*main\.js|.*dice\.js)(.*?)\n```'
        else:
            pattern = r'```\s*\n(.*?)(?:\n)?```'
        matches = [match.strip() for match in re.findall(pattern, content, re.DOTALL) if match and match.strip()]
        if matches:
            code_matches = matches
            break

    if code_matches:
        return code_matches[0]

    if declared_files:
        file_map = {file_info['filename']: file_info['content'] for file_info in declared_files}
        primary_file = choose_primary_code_file(language, file_map)
        if primary_file and primary_file in file_map:
            return file_map[primary_file].strip()
        first_file = declared_files[0]
        return first_file['content'].strip()

    return ''


def _extract_explanation(content: str) -> str:
    """Get explanation text before the first code block or section heading."""
    cleaned_content = _strip_tool_summary(content)
    code_match = re.search(r'```', cleaned_content)
    heading_match = SECTION_HEADING_PATTERN.search(cleaned_content)

    cut_points = [match.start() for match in [code_match, heading_match] if match]
    if cut_points:
        return cleaned_content[:min(cut_points)].strip()
    return cleaned_content.strip()


def _extract_suggestions(content: str) -> List[str]:
    """Extract suggestion bullet lists from the tail of the response."""
    cleaned_content = _strip_tool_summary(content)
    last_fence_idx = cleaned_content.rfind('```')
    tail = cleaned_content[last_fence_idx + 3:] if last_fence_idx != -1 else cleaned_content

    for pattern in SUGGESTION_PATTERNS:
        match = re.search(pattern, tail, re.IGNORECASE | re.DOTALL)
        if not match:
            continue
        suggestions_text = match.group(1)
        suggestions = re.findall(r'[-*•\d.]\s*(.*?)(?=\n[-*•\d.]|\Z)', suggestions_text, re.DOTALL)
        cleaned = [s.strip() for s in suggestions if s.strip()]
        if cleaned:
            return cleaned

    return []


def parse_response(
    content: str,
    language: str = 'undecided',
    project_id: Optional[int] = None
) -> Dict:
    """
    Parse AI response to extract code, explanation, suggestions, and file declarations.

    Args:
        content: The raw AI response text
        language: 'p5js', 'html', 'python', or 'undecided' - affects which code blocks to look for
        project_id: Project ID for saving extracted files

    Returns:
        Dict with code, explanation, suggestions, created_files, primary_file
    """
    result = {
        'code': '',
        'explanation': '',
        'suggestions': [],
        'created_files': [],
        'primary_file': None,
    }

    print(f"_parse_response: content length {len(content)}, project_id={project_id}")

    declared_files = _extract_declared_files(content)
    file_map = {file_info['filename']: file_info['content'] for file_info in declared_files}
    result['primary_file'] = choose_primary_code_file(language, file_map) if file_map else None

    print(f"_parse_response: found {len(declared_files)} file declarations")

    if project_id and declared_files:
        file_tools = FileTools(project_id)
        for file_info in declared_files:
            try:
                tool_result = file_tools.write_file(file_info['filename'], file_info['content'])
                if tool_result.get('success'):
                    result['created_files'].append({
                        'filename': file_info['filename'],
                        'action': tool_result.get('action', 'created')
                    })
                    print(f"_parse_response: saved file {file_info['filename']}")
            except Exception as e:
                print(f"_parse_response: error saving file {file_info['filename']}: {e}")

    result['code'] = _extract_primary_code(content, language, declared_files)
    print(f"_parse_response: extracted code length {len(result['code'])}")

    result['explanation'] = _extract_explanation(content)
    print(f"_parse_response: explanation length {len(result['explanation'])}")

    result['suggestions'] = _extract_suggestions(content)

    return result
