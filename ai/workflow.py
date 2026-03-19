"""Workflow analysis for guided kickoff and iterative co-design."""

from __future__ import annotations

import posixpath
from typing import Dict, List, Optional

from projects.state import choose_primary_code_file, is_code_file
from projects.utils import starter_code_file


FAST_PATH_HINTS = (
    'move fast',
    'use your judgment',
    'use your judgement',
    'just build it',
    'just make it',
    'skip the questions',
    'skip questions',
    'no questions',
    'don\'t ask questions',
    'dont ask questions',
    'make reasonable assumptions',
    'run with it',
    'go ahead and build',
)

PROTOTYPE_HINTS = (
    'prototype',
    'rough version',
    'quick version',
    'proof of concept',
    'proof-of-concept',
    'poc',
    'mockup',
    'mock-up',
    'experiment',
    'spike',
)

PIVOT_HINTS = (
    'actually',
    'instead',
    'change direction',
    'switch to',
    'turn it into',
    'pivot',
    'rather than',
)

GENERIC_DOC_MARKERS = {
    'design.md': (
        '## starter path',
        'feature 1',
        'feature 2',
        'feature 3',
        'stretch feature 1',
        'stretch feature 2',
        'what is the smallest version i can finish today?',
    ),
    'architecture.md': (
        '[browser / desktop / mobile]',
        '**starter file** - the first thing to run and edit',
        '**project docs** - keep track of ideas, tasks, and decisions',
        'start simple. make one thing work before adding more parts.',
    ),
    'todo.md': (
        '## first moves',
        '## current',
        '- [ ] initial setup',
        '- [ ] define core features',
        '- add your own twist',
    ),
    'notes.md': (
        '## questions to ask',
        '- project created',
        '- starter file ready',
        '## decisions made',
    ),
}


MODE_SUMMARIES = {
    'guided-kickoff': 'Ask a few high-leverage questions first, then synthesize docs before scaffolding.',
    'fast-path': 'Make sensible assumptions, keep docs lean, and build momentum quickly.',
    'prototype-mode': 'Bias toward the smallest playful prototype and avoid over-planning.',
    'iterative-co-design': 'Keep building collaboratively, explain decisions, and ask one focused follow-up only when it unlocks the next step.',
}


def _normalize_text(text: Optional[str]) -> str:
    return ' '.join((text or '').strip().lower().split())


def _contains_any(text: str, patterns) -> bool:
    return any(pattern in text for pattern in patterns)


def _is_generic_doc(filename: str, content: str) -> bool:
    basename = posixpath.basename(filename or '').lower()
    markers = GENERIC_DOC_MARKERS.get(basename)
    if not markers:
        return False

    normalized = _normalize_text(content)
    hits = sum(1 for marker in markers if marker in normalized)
    return hits >= 2


def _count_generic_docs(project_files: Optional[Dict[str, str]]) -> int:
    files = project_files or {}
    return sum(1 for filename, content in files.items() if _is_generic_doc(filename, content or ''))


def _count_custom_docs(project_files: Optional[Dict[str, str]]) -> int:
    files = project_files or {}
    count = 0
    for filename, content in files.items():
        basename = posixpath.basename(filename or '').lower()
        if basename not in GENERIC_DOC_MARKERS:
            continue
        text = (content or '').strip()
        if text and not _is_generic_doc(filename, text):
            count += 1
    return count


def _normalize_code(text: Optional[str]) -> str:
    return '\n'.join((text or '').strip().splitlines()).strip()


def _has_meaningful_code(project_files: Optional[Dict[str, str]], language: str, current_code: str = '') -> bool:
    files = project_files or {}
    code_files = {
        filename: content
        for filename, content in files.items()
        if is_code_file(filename) and (content or '').strip()
    }

    if not code_files:
        return bool((current_code or '').strip())

    if len(code_files) > 1:
        return True

    filename, content = next(iter(code_files.items()))
    starter_filename, starter_content = starter_code_file(language)
    if posixpath.basename(filename) != posixpath.basename(starter_filename):
        return True

    return _normalize_code(content) != _normalize_code(starter_content)


def _assistant_recently_asked_questions(conversation_history: Optional[List[Dict]]) -> bool:
    history = conversation_history or []
    recent_assistant_messages = [
        (entry.get('content') or '')
        for entry in history[-4:]
        if entry.get('role') == 'assistant'
    ]
    return any('?' in message or 'questions for you' in _normalize_text(message) for message in recent_assistant_messages)


def _conversation_turn_count(conversation_history: Optional[List[Dict]]) -> int:
    return len([entry for entry in (conversation_history or []) if entry.get('role') in {'user', 'assistant'}])


def analyze_workflow_context(
    message: str,
    conversation_history: Optional[List[Dict]] = None,
    project_files: Optional[Dict[str, str]] = None,
    language: str = 'undecided',
    current_code: str = '',
) -> Dict:
    """Infer how the assistant should handle kickoff vs iterative collaboration."""
    normalized_message = _normalize_text(message)
    turn_count = _conversation_turn_count(conversation_history)
    generic_doc_count = _count_generic_docs(project_files)
    custom_doc_count = _count_custom_docs(project_files)
    has_meaningful_code = _has_meaningful_code(project_files, language or 'undecided', current_code=current_code)
    assistant_recently_asked = _assistant_recently_asked_questions(conversation_history)

    fast_path_requested = _contains_any(normalized_message, FAST_PATH_HINTS)
    prototype_requested = _contains_any(normalized_message, PROTOTYPE_HINTS)
    pivot_detected = _contains_any(normalized_message, PIVOT_HINTS)

    project_is_fresh = (
        not has_meaningful_code
        and turn_count <= 4
        and (generic_doc_count >= 2 or (generic_doc_count == 0 and custom_doc_count == 0))
    )

    phase = 'guided-kickoff' if project_is_fresh else 'iterative-co-design'

    if prototype_requested:
        mode = 'prototype-mode'
    elif fast_path_requested:
        mode = 'fast-path'
    elif phase == 'guided-kickoff':
        mode = 'guided-kickoff'
    else:
        mode = 'iterative-co-design'

    if mode == 'fast-path':
        question_budget = 0
    elif mode == 'prototype-mode':
        question_budget = 1
    elif phase == 'guided-kickoff':
        question_budget = 0 if assistant_recently_asked else 3
    else:
        question_budget = 0 if fast_path_requested else 1

    should_ask_questions_now = (
        phase == 'guided-kickoff'
        and mode == 'guided-kickoff'
        and question_budget > 0
        and not assistant_recently_asked
    )

    should_synthesize_docs_now = (
        pivot_detected
        or (phase == 'guided-kickoff' and not should_ask_questions_now)
        or (mode in {'fast-path', 'prototype-mode'} and generic_doc_count >= 1)
    )

    should_scaffold_now = not should_ask_questions_now and (
        phase == 'guided-kickoff'
        or mode in {'fast-path', 'prototype-mode'}
        or has_meaningful_code
    )

    doc_targets = ['design.md', 'architecture.md', 'todo.md']
    if pivot_detected or assistant_recently_asked:
        doc_targets.append('notes.md')

    project_maturity = 'starter' if project_is_fresh else 'active'
    if has_meaningful_code and custom_doc_count >= 2:
        project_maturity = 'co-design'

    return {
        'phase': phase,
        'mode': mode,
        'mode_summary': MODE_SUMMARIES[mode],
        'project_maturity': project_maturity,
        'question_budget': question_budget,
        'should_ask_questions_now': should_ask_questions_now,
        'should_synthesize_docs_now': should_synthesize_docs_now,
        'should_scaffold_now': should_scaffold_now,
        'should_keep_docs_in_sync': bool(should_synthesize_docs_now or phase != 'guided-kickoff'),
        'assistant_recently_asked_questions': assistant_recently_asked,
        'fast_path_requested': fast_path_requested,
        'prototype_requested': prototype_requested,
        'pivot_detected': pivot_detected,
        'has_meaningful_code': has_meaningful_code,
        'generic_doc_count': generic_doc_count,
        'custom_doc_count': custom_doc_count,
        'doc_targets': doc_targets,
        'primary_file': choose_primary_code_file(language, project_files or {}),
    }


def workflow_prompt_block(workflow: Optional[Dict]) -> str:
    """Format workflow guidance for the system prompt."""
    if not workflow:
        return ''

    doc_targets = ', '.join(workflow.get('doc_targets') or ['design.md', 'architecture.md', 'todo.md'])
    ask_now = 'yes' if workflow.get('should_ask_questions_now') else 'no'
    synthesize_now = 'yes' if workflow.get('should_synthesize_docs_now') else 'no'
    scaffold_now = 'yes' if workflow.get('should_scaffold_now') else 'no'
    keep_docs_synced = 'yes' if workflow.get('should_keep_docs_in_sync') else 'no'

    lines = [
        '## WORKFLOW MODE FOR THIS TURN',
        f"- Phase: {workflow.get('phase', 'iterative-co-design')}",
        f"- Mode: {workflow.get('mode', 'iterative-co-design')}",
        f"- Project maturity: {workflow.get('project_maturity', 'active')}",
        f"- Question budget: {workflow.get('question_budget', 1)}",
        f"- Ask clarifying questions right now: {ask_now}",
        f"- Synthesize docs right now: {synthesize_now}",
        f"- Scaffold or keep building right now: {scaffold_now}",
        f"- Keep docs in sync with direction changes: {keep_docs_synced}",
        f"- Docs to update when decisions change: {doc_targets}",
        '',
        workflow.get('mode_summary') or MODE_SUMMARIES.get(workflow.get('mode', ''), ''),
        '',
        'Behavior rules for this turn:',
        '- If you need clarification, ask only the highest-leverage questions and stop there.',
        '- If you already have enough context, rewrite `design.md`, `architecture.md`, and `todo.md` with project-specific decisions before you scaffold or expand code.',
        '- When you do build, explain what changed and why in plain kid-friendly language.',
        '- Ask at most one focused follow-up question after a build, and only if the answer will change the next step.',
        '- Support fast requests like "move fast" or "use your judgment" by making reasonable assumptions instead of stalling.',
    ]

    return '\n'.join(line for line in lines if line is not None).strip()
