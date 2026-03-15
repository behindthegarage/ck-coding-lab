"""
projects/utils.py - Shared project utilities
Club Kinawa Coding Lab
"""

from datetime import datetime


def create_default_files(db, project_id: int, project_name: str):
    """Create default files for a new project."""
    default_files = {
        'design.md': f"""# Design: {project_name}

## Elevator Pitch

[One sentence describing what this project does]

## Core Features

- Feature 1
- Feature 2
- Feature 3

## Stretch Goals

- [ ] Stretch feature 1
- [ ] Stretch feature 2

## Open Questions

- What technology stack should we use?
- What's the simplest version we can build first?
""",
        'architecture.md': f"""# Architecture: {project_name}

## Technology Stack

- Language: [p5.js / HTML/CSS/JS / Python]
- Key Libraries: 
- Target Platform: [Browser / Desktop / Mobile]

## File Structure

```
{project_name}/
├── main.js (or main.py, index.html)
└── [other files]
```

## Key Components

1. **Component 1** - Description
2. **Component 2** - Description

## Dependencies

- None yet

## Notes

[Any technical decisions or constraints]
""",
        'todo.md': f"""# Todo: {project_name}

## Current

- [ ] Initial setup
- [ ] Define core features

## Completed

_None yet_

## Blocked

_None yet_

## Ideas

- Future improvement 1
- Future improvement 2
""",
        'notes.md': f"""# Notes: {project_name}

## Session Log

### {datetime.now().strftime('%Y-%m-%d')}

- Project created
- Initial ideas:

## Research

[Links, references, things to remember]

## Questions to Ask

- 

## Decisions Made

- 
"""
    }
    
    for filename, content in default_files.items():
        try:
            db.execute('''
                INSERT INTO project_files (project_id, filename, content)
                VALUES (?, ?, ?)
            ''', (project_id, filename, content))
        except Exception as e:
            # File might already exist, skip
            pass
