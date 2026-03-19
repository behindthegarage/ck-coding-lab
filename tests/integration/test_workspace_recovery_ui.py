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
        assert '/lab/static/js/workspace.js?v=49' in html
        assert '/lab/static/js/workspace-versions.js?v=4' in html

    def test_workspace_script_supports_deleted_file_undo_toasts(self, client):
        response = client.get('/lab/static/js/workspace.js')

        assert response.status_code == 200
        js = response.get_data(as_text=True)

        assert 'async function restoreDeletedFile(deletedFile)' in js
        assert 'actionLabel: \'Undo\'' in js
        assert 'async function handleWorkspaceToastAction()' in js
        assert 'function initializeWorkspaceToast()' in js
        assert 'You can undo this right after deleting if you change your mind.' in js

    def test_workspace_script_handles_network_errors_during_file_create(self, client):
        response = client.get('/lab/static/js/workspace.js')

        assert response.status_code == 200
        js = response.get_data(as_text=True)

        assert 'async function createNewFile()' in js
        assert 'let data;' in js
        assert 'try {' in js
        assert 'data = await apiRequest(`/projects/${projectId}/files`,' in js
        assert '} catch (error) {' in js
        assert "error.message || 'Failed to create file. Please try again.'" in js
        assert 'try {' in js and 'await viewFile(data.file.id, data.file.filename);' in js

    def test_workspace_script_ignores_stale_file_loads_before_updating_modal_state(self, client):
        response = client.get('/lab/static/js/workspace.js')

        assert response.status_code == 200
        js = response.get_data(as_text=True)

        assert 'let currentFileLoadToken = 0;' in js
        assert 'function isStaleFileLoadRequest(loadToken, fileId)' in js
        assert 'const loadToken = ++currentFileLoadToken;' in js
        assert 'if (isStaleFileLoadRequest(loadToken, fileId)) {' in js
        assert "console.error('Error loading file:'" in js
        assert 'currentFileLoadToken += 1;' in js

    def test_workspace_script_warns_before_reload_and_logout_when_file_edits_are_unsaved(self, client):
        response = client.get('/lab/static/js/workspace.js')

        assert response.status_code == 200
        js = response.get_data(as_text=True)

        assert 'function getUnsavedWorkspaceChangesMessage()' in js
        assert 'function hasUnsavedWorkspaceChanges()' in js
        assert 'function handleWorkspaceBeforeUnload(event)' in js
        assert "window.addEventListener('beforeunload', handleWorkspaceBeforeUnload);" in js
        assert "title: 'Log out and discard unsaved changes'" in js
        assert "confirmLabel: 'Log out anyway'" in js
        assert 'You have unsaved changes in ${filename}. Leave this page and lose them?' in js

    def test_workspace_script_handles_project_reload_failures_without_leaving_the_ui_blank(self, client):
        response = client.get('/lab/static/js/workspace.js')

        assert response.status_code == 200
        js = response.get_data(as_text=True)

        assert 'function renderWorkspaceLoadFailure(message, { redirectToProjects = false } = {})' in js
        assert "Project unavailable" in js
        assert "Project not found" in js
        assert "Network error while loading this project." in js
        assert "window.location.href = '/lab/projects';" in js
        assert 'redirectToProjects: /not found/i.test(message)' in js

    def test_workspace_script_restores_folder_collapse_state_after_search(self, client):
        response = client.get('/lab/static/js/workspace.js')

        assert response.status_code == 200
        js = response.get_data(as_text=True)

        assert 'let folderStateBeforeSearch = null;' in js
        assert 'function setFileSearchQuery(value = \'\') {' in js
        assert 'const hadQuery = Boolean(fileSearchQuery.trim());' in js
        assert 'const hasQuery = Boolean(nextQuery.trim());' in js
        assert 'folderStateBeforeSearch = { ...openFolderPaths };' in js
        assert 'openFolderPaths = folderStateBeforeSearch ? { ...folderStateBeforeSearch } : openFolderPaths;' in js
        assert 'folderStateBeforeSearch = null;' in js

    def test_workspace_script_prunes_stale_folder_and_menu_state_after_structural_changes(self, client):
        response = client.get('/lab/static/js/workspace.js')

        assert response.status_code == 200
        js = response.get_data(as_text=True)

        assert 'function getExistingFolderPaths(files = projectFiles)' in js
        assert 'function pruneFolderStateSnapshot(snapshot, validPaths)' in js
        assert 'function reconcileWorkspaceTreeState()' in js
        assert 'openFolderPaths = pruneFolderStateSnapshot(openFolderPaths, validPaths);' in js
        assert 'folderStateBeforeSearch = pruneFolderStateSnapshot(folderStateBeforeSearch, validPaths);' in js
        assert 'if (activeFileMenuId !== null && !getProjectFileById(activeFileMenuId)) {' in js
        assert 'reconcileWorkspaceTreeState();' in js

    def test_versions_script_handles_network_errors_during_save(self, client):
        response = client.get('/lab/static/js/workspace-versions.js')

        assert response.status_code == 200
        js = response.get_data(as_text=True)

        assert 'let data;' in js
        assert 'try {' in js
        assert 'data = await apiRequest(`/projects/${projectId}/versions`,' in js
        assert '} catch (error) {' in js
        assert "error.message || 'Failed to save version. Please try again.'" in js

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
