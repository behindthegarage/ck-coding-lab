# tests/integration/test_preview_isolation.py
"""Regression tests for preview/session isolation boundaries."""

import re

import pytest


@pytest.mark.integration
class TestPreviewIsolation:
    """Preview sandbox hardening should keep preview code off the app origin."""

    def test_preview_iframe_does_not_allow_same_origin(self, client):
        response = client.get('/lab/static/js/sandbox.js')

        assert response.status_code == 200
        js = response.get_data(as_text=True)

        assert "const PREVIEW_SANDBOX_PERMISSIONS = 'allow-scripts';" in js
        assert 'allow-same-origin' not in js

    def test_preview_messages_are_scoped_to_the_active_iframe(self, client):
        response = client.get('/lab/static/js/sandbox.js')

        assert response.status_code == 200
        js = response.get_data(as_text=True)

        assert re.search(
            r"if \(!event\.data \|\| !this\.iframe \|\| event\.source !== this\.iframe\.contentWindow\)",
            js,
        )
