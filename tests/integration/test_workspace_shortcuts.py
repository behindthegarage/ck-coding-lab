"""Regression tests for workspace keyboard shortcut affordances."""

import pytest


@pytest.mark.integration
class TestWorkspaceKeyboardShortcuts:
    """The workspace should expose discoverable keyboard shortcuts."""

    def test_workspace_template_includes_shortcut_hints_and_modal(self, client):
        response = client.get('/lab/project/123')

        assert response.status_code == 200
        html = response.get_data(as_text=True)

        assert 'id="file-search-input"' in html
        assert 'Quick open files...' in html
        assert 'Ctrl/Cmd + P to search • Enter to open' in html
        assert 'id="shortcuts-help-btn"' in html
        assert 'id="shortcuts-modal"' in html
        assert 'Ctrl/Cmd + Shift + S' in html
        assert 'Alt + 1 / 2 / 3' in html

    def test_workspace_script_registers_global_shortcuts(self, client):
        response = client.get('/lab/static/js/workspace.js')

        assert response.status_code == 200
        js = response.get_data(as_text=True)

        assert 'function handleGlobalWorkspaceShortcuts(e)' in js
        assert "key === 'p'" in js
        assert "key === 's'" in js
        assert "key === '1'" in js
        assert "key === '2'" in js
        assert "key === '3'" in js
        assert "focusFileSearchShortcut" in js
        assert "focusChatShortcut" in js
        assert "focusPreviewShortcut" in js
        assert "saveProjectVersion()" in js
        assert "openShortcutsModal()" in js
        assert "document.addEventListener('keydown', handleGlobalWorkspaceShortcuts)" in js
