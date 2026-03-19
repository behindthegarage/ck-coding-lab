"""Regression tests for humane auth/API error handling in the browser."""

import pytest


@pytest.mark.integration
class TestAuthErrorHandlingUI:
    def test_auth_script_summarizes_gateway_html_errors_for_users(self, client):
        response = client.get('/lab/static/js/auth.js')

        assert response.status_code == 200
        js = response.get_data(as_text=True)

        assert 'function summarizeServerError(response, raw = \'\')' in js
        assert "if (status === 504) {" in js
        assert "return 'The AI took too long to respond. Please try again.';" in js
        assert "if (status === 502 || status === 503) {" in js
        assert "return 'The AI service is temporarily unavailable. Please try again.';" in js
        assert "const looksLikeHtml = /<html|<body|<!doctype/i.test(normalized);" in js
        assert 'summarizeServerError(response, raw)' in js
