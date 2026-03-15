"""
E2E Tests - CK Coding Lab
End-to-end user flow tests for critical user journeys.
"""

import pytest

# Mark all E2E tests
def pytest_configure(config):
    """Configure pytest markers for E2E tests."""
    config.addinivalue_line("markers", "e2e: mark test as end-to-end test")
