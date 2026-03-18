# tests/integration/test_upload_ui.py
"""Regression tests for the workspace upload experience."""

import pytest


@pytest.mark.integration
class TestWorkspaceUploadSurface:
    """The workspace should expose the improved upload affordances."""

    def test_workspace_template_includes_upload_dropzone_and_clear_action(self, client):
        response = client.get('/lab/project/123')

        assert response.status_code == 200
        html = response.get_data(as_text=True)

        assert 'id="upload-dropzone"' in html
        assert 'id="upload-clear"' in html
        assert 'Drop an image or code file here, or tap Upload.' in html
        assert 'Images are shared with Hari. Text files get pasted into chat.' in html

    def test_workspace_script_supports_drag_drop_and_default_upload_prompts(self, client):
        response = client.get('/lab/static/js/workspace.js')

        assert response.status_code == 200
        js = response.get_data(as_text=True)

        assert 'function setupUploadDropzone()' in js
        assert "dropzone.addEventListener('drop'" in js
        assert 'function buildUploadMessage(message)' in js
        assert 'Please look at this image and help me use it in my project.' in js
        assert 'press Send to use a starter prompt' in js
