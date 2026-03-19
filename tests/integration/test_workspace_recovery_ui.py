"""Regression tests for workspace recovery affordances."""

import pytest


@pytest.mark.integration
class TestWorkspaceRecoverySurface:
    """Risky workspace actions should expose a humane way back."""

    def test_workspace_template_includes_undoable_toast_controls(self, client):
        response = client.get('/lab/project/123')

        assert response.status_code == 200
        html = response.get_data(as_text=True)

        assert 'id="workspace-toast-message"' in html
        assert 'id="workspace-toast-actions"' in html
        assert 'id="workspace-toast-action"' in html
        assert 'id="workspace-toast-dismiss"' in html
        assert '/lab/static/css/workspace.css?v=41' in html
        assert '/lab/static/js/workspace.js?v=46' in html
        assert '/lab/static/js/workspace-versions.js?v=3' in html

    def test_workspace_script_supports_deleted_file_undo_toasts(self, client):
        response = client.get('/lab/static/js/workspace.js')

        assert response.status_code == 200
        js = response.get_data(as_text=True)

        assert 'async function restoreDeletedFile(deletedFile)' in js
        assert 'actionLabel: \'Undo\'' in js
        assert 'async function handleWorkspaceToastAction()' in js
        assert 'function initializeWorkspaceToast()' in js
        assert 'You can undo this right after deleting if you change your mind.' in js

    def test_versions_script_creates_hidden_recovery_points_before_restore(self, client):
        response = client.get('/lab/static/js/workspace-versions.js')

        assert response.status_code == 200
        js = response.get_data(as_text=True)

        assert "const RECOVERY_VERSION_PREFIX = '__ckcl_recovery__:';" in js
        assert 'function getVisibleWorkspaceVersions()' in js
        assert 'async function createRecoveryVersion(reason = \'Before risky workspace action\')' in js
        assert 'async function undoWorkspaceRecovery(versionId, label = \'your previous project state\')' in js
        assert "Couldn't create a safety net, so the restore was canceled." in js

    def test_workspace_styles_include_toast_action_layout(self, client):
        response = client.get('/lab/static/css/workspace.css')

        assert response.status_code == 200
        css = response.get_data(as_text=True)

        assert '.workspace-toast-actions' in css
        assert '.workspace-toast-action' in css
        assert '.workspace-toast-dismiss' in css
        assert '.workspace-toast-message' in css
