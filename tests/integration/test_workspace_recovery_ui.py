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
        assert 'Restore a named save point or an automatic checkpoint if you need to roll the project back.' in html
        assert '/lab/static/css/workspace.css?v=44' in html
        assert '/lab/static/js/auth.js?v=8' in html
        assert '/lab/static/js/workspace.js?v=55' in html
        assert '/lab/static/js/workspace-versions.js?v=5' in html
        assert 'Version History' in html

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

    def test_workspace_script_sanitizes_legacy_inline_tool_payload_markers(self, client):
        response = client.get('/lab/static/js/workspace.js')

        assert response.status_code == 200
        js = response.get_data(as_text=True)

        assert 'function sanitizeAssistantContent(content)' in js
        assert '<\\|tool_calls_section_begin\\|>' in js
        assert '<\\|tool_call_begin\\|>' in js
        assert 'functions\\.' in js

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

    def test_workspace_script_reconciles_ai_change_badges_after_manual_rename_delete_and_restore(self, client):
        response = client.get('/lab/static/js/workspace.js')

        assert response.status_code == 200
        js = response.get_data(as_text=True)

        assert 'let suppressAssistantChangeBadgesOnce = false;' in js
        assert 'function clearLatestAssistantChanges()' in js
        assert 'function moveLatestAssistantChange(previousFilename, nextFilename)' in js
        assert 'function removeLatestAssistantChange(filename)' in js
        assert 'function suppressAssistantChangeBadgesForNextConversationRender()' in js
        assert 'moveLatestAssistantChange(previousFilename, data.file.filename);' in js
        assert 'removeLatestAssistantChange(deletedFilename);' in js
        assert 'const shouldSuppressAssistantBadges = suppressAssistantChangeBadgesOnce;' in js
        assert 'clearLatestAssistantChanges();' in js

    def test_workspace_script_refreshes_current_code_and_clears_stale_open_file_state_after_ai_file_changes(self, client):
        response = client.get('/lab/static/js/workspace.js')

        assert response.status_code == 200
        js = response.get_data(as_text=True)

        assert 'function clearMissingCurrentFileSelection()' in js
        assert "showWorkspaceToast('The file you were viewing is no longer in this project.'" in js
        assert 'clearMissingCurrentFileSelection();' in js
        assert 'currentCode = project.current_code || \"\";' not in js
        assert "currentCode = project.current_code || '';" in js
        assert 'updateCodeDisplay();' in js
        assert 'async function refreshFileTree() {' in js
        assert 'if (data && data.success && data.project) {' in js
        assert 'project = data.project;' in js
        assert 'projectFiles = data.files || [];' in js
        assert 'currentCode = project.current_code || \"\";' not in js
        assert 'reconcileWorkspaceTreeState();' in js

    def test_workspace_script_reconciles_open_file_modal_content_when_project_state_changes_under_it(self, client):
        response = client.get('/lab/static/js/workspace.js')

        assert response.status_code == 200
        js = response.get_data(as_text=True)

        assert 'function syncOpenFileModalWithProjectState()' in js
        assert 'const nextContent = currentFile.content || \"\";' not in js
        assert "const nextContent = currentFile.content || '';" in js
        assert 'const hasUnsavedLocalEdits = isFileModalDirty();' in js
        assert 'filenameEl.textContent = currentFile.filename;' in js
        assert 'This file changed elsewhere. Review before saving so you do not overwrite newer code.' in js
        assert 'File updated from the latest project state.' in js
        assert 'syncOpenFileModalWithProjectState();' in js

    def test_workspace_script_handles_sidebar_file_action_failures_without_silent_crashes(self, client):
        response = client.get('/lab/static/js/workspace.js')

        assert response.status_code == 200
        js = response.get_data(as_text=True)

        assert "console.error('Error renaming file from sidebar:'" in js
        assert "console.error('Error deleting file from sidebar:'" in js
        assert "console.error('Error restoring deleted file:'" in js
        assert "showWorkspaceToast(error.message || 'Failed to rename file.'" in js
        assert "showWorkspaceToast(error.message || 'Failed to delete file.'" in js
        assert "showWorkspaceToast(error.message || `Couldn't restore ${deletedFile.filename}.`" in js

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
        assert 'function getRecoveryWorkspaceVersions()' in js
        assert "return versionOrDescription.checkpoint_kind === 'recovery';" in js
        assert 'function getVersionDetail(version)' in js
        assert 'version-detail' in js
        assert 'async function createRecoveryVersion(reason = \'Before risky workspace action\')' in js
        assert 'async function undoWorkspaceRecovery(versionId, label = \'your previous project state\')' in js
        assert 'Safety nets the system created before risky changes or after AI updates.' in js
        assert 'const data = await apiRequest(`/projects/${projectId}/versions`);' in js
        assert 'Added an automatic checkpoint so this older project has a safe place to come back to.' in js
        assert 'suppressAssistantChangeBadgesForNextConversationRender();' in js
        assert "Couldn't create a safety net, so the restore was canceled." in js

    def test_workspace_script_supports_opening_version_history_from_project_launch_intent(self, client):
        response = client.get('/lab/static/js/workspace.js')

        assert response.status_code == 200
        js = response.get_data(as_text=True)

        assert 'const workspaceLaunchParams = new URLSearchParams(window.location.search);' in js
        assert 'function consumeWorkspaceLaunchIntent()' in js
        assert "const modal = workspaceLaunchParams.get('modal');" in js
        assert "if (modal === 'versions' && typeof openVersionsModal === 'function')" in js
        assert 'window.history.replaceState({}, \'\', nextUrl);' in js
        assert 'consumeWorkspaceLaunchIntent();' in js

    def test_workspace_styles_include_toast_action_layout(self, client):
        response = client.get('/lab/static/css/workspace.css')

        assert response.status_code == 200
        css = response.get_data(as_text=True)

        assert '.workspace-toast-actions' in css
        assert '.workspace-toast-action' in css
        assert '.workspace-toast-dismiss' in css
        assert '.workspace-toast-message' in css
