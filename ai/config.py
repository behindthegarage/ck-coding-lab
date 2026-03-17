# ai/config.py - API Configuration and Constants
"""
Configuration for AI Client module.
API keys, endpoints, model settings, and constants.
"""

import os

# API Configuration
KIMI_BASE_URL = "https://api.kimi.com/coding"
KIMI_MODEL = "k2p5"  # Kimi K2.5 model ID
# 4096 was clipping larger HTML/JS game generations mid-file, which meant
# filename-tagged code blocks never closed and nothing got persisted to
# project_files. Give the model more room for full multi-hundred-line outputs.
DEFAULT_MAX_TOKENS = 8192
DEFAULT_TEMPERATURE = 0.7

# Language-specific context appended to agent.md
LANGUAGE_CONTEXT = {
    "p5js": """
## CURRENT PROJECT: P5.JS

You are helping with a p5.js project (JavaScript creative coding library).

**p5.js specifics:**
- Use `setup()` and `draw()` functions
- `createCanvas(width, height)` in setup
- Use p5.js key constants: UP_ARROW, DOWN_ARROW, LEFT_ARROW, RIGHT_ARROW (not UP, DOWN, LEFT, RIGHT)
- Available: all p5.js functions (circle, rect, fill, background, etc.)

**Output format:**
Generate p5.js code in a markdown block. Brief explanation before, suggestions after.
""",
    "html": """
## CURRENT PROJECT: HTML/CSS/JS

You are helping with an HTML project (web page or web game).

**HTML specifics:**
- Generate complete, valid HTML documents
- Include CSS in <style> tags and JS in <script> tags
- Or use external files if the project has multiple components

**Output format:**
Generate HTML in a markdown block. Brief explanation before, suggestions after.
""",
    "python": """
## CURRENT PROJECT: PYTHON

You are helping with a Python project.

**Python specifics:**
- Write clean, readable Python code
- Use functions and classes appropriately
- Include if __name__ == "__main__": block for runnable scripts
- Use type hints where they add clarity (optional but helpful)

**Output format:**
Generate Python code in a markdown block. Brief explanation before, suggestions after.
"""
}

UNDECIDED_CONTEXT = """
## CURRENT PROJECT: NOT YET DECIDED

The user hasn't chosen a language yet. This is the beginning of the project.

**Your job:** Help them decide on the best technology stack for their idea.

**Questions to ask:**
- What kind of project is this? (Game, website, tool, animation?)
- Where should it run? (Browser, their computer, phone?)
- Do they need to share it with others easily?
- Is it visual or text-based?

**Options to present:**
- **p5.js** — Games, animations, visual art. Runs in browser. Easy to share.
- **HTML/CSS/JS** — Websites, web apps, interactive pages. Runs in browser. Most flexible.
- **Python** — Scripts, data processing, text-based games. Runs on their computer. Great for learning programming concepts.

Once they choose (or you agree on a direction), start building with that choice.
"""

# Language to code block identifier mapping
CODE_LANG_MAP = {
    "p5js": "javascript",
    "html": "html",
    "python": "python"
}

# Language identifiers for code block parsing
LANG_IDENTIFIERS = {
    "p5js": ["javascript", "js", ""],
    "html": ["html", ""],
    "python": ["python", "py", ""],
    "undecided": ["javascript", "js", "html", "python", "py", ""]
}


def get_api_key() -> str:
    """Get Kimi API key from environment."""
    api_key = os.environ.get('KIMI_API_KEY')
    if not api_key:
        raise ValueError("KIMI_API_KEY environment variable is required")
    return api_key
