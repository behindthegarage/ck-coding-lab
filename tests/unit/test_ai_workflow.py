"""Unit tests for kickoff/co-design workflow analysis."""

import pytest

from ai.workflow import analyze_workflow_context, workflow_prompt_block
from projects.utils import starter_code_file


@pytest.mark.unit
class TestWorkflowAnalysis:
    def _starter_project_files(self, language='html'):
        starter_filename, starter_content = starter_code_file(language)
        return {
            'design.md': """# Design: Space Catcher

## Idea

Build the smallest fun version first, then level it up.

## Starter Path

- Language: HTML/CSS/JS
- First file to open: `index.html`
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
            'architecture.md': """# Architecture: Space Catcher

## Technology Stack

- Language: HTML/CSS/JS
- Target Platform: [Browser / Desktop / Mobile]

## File Structure

```
Space Catcher/
├── index.html
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
            'todo.md': """# Todo: Space Catcher

## First Moves

- [ ] Open `index.html`
- [ ] Open the preview and click the button.
- [ ] Change the heading and page colors.
- [ ] Add another section about your idea.

## Current

- [ ] Initial setup
- [ ] Define core features

## Completed

_None yet_

## Ideas

- Add your own twist
- Ask the AI for one next step at a time
""",
            starter_filename: starter_content,
        }

    def test_guided_kickoff_asks_small_question_set_before_scaffolding(self):
        workflow = analyze_workflow_context(
            message='I want to make a game where a fox catches falling stars.',
            conversation_history=[],
            project_files=self._starter_project_files('html'),
            language='html',
        )

        assert workflow['phase'] == 'guided-kickoff'
        assert workflow['mode'] == 'guided-kickoff'
        assert workflow['question_budget'] == 3
        assert workflow['should_ask_questions_now'] is True
        assert workflow['should_synthesize_docs_now'] is False
        assert workflow['should_scaffold_now'] is False

    def test_fast_path_skips_questions_and_moves_into_docs_and_scaffold(self):
        workflow = analyze_workflow_context(
            message='Move fast and use your judgment. Just build a pizza shop website.',
            conversation_history=[],
            project_files=self._starter_project_files('html'),
            language='html',
        )

        assert workflow['mode'] == 'fast-path'
        assert workflow['question_budget'] == 0
        assert workflow['should_ask_questions_now'] is False
        assert workflow['should_synthesize_docs_now'] is True
        assert workflow['should_scaffold_now'] is True

    def test_prototype_mode_allows_one_question_but_keeps_momentum(self):
        workflow = analyze_workflow_context(
            message='Make a quick prototype for a slime jumping game.',
            conversation_history=[],
            project_files=self._starter_project_files('p5js'),
            language='p5js',
        )

        assert workflow['mode'] == 'prototype-mode'
        assert workflow['question_budget'] == 1
        assert workflow['should_scaffold_now'] is True

    def test_answer_after_recent_question_round_triggers_doc_synthesis(self):
        workflow = analyze_workflow_context(
            message='Single player, spooky forest theme, and two short levels.',
            conversation_history=[
                {'role': 'user', 'content': 'Help me make a maze game.'},
                {'role': 'assistant', 'content': 'A couple questions for you:\n- Should it be spooky or funny?\n- One level or several?'}
            ],
            project_files=self._starter_project_files('html'),
            language='html',
        )

        assert workflow['phase'] == 'guided-kickoff'
        assert workflow['assistant_recently_asked_questions'] is True
        assert workflow['should_ask_questions_now'] is False
        assert workflow['should_synthesize_docs_now'] is True
        assert workflow['should_scaffold_now'] is True

    def test_iterative_phase_detects_pivot_and_keeps_docs_in_sync(self):
        project_files = {
            'design.md': '# Design\n\n## Core Features\n- Sword combat\n- Enemy waves\n',
            'architecture.md': '# Architecture\n\n## Technology Stack\n- Language: HTML/CSS/JS\n',
            'todo.md': '# Todo\n\n## Current\n- [ ] Polish combat\n',
            'index.html': '<!DOCTYPE html><html><body><script src="main.js"></script></body></html>',
            'main.js': 'console.log("battle prototype");',
        }

        workflow = analyze_workflow_context(
            message='Actually, turn it into a potion shop simulator instead of a battle game.',
            conversation_history=[
                {'role': 'user', 'content': 'Make a battle game.'},
                {'role': 'assistant', 'content': 'I built the combat loop.'}
            ],
            project_files=project_files,
            language='html',
        )

        assert workflow['phase'] == 'iterative-co-design'
        assert workflow['pivot_detected'] is True
        assert workflow['should_synthesize_docs_now'] is True
        assert workflow['should_keep_docs_in_sync'] is True
        assert 'notes.md' in workflow['doc_targets']

    def test_workflow_prompt_block_mentions_question_budget_and_docs(self):
        workflow = analyze_workflow_context(
            message='Move fast and build a weather dashboard.',
            conversation_history=[],
            project_files=self._starter_project_files('html'),
            language='html',
        )

        prompt_block = workflow_prompt_block(workflow)

        assert 'WORKFLOW MODE FOR THIS TURN' in prompt_block
        assert 'Question budget: 0' in prompt_block
        assert 'Docs to update when decisions change: design.md, architecture.md, todo.md' in prompt_block
        assert 'Make sensible assumptions' in prompt_block
