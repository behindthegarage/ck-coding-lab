# tests/integration/test_projects_onboarding_ui.py
"""Regression tests for first-project onboarding affordances on the projects page."""

import pytest


@pytest.mark.integration
class TestProjectsOnboardingSurface:
    """The projects page should expose clearer starter affordances."""

    def test_projects_template_includes_quick_start_copy_and_starter_preview(self, client):
        response = client.get('/lab/projects')

        assert response.status_code == 200
        html = response.get_data(as_text=True)

        assert 'Pick a starter, make one tiny change' in html
        assert 'data-template="p5js"' in html
        assert 'data-template="html"' in html
        assert 'data-template="python"' in html
        assert 'id="starter-preview"' in html
        assert 'Choose a starter, then change one thing right away' in html

    def test_projects_script_supports_empty_state_starters_preview_updates_and_retryable_load_errors(self, client):
        response = client.get('/lab/static/js/projects.js')

        assert response.status_code == 200
        js = response.get_data(as_text=True)

        assert 'const STARTER_PRESETS =' in js
        assert 'function renderEmptyState(container)' in js
        assert 'function renderProjectsError(container, message =' in js
        assert 'retry-projects-load' in js
        assert "We couldn't load your projects" in js
        assert 'function applyStarterPreset(presetKey, overwriteText = true)' in js
        assert 'function renderStarterPreview()' in js
        assert "openNewProjectModal('p5js')" in js
