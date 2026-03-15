# ai/parser.py - Response Parsing for AI Output
"""
Parse AI responses to extract code, explanations, suggestions, and file declarations.
"""

import re
from typing import Dict, List, Optional

from ai.tools import FileTools


def parse_response(
    content: str,
    language: str = "undecided",
    project_id: Optional[int] = None
) -> Dict:
    """
    Parse AI response to extract code, explanation, suggestions, and file declarations.
    
    Args:
        content: The raw AI response text
        language: 'p5js', 'html', 'python', or 'undecided' - affects which code blocks to look for
        project_id: Project ID for saving extracted files
        
    Returns:
        Dict with code, explanation, suggestions, created_files
    """
    result = {
        "code": "",
        "explanation": "",
        "suggestions": [],
        "created_files": []
    }
    
    print(f"_parse_response: content length {len(content)}, project_id={project_id}")
    
    # STEP 1: Extract file declarations from code blocks
    # Pattern: ```language filename or ```language [filename]
    # Examples: ```html index.html, ```css style.css, ```js main.js
    file_pattern = r'```(html|css|js|javascript|python|py)\s*\[?([^\]\n]+)\]?\s*\n(.*?)```'
    file_matches = re.findall(file_pattern, content, re.DOTALL)
    
    # Also look for "File: filename" pattern before code blocks
    file_prefix_pattern = r'(?:File|file):\s*([\w.\-/]+)\s*\n```(html|css|js|javascript|python|py)?\s*\n(.*?)```'
    prefix_matches = re.findall(file_prefix_pattern, content, re.DOTALL)
    
    all_files = []
    
    # Process filename-in-codeblock pattern
    for lang, filename, file_content in file_matches:
        filename = filename.strip()
        if filename and file_content:
            all_files.append({
                'filename': filename,
                'content': file_content.strip(),
                'language': lang
            })
    
    # Process "File: filename" pattern
    for filename, lang, file_content in prefix_matches:
        filename = filename.strip()
        if filename and file_content:
            all_files.append({
                'filename': filename,
                'content': file_content.strip(),
                'language': lang or 'text'
            })
    
    print(f"_parse_response: found {len(all_files)} file declarations")
    
    # Save files to database if project_id is provided
    if project_id and all_files:
        file_tools = FileTools(project_id)
        for file_info in all_files:
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
    
    # STEP 2: Extract main code block for backward compatibility
    # Map language to possible code block identifiers
    lang_identifiers = {
        "p5js": ["javascript", "js", ""],
        "html": ["html", ""],
        "python": ["python", "py", ""],
        "undecided": ["javascript", "js", "html", "python", "py", ""]
    }
    identifiers = lang_identifiers.get(language, [""])
    
    # Build regex patterns for each identifier (without filename)
    code_patterns = []
    for ident in identifiers:
        if ident:
            # Pattern without filename - just language tag
            code_patterns.append(rf'```{ident}\s*\n(?!.*index\.html|.*style\.css|.*main\.js|.*dice\.js)(.*?)\n```')
        else:
            code_patterns.append(r'```\s*\n(.*?)(?:\n)?```')
    
    code_matches = []
    for pattern in code_patterns:
        matches = re.findall(pattern, content, re.DOTALL)
        if matches:
            code_matches = matches
            break
    
    print(f"_parse_response: found {len(code_matches)} code blocks for main code")
    
    if code_matches:
        result["code"] = code_matches[0].strip()
        print(f"_parse_response: extracted code length {len(result['code'])}")
    
    # STEP 3: Get explanation - text before first code block
    parts = re.split(r'```(?:\w+)?(?:\s*\[?[^\]]*\]?)?\s*\n?', content, maxsplit=1, flags=re.DOTALL)
    if parts:
        result["explanation"] = parts[0].strip()
        print(f"_parse_response: explanation length {len(result['explanation'])}")
    
    # STEP 4: Extract suggestions from text after code blocks
    if len(parts) > 1:
        after_code_parts = content.split('```')
        if len(after_code_parts) >= 3:
            after_code = ''.join(after_code_parts[2:])
            
            # Look for suggestions - various patterns
            suggestion_patterns = [
                r'(?:What you could add|Suggestions|Next steps|Try adding|Ideas to try)[\s:]*\n((?:[-*•\d.]\s*.*?\n?)+)',
                r'(?:\*\*)?(?:What you could add|Suggestions)[\s:]*(?:\*\*)?\n((?:[-*•\d.]\s*.*?\n?)+)',
                r'\n((?:[-*•]\s*.*?\n)+)',  # Any bullet list
            ]
            for pattern in suggestion_patterns:
                match = re.search(pattern, after_code, re.IGNORECASE | re.DOTALL)
                if match:
                    suggestions_text = match.group(1)
                    suggestions = re.findall(r'[-*•\d.]\s*(.*?)(?=\n[-*•\d.]|\Z)', suggestions_text, re.DOTALL)
                    result["suggestions"] = [s.strip() for s in suggestions if s.strip()]
                    break
    
    return result
