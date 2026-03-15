# tests/conftest.py - Shared pytest fixtures for CK Coding Lab
"""
Shared fixtures for all CK Coding Lab tests.

Fixtures provided:
- app: Flask app instance with test configuration
- client: Flask test client
- db_path: Path to temporary test database
- test_user: Factory for creating test users
- auth_headers: Helper to get auth headers for a user
"""

import os
import sys
import tempfile
import pytest
import uuid
import sqlite3
from datetime import datetime, timedelta, timezone

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


# Global to track current test database
_current_test_db = None


@pytest.fixture(autouse=True)
def setup_database(monkeypatch, tmp_path):
    """
    Autouse fixture to ensure database is properly configured for all tests.
    This runs before each test and sets up a fresh database.
    """
    global _current_test_db
    
    # Create temporary database
    db_path = str(tmp_path / 'test.db')
    _current_test_db = db_path
    
    # Set environment variable
    monkeypatch.setenv('CKCL_DB_PATH', db_path)
    
    # Create database file and initialize
    from database import init_db_full
    init_db_full(db_path)
    
    yield db_path
    
    # Cleanup - file will be deleted by tmp_path fixture
    _current_test_db = None


@pytest.fixture
def app(setup_database):
    """
    Create and configure a Flask app for testing.
    Uses the database from setup_database fixture.
    
    Yields:
        Flask: Configured Flask application with test database
    """
    from app import create_app
    
    app = create_app({
        'TESTING': True,
        'DATABASE': setup_database,
        'SECRET_KEY': 'test-secret-key'
    })
    
    yield app


@pytest.fixture
def client(app):
    """
    Create a test client for the app.
    
    Args:
        app: Flask app fixture
        
    Returns:
        TestClient: Flask test client
    """
    return app.test_client()


@pytest.fixture
def db_path(setup_database):
    """
    Get the test database path.
    
    Returns:
        str: Path to test database
    """
    return setup_database


@pytest.fixture
def db_connection(setup_database):
    """
    Get a database connection for direct database operations in tests.
    
    Yields:
        sqlite3.Cursor: Database cursor with foreign keys enabled
    """
    conn = sqlite3.connect(setup_database)
    conn.execute("PRAGMA foreign_keys = ON")
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    
    yield cursor
    
    conn.commit()
    conn.close()


# ==================== User Fixtures ====================

@pytest.fixture
def test_user_factory(setup_database):
    """
    Factory fixture for creating test users with unique usernames.
    
    Returns a function that creates users with default test values.
    Uses UUID to ensure uniqueness across tests.
    
    Usage:
        def test_something(test_user_factory):
            user = test_user_factory(pin='1234')
    """
    from auth import create_user
    
    def _create_user(username=None, pin='1234', role='kid'):
        # Generate unique username if not provided
        if username is None:
            username = f'user_{uuid.uuid4().hex[:8]}'
        user = create_user(username, pin, role)
        return user
    
    return _create_user


@pytest.fixture
def test_user(test_user_factory):
    """
    Create a single test user with unique username.
    
    Returns:
        dict: User data (without pin_hash)
    """
    return test_user_factory(pin='1234', role='kid')


@pytest.fixture
def test_admin(test_user_factory):
    """
    Create a test admin user.
    
    Returns:
        dict: Admin user data
    """
    return test_user_factory(pin='5678', role='admin')


@pytest.fixture
def auth_token_factory(setup_database):
    """
    Factory fixture for creating authentication tokens.
    
    Returns a function that creates session tokens for user IDs.
    """
    from auth import create_session
    
    def _create_token(user_id):
        return create_session(user_id)
    
    return _create_token


@pytest.fixture
def auth_headers_factory(auth_token_factory):
    """
    Factory fixture for creating Authorization headers.
    
    Returns a function that creates headers dict with Bearer token.
    
    Usage:
        def test_protected(auth_headers_factory, test_user):
            headers = auth_headers_factory(test_user['id'])
            client.get('/api/auth/me', headers=headers)
    """
    def _create_headers(user_id):
        token = auth_token_factory(user_id)
        return {'Authorization': f'Bearer {token}'}
    
    return _create_headers


@pytest.fixture
def auth_headers(auth_headers_factory, test_user):
    """
    Authorization headers for the default test user.
    
    Returns:
        dict: Headers with Authorization Bearer token
    """
    return auth_headers_factory(test_user['id'])


@pytest.fixture
def admin_auth_headers(auth_headers_factory, test_admin):
    """
    Authorization headers for the test admin user.
    
    Returns:
        dict: Headers with Authorization Bearer token for admin
    """
    return auth_headers_factory(test_admin['id'])


# ==================== Project Fixtures ====================

@pytest.fixture
def project_factory(setup_database, test_user):
    """
    Factory fixture for creating test projects.
    
    Usage:
        def test_project(project_factory):
            project = project_factory(name='My Game', description='Test')
    """
    def _create_project(name=None, description='A test project', language='p5js'):
        conn = sqlite3.connect(setup_database)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        # Generate unique name if not provided
        if name is None:
            name = f'Project_{uuid.uuid4().hex[:8]}'
        
        cursor.execute('''
            INSERT INTO projects (user_id, name, description, language)
            VALUES (?, ?, ?, ?)
        ''', (test_user['id'], name, description, language))
        
        project_id = cursor.lastrowid
        conn.commit()
        
        cursor.execute('SELECT * FROM projects WHERE id = ?', (project_id,))
        project = dict(cursor.fetchone())
        conn.close()
        
        return project
    
    return _create_project


@pytest.fixture
def test_project(project_factory):
    """
    Create a single test project with default values.
    
    Returns:
        dict: Project data
    """
    return project_factory()


# ==================== Utility Fixtures ====================

@pytest.fixture
def create_multiple_users(test_user_factory):
    """
    Create multiple test users at once.
    
    Usage:
        def test_bulk(create_multiple_users):
            users = create_multiple_users(5)
    """
    def _create_many(count=3):
        users = []
        for i in range(count):
            pin = f'{1000 + i:04d}'
            user = test_user_factory(pin=pin)
            users.append(user)
        return users
    
    return _create_many


@pytest.fixture
def mock_ai_response():
    """
    Mock AI response data for testing AI client parsing.
    
    Returns:
        dict: Sample AI response with code, explanation, etc.
    """
    return {
        'success': True,
        'code': '''function setup() {
    createCanvas(400, 400);
}

function draw() {
    background(220);
    ellipse(200, 200, 100, 100);
}''',
        'explanation': 'This creates a simple canvas with a circle.',
        'suggestions': ['Add color', 'Make it interactive'],
        'model': 'kimi-k2.5',
        'tokens_used': 150
    }
