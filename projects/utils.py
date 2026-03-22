"""
projects/utils.py - Shared project utilities
Club Kinawa Coding Lab
"""

import re
import sqlite3
from datetime import datetime

from projects.state import sync_current_code_cache


SUPPORTED_PROJECT_LANGUAGES = {'p5js', 'html', 'python', 'undecided'}
MAX_PROJECT_DESCRIPTION_LENGTH = 1000


LANGUAGE_LABELS = {
    'p5js': 'p5.js',
    'html': 'HTML/CSS/JS',
    'python': 'Python',
    'undecided': 'Starter project',
}


STARTER_CODE_TEMPLATES = {
    'p5js': (
        'sketch.js',
        """function setup() {
  createCanvas(480, 320);
  textAlign(CENTER, CENTER);
  textSize(20);
}

function draw() {
  background(15, 23, 42);

  fill(139, 92, 246);
  circle(mouseX, mouseY, 48);

  fill(248, 250, 252);
  text('Move the mouse to paint!', width / 2, 36);
  textSize(14);
  text('Try changing the colors, text, or shape size.', width / 2, height - 24);
}
""",
    ),
    'html': (
        'index.html',
        """<!DOCTYPE html>
<html lang=\"en\">
<head>
  <meta charset=\"UTF-8\" />
  <meta name=\"viewport\" content=\"width=device-width, initial-scale=1.0\" />
  <title>My first web page</title>
  <style>
    body {
      font-family: Arial, sans-serif;
      margin: 0;
      min-height: 100vh;
      display: grid;
      place-items: center;
      background: linear-gradient(135deg, #0f172a, #4c1d95);
      color: white;
    }

    .card {
      width: min(90vw, 420px);
      padding: 2rem;
      border-radius: 20px;
      background: rgba(15, 23, 42, 0.82);
      box-shadow: 0 20px 45px rgba(15, 23, 42, 0.35);
      text-align: center;
    }

    button {
      margin-top: 1rem;
      padding: 0.8rem 1.2rem;
      border: none;
      border-radius: 999px;
      font-size: 1rem;
      font-weight: 700;
      cursor: pointer;
      background: #f472b6;
      color: white;
    }
  </style>
</head>
<body>
  <main class=\"card\">
    <h1>Hello, web creator! 🌟</h1>
    <p>Press the button, then edit the words, colors, or layout to make this page yours.</p>
    <button onclick=\"changeMessage()\">Surprise me</button>
    <p id=\"message\">You built your first page.</p>
  </main>

  <script>
    function changeMessage() {
      const ideas = [
        'Try adding your favorite animal.',
        'What happens if you change the background?',
        'Can you add a second button?',
        'Make this page tell a joke!'
      ];
      const nextIdea = ideas[Math.floor(Math.random() * ideas.length)];
      document.getElementById('message').textContent = nextIdea;
    }
  </script>
</body>
</html>
""",
    ),
    'python': (
        'main.py',
        """print(\"Welcome to your first Python project! 🐍\")
print(\"Change the words below, then run it again.\")

hero_name = \"Pixel Explorer\"
mission = \"build something fun\"

print(f\"Hero: {hero_name}\")
print(f\"Mission: {mission}\")

for step in [\"Imagine it\", \"Code it\", \"Share it\"]:
    print(f\"- {step}\")
""",
    ),
    'undecided': (
        'sketch.js',
        """function setup() {
  createCanvas(480, 320);
  background(15, 23, 42);
}

function draw() {
  fill(139, 92, 246);
  circle(mouseX, mouseY, 48);
}
""",
    ),
}


FIRST_STEPS = {
    'p5js': [
        'Run the sketch and move your mouse.',
        'Change the colors or shape size.',
        'Add a new rule when the mouse is pressed.'
    ],
    'html': [
        'Open the preview and click the button.',
        'Change the heading and page colors.',
        'Add another section about your idea.'
    ],
    'python': [
        'Run the script once to see the output.',
        'Rename the hero and mission.',
        'Add one more print() line for your own idea.'
    ],
    'undecided': [
        'Try the starter and see what it does.',
        'Change one number or color.',
        'Ask the AI to help you turn it into your idea.'
    ],
}


def normalize_project_language(language: str) -> str:
    """Normalize project language values to the supported starter set."""
    normalized = (language or 'undecided').strip().lower()
    return normalized if normalized in SUPPORTED_PROJECT_LANGUAGES else 'undecided'


def language_label(language: str) -> str:
    """Return a display-friendly language label."""
    return LANGUAGE_LABELS.get(normalize_project_language(language), 'Starter project')


VALID_PROJECT_FILENAME_RE = re.compile(r'^[A-Za-z0-9][A-Za-z0-9._\-/ ]*[A-Za-z0-9]$')
SUSPICIOUS_FILENAME_TOKENS = (';', '(', ')', '{', '}', '=>', '<script', 'function ', '\n')


def normalize_project_filename(filename: str) -> str:
    return '/'.join(part for part in (filename or '').strip().replace('\\', '/').split('/') if part not in {'', '.'})


def is_valid_project_filename(filename: str) -> bool:
    normalized = normalize_project_filename(filename)
    if not normalized:
        return False
    if normalized.startswith('/') or '..' in normalized.split('/'):
        return False
    if any(token in normalized.lower() for token in SUSPICIOUS_FILENAME_TOKENS):
        return False
    if not VALID_PROJECT_FILENAME_RE.match(normalized):
        return False
    return all(part and part not in {'.', '..'} for part in normalized.split('/'))


def looks_suspicious_project_filename(filename: str) -> bool:
    normalized = normalize_project_filename(filename)
    return bool(normalized) and not is_valid_project_filename(normalized)


def starter_code_file(language: str):
    """Return starter filename/content for the chosen language."""
    return STARTER_CODE_TEMPLATES.get(normalize_project_language(language), STARTER_CODE_TEMPLATES['undecided'])


def starter_first_steps(language: str):
    """Return friendly first-step suggestions for the chosen language."""
    return FIRST_STEPS.get(normalize_project_language(language), FIRST_STEPS['undecided'])


def create_default_files(db, project_id: int, project_name: str, language: str = 'undecided', description: str = ''):
    """Create default planning docs plus a runnable starter file for a new project."""
    language = normalize_project_language(language)
    starter_filename, starter_content = starter_code_file(language)
    steps = starter_first_steps(language)
    project_blurb = description or 'Build the smallest fun version first, then level it up.'
    stack_label = language_label(language)
    created_files = []

    default_files = {
        'design.md': f"""# Design: {project_name}

## Idea

{project_blurb}

## Starter Path

- Language: {stack_label}
- First file to open: `{starter_filename}`
- First goal: Make one visible change, then test it.

## Core Features

- Feature 1
- Feature 2
- Feature 3

## Stretch Goals

- [ ] Stretch feature 1
- [ ] Stretch feature 2

## Open Questions

- What is the smallest version I can finish today?
- What would make this more fun to play or explore?
""",
        'architecture.md': f"""# Architecture: {project_name}

## Technology Stack

- Language: {stack_label}
- Target Platform: [Browser / Desktop / Mobile]

## File Structure

```
{project_name}/
├── {starter_filename}
├── design.md
├── architecture.md
├── todo.md
└── notes.md
```

## Key Components

1. **Starter file** - The first thing to run and edit
2. **Project docs** - Keep track of ideas, tasks, and decisions

## Notes

Start simple. Make one thing work before adding more parts.
""",
        'todo.md': f"""# Todo: {project_name}

## First Moves

- [ ] Open `{starter_filename}`
- [ ] {steps[0]}
- [ ] {steps[1]}
- [ ] {steps[2]}

## Current

- [ ] Initial setup
- [ ] Define core features

## Completed

_None yet_

## Ideas

- Add your own twist
- Ask the AI for one next step at a time
""",
        'notes.md': f"""# Notes: {project_name}

## Session Log

### {datetime.now().strftime('%Y-%m-%d')}

- Project created
- Starter file ready: `{starter_filename}`
- First plan: {steps[0]}

## Questions to Ask

- What should I build first?
- What one change should I try next?

## Decisions Made

- Starting with {stack_label}
""",
        starter_filename: starter_content,
    }

    for filename, content in default_files.items():
        try:
            db.execute(
                '''
                INSERT INTO project_files (project_id, filename, content)
                VALUES (?, ?, ?)
            ''',
                (project_id, filename, content),
            )
            created_files.append(filename)
        except sqlite3.IntegrityError as exc:
            # Allow idempotent reseeding, but don't hide unrelated database issues.
            if 'UNIQUE constraint failed' not in str(exc):
                raise

    sync_current_code_cache(db, project_id, language, fallback_current_code='', touch_project=False)
    return created_files
