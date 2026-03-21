"""Regression tests for chat-to-file awareness affordances in the workspace."""

import pytest


@pytest.mark.integration
class TestChatFileAwarenessSurface:
    """The workspace should make AI-touched files easier to spot and open."""

    def test_workspace_script_includes_open_file_actions_from_assistant_messages(self, client):
        response = client.get('/lab/static/js/workspace.js')

        assert response.status_code == 200
        js = response.get_data(as_text=True)

        assert 'async function openWorkspaceFileByName(filename)' in js
        assert 'setLatestAssistantChanges(changedFiles);' in js
        assert "const fileButton = event.target.closest('[data-open-file]');" in js
        assert 'assistant-file-chip' in js
        assert 'assistant-review-card' in js
        assert 'assistant-questions-card' in js
        assert 'decisionNotes: data.response.decision_notes || []' in js
        assert 'followUpQuestions: data.response.follow_up_questions || []' in js
        assert 'changeReview: data.response.change_review || []' in js
        assert 'file-recent-badge' in js

    def test_workspace_styles_include_changed_file_chips_review_cards_and_recent_file_badges(self, client):
        response = client.get('/lab/static/css/workspace.css')

        assert response.status_code == 200
        css = response.get_data(as_text=True)

        assert '.assistant-file-chip' in css
        assert '.assistant-file-link' in css
        assert '.assistant-file-chip-meta' in css
        assert '.assistant-context-card' in css
        assert '.assistant-questions-card' in css
        assert '.assistant-review-card' in css
        assert '.assistant-review-diff' in css
        assert '.file-recent-badge' in css

    def test_workspace_template_references_current_workspace_assets(self, client):
        response = client.get('/lab/project/123')

        assert response.status_code == 200
        html = response.get_data(as_text=True)

        assert '/lab/static/css/workspace.css?v=43' in html
        assert '/lab/static/js/workspace.js?v=55' in html
