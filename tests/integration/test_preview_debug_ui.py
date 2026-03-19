# tests/integration/test_preview_debug_ui.py
"""Regression tests for the preview debug surface."""

import pytest


@pytest.mark.integration
class TestPreviewDebugSurface:
    """The workspace should expose a lightweight preview debug pane."""

    def test_workspace_template_includes_preview_debug_panel(self, client):
        response = client.get('/lab/project/123')

        assert response.status_code == 200
        html = response.get_data(as_text=True)

        assert 'id="preview-debug-panel"' in html
        assert 'id="preview-debug-toggle"' in html
        assert 'id="preview-debug-list"' in html
        assert 'Watching runtime errors and console.error.' in html
        assert '/lab/static/js/workspace-preview.js?v=3' in html

    def test_sandbox_injects_runtime_and_console_debug_bridge(self, client):
        response = client.get('/lab/static/js/sandbox.js')

        assert response.status_code == 200
        js = response.get_data(as_text=True)

        assert 'window.__CKPreviewBridge = { post, serialize };' in js
        assert "type: 'console'" in js
        assert "type: 'runtime-error'" in js
        assert "window.addEventListener('unhandledrejection'" in js

    def test_workspace_preview_script_renders_debug_entries(self, client):
        response = client.get('/lab/static/js/workspace-preview.js')

        assert response.status_code == 200
        js = response.get_data(as_text=True)

        assert 'function appendPreviewDebugEntry(entry)' in js
        assert 'preview-debug-entry' in js
        assert 'Could not load preview files' in js
        assert "const hasHtmlEntry = projectFiles.some(f => (f.filename || '').toLowerCase().endsWith('.html'));" in js
        assert "const entryFilename = response.entry_filename || 'index.html';" in js
        assert 'const bundledHtml = buildPreviewBundle(response.files, entryFilename);' in js
        assert "function buildPreviewBundle(files, entryFilename = 'index.html')" in js
