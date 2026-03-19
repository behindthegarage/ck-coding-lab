"""Regression tests for the public lab entry route."""

import pytest


@pytest.mark.integration
class TestLabEntryRoute:
    def test_lab_root_and_trailing_slash_both_serve_login(self, client):
        for path in ('/lab', '/lab/'):
            response = client.get(path)

            assert response.status_code == 200
            html = response.get_data(as_text=True)
            assert 'Welcome to Coding Lab' in html
            assert 'PIN Code' in html
