# ai/prompts.py - System Prompts and Prompt Building
"""
System prompt loading and prompt construction for AI interactions.
"""

import os
from typing import Dict, Optional

from ai.config import LANGUAGE_CONTEXT, UNDECIDED_CONTEXT
from ai.workflow import workflow_prompt_block
from projects.state import choose_primary_code_file

MAX_CONTEXT_FILE_CHARS = 1600

RESPONSE_CONTRACT = """
## RESPONSE CONTRACT

Follow this contract every time you help with code:

- Read the current project state before making changes. If tools are available, use `list_files` and `read_file` when you need to inspect files.
- When tools are available and you need to change files, prefer the file tools to create or update them.
- If tools are not available, create or update files with fenced code blocks whose opening line is exactly `LANGUAGE filename.ext`.
- For multi-file work, be explicit about the entry file. For browser projects, that is usually `index.html`.
- Keep explanations outside code fences. Keep file contents inside code fences.
- Never write fake tool logs like `write_file: index.html -> created` in plain text.
- Never expose internal parser or transcript markers such as `tool_calls_section_begin`, `tool_call_begin`, `tool_result_begin`, `tool_use`, or raw tool payloads.
- If only one primary code file is changing, a normal single code block is okay. If multiple files are involved, use one filename-tagged block per file.
- Replace starter-template wording with project-specific details from the actual conversation. Do not leave placeholder bullets like `Feature 1` or `[Browser / Desktop / Mobile]` once you know the real answer.

Keep the conversation staged and readable:
1. If you still need context, ask only a few high-leverage questions and stop there.
2. After the user answers, give a short synthesis of the direction you are taking.
3. When you update planning docs, include an explicit `## Doc updates` section summarizing what changed in `design.md`, `architecture.md`, and `todo.md` in plain language.
4. After file work, use a short paragraph for what changed, optional `## Why this approach`, optional `## What changed`, optional `## Questions for you`, optional `## Start here`, and optional `## Next ideas`.
5. Ask at most one focused follow-up question after a build, and only if the answer meaningfully changes the next step.
""".strip()


def load_agent_prompt() -> str:
    """Load the agent.md system prompt."""
    prompt_path = os.path.join(
        os.path.dirname(os.path.dirname(__file__)),
        'prompts',
        'agent.md'
    )
    try:
        with open(prompt_path, 'r') as f:
            return f.read()
    except FileNotFoundError:
        print(f"Warning: agent.md not found at {prompt_path}, using default")
        return "You are Hari, a helpful coding assistant."


def _build_project_context(language: str, project_files: Optional[Dict[str, str]] = None) -> str:
    """Build project file context with inventory plus truncated contents."""
    if not project_files:
        return ""

    primary_file = choose_primary_code_file(language, project_files)
    filenames = sorted(project_files.keys())

    lines = ["", "", "## CURRENT PROJECT STATE", ""]
    lines.append("Files in the project:")
    for filename in filenames:
        lines.append(f"- {filename}")

    if primary_file:
        lines.append("")
        lines.append(f"Current primary / entry file: {primary_file}")

    lines.append("")
    lines.append("File contents:")

    for filename in filenames:
        content = project_files.get(filename, "") or ""
        display_content = content
        if len(display_content) > MAX_CONTEXT_FILE_CHARS:
            display_content = display_content[:MAX_CONTEXT_FILE_CHARS] + "\n... [truncated]"
        lines.append("")
        lines.append(f"### {filename}")
        lines.append("```")
        lines.append(display_content)
        lines.append("```")

    return "\n".join(lines)


def build_system_prompt(
    base_prompt: str,
    language: str,
    project_files: Optional[Dict[str, str]] = None,
    tools_enabled: bool = False,
    workflow_context: Optional[Dict] = None,
) -> str:
    """
    Build the full system prompt for a given language.

    Args:
        base_prompt: The base system prompt from agent.md
        language: Which language mode ('p5js', 'html', 'python', or 'undecided')
        project_files: Optional dict of filename -> content for context
        tools_enabled: Whether file tools are available for this request
        workflow_context: Optional per-turn kickoff/co-design guidance

    Returns:
        The complete system prompt string
    """
    parts = [base_prompt.strip()]

    if language == 'undecided' or not language:
        parts.append(UNDECIDED_CONTEXT.strip())
    else:
        lang_context = LANGUAGE_CONTEXT.get(language, LANGUAGE_CONTEXT['p5js'])
        parts.append(lang_context.strip())

    parts.append(RESPONSE_CONTRACT)

    workflow_block = workflow_prompt_block(workflow_context)
    if workflow_block:
        parts.append(workflow_block)

    if tools_enabled:
        parts.append("Tools are available in this turn. Use them for file reads and writes when that makes the result clearer and more reliable.")
    else:
        parts.append("Tools are not available in this turn. If you need multiple files, output one filename-tagged code block per file.")

    project_context = _build_project_context(language, project_files)
    if project_context:
        parts.append(project_context.strip())

    return "\n\n".join(part for part in parts if part)
