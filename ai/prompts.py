# ai/prompts.py - System Prompts and Prompt Building
"""
System prompt loading and prompt construction for AI interactions.
"""

import os
from typing import Dict, Optional

from ai.config import LANGUAGE_CONTEXT, UNDECIDED_CONTEXT


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


def build_system_prompt(
    base_prompt: str,
    language: str,
    project_files: Optional[Dict[str, str]] = None
) -> str:
    """
    Build the full system prompt for a given language.
    
    Args:
        base_prompt: The base system prompt from agent.md
        language: Which language mode ('p5js', 'html', 'python', or 'undecided')
        project_files: Optional dict of filename -> content for context
        
    Returns:
        The complete system prompt string
    """
    # Add project context if available
    if project_files:
        context_section = "\n\n## CURRENT PROJECT STATE\n\n"
        for filename, content in sorted(project_files.items()):
            # Truncate very long files
            display_content = content if len(content) < 2000 else content[:2000] + "\n... [truncated]"
            context_section += f"### {filename}\n```\n{display_content}\n```\n\n"
        base_prompt = base_prompt + context_section
    
    if language == 'undecided' or not language:
        return f"{base_prompt}\n\n{UNDECIDED_CONTEXT}"
    
    lang_context = LANGUAGE_CONTEXT.get(language, LANGUAGE_CONTEXT["p5js"])
    return f"{base_prompt}\n\n{lang_context}"
