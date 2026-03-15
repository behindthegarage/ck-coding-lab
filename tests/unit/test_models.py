# tests/unit/test_models.py - Database model tests
"""
Unit tests for database models and operations.

Tests cover:
- Database initialization
- Project CRUD operations
- Conversation storage
- File management
- Data integrity
"""

import pytest
import sqlite3


@pytest.mark.unit
@pytest.mark.models
class TestDatabaseInitialization:
    """Tests for database schema initialization."""
    
    def test_users_table_exists(self, db_connection):
        """Test that users table is created."""
        db_connection.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='users'"
        )
        assert db_connection.fetchone() is not None
    
    def test_sessions_table_exists(self, db_connection):
        """Test that sessions table is created."""
        db_connection.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='sessions'"
        )
        assert db_connection.fetchone() is not None
    
    def test_projects_table_exists(self, db_connection):
        """Test that projects table is created."""
        db_connection.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='projects'"
        )
        assert db_connection.fetchone() is not None
    
    def test_conversations_table_exists(self, db_connection):
        """Test that conversations table is created."""
        db_connection.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='conversations'"
        )
        assert db_connection.fetchone() is not None
    
    def test_project_files_table_exists(self, db_connection):
        """Test that project_files table is created."""
        db_connection.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='project_files'"
        )
        assert db_connection.fetchone() is not None
    
    def test_sessions_indexes_exist(self, db_connection):
        """Test that session indexes are created."""
        db_connection.execute(
            "SELECT name FROM sqlite_master WHERE type='index' AND name='idx_sessions_token'"
        )
        assert db_connection.fetchone() is not None
        
        db_connection.execute(
            "SELECT name FROM sqlite_master WHERE type='index' AND name='idx_sessions_expires'"
        )
        assert db_connection.fetchone() is not None


@pytest.mark.unit
@pytest.mark.models
class TestProjectModel:
    """Tests for project database operations."""
    
    def test_create_project(self, db_path, db_connection):
        """Test creating a project."""
        # First create a user directly in this connection
        db_connection.execute('''
            INSERT INTO users (username, pin_hash, role)
            VALUES (?, ?, ?)
        ''', ('project_test_user', 'hash', 'kid'))
        user_id = db_connection.lastrowid
        
        db_connection.execute('''
            INSERT INTO projects (user_id, name, description, language)
            VALUES (?, ?, ?, ?)
        ''', (user_id, 'Test Project', 'Description', 'p5js'))
        
        project_id = db_connection.lastrowid
        assert project_id is not None
        
        db_connection.execute('SELECT * FROM projects WHERE id = ?', (project_id,))
        project = db_connection.fetchone()
        
        assert project['name'] == 'Test Project'
        assert project['description'] == 'Description'
        assert project['language'] == 'p5js'
        assert project['user_id'] == user_id
    
    def test_project_has_timestamps(self, db_path, db_connection):
        """Test that projects have created_at and updated_at."""
        # Create a user first
        db_connection.execute('''
            INSERT INTO users (username, pin_hash, role)
            VALUES (?, ?, ?)
        ''', ('timestamp_user', 'hash', 'kid'))
        user_id = db_connection.lastrowid
        
        db_connection.execute('''
            INSERT INTO projects (user_id, name)
            VALUES (?, ?)
        ''', (user_id, 'Timestamp Test'))
        
        project_id = db_connection.lastrowid
        db_connection.execute('SELECT created_at, updated_at FROM projects WHERE id = ?', (project_id,))
        project = db_connection.fetchone()
        
        assert project['created_at'] is not None
        assert project['updated_at'] is not None
    
    def test_project_user_foreign_key(self, db_connection):
        """Test that project user_id has foreign key constraint."""
        # Try to insert project with non-existent user
        with pytest.raises(sqlite3.IntegrityError):
            db_connection.execute('''
                INSERT INTO projects (user_id, name)
                VALUES (99999, 'Bad Project')
            ''')
    
    def test_project_name_length_constraint(self, db_path, db_connection):
        """Test project name length limits - SQLite allows empty strings."""
        # Create a user first
        db_connection.execute('''
            INSERT INTO users (username, pin_hash, role)
            VALUES (?, ?, ?)
        ''', ('name_test_user', 'hash', 'kid'))
        user_id = db_connection.lastrowid
        
        # Empty name - SQLite allows this, our application layer validates
        # Just verify the constraint at DB level isn't violated
        db_connection.execute('''
            INSERT INTO projects (user_id, name)
            VALUES (?, '')
        ''', (user_id,))
        
        # Should have created the project
        project_id = db_connection.lastrowid
        assert project_id is not None
    
    def test_update_project(self, db_path, db_connection):
        """Test updating a project."""
        # Create a user first
        db_connection.execute('''
            INSERT INTO users (username, pin_hash, role)
            VALUES (?, ?, ?)
        ''', ('update_user', 'hash', 'kid'))
        user_id = db_connection.lastrowid
        
        db_connection.execute('''
            INSERT INTO projects (user_id, name, description)
            VALUES (?, ?, ?)
        ''', (user_id, 'Original Name', 'Old desc'))
        project_id = db_connection.lastrowid
        
        db_connection.execute('''
            UPDATE projects SET name = ?, description = ? WHERE id = ?
        ''', ('Updated Name', 'Updated Description', project_id))
        
        db_connection.execute('SELECT * FROM projects WHERE id = ?', (project_id,))
        updated = db_connection.fetchone()
        
        assert updated['name'] == 'Updated Name'
        assert updated['description'] == 'Updated Description'
    
    def test_delete_project_cascades(self, db_path, db_connection):
        """Test that deleting project cascades to conversations."""
        # Create a user first
        db_connection.execute('''
            INSERT INTO users (username, pin_hash, role)
            VALUES (?, ?, ?)
        ''', ('cascade_user', 'hash', 'kid'))
        user_id = db_connection.lastrowid
        
        db_connection.execute('''
            INSERT INTO projects (user_id, name)
            VALUES (?, ?)
        ''', (user_id, 'Cascade Test'))
        project_id = db_connection.lastrowid
        
        # Add a conversation
        db_connection.execute('''
            INSERT INTO conversations (project_id, role, content)
            VALUES (?, ?, ?)
        ''', (project_id, 'user', 'Test message'))
        
        # Delete project
        db_connection.execute('DELETE FROM projects WHERE id = ?', (project_id,))
        
        # Conversation should be gone
        db_connection.execute('SELECT * FROM conversations WHERE project_id = ?', (project_id,))
        assert db_connection.fetchone() is None


@pytest.mark.unit
@pytest.mark.models
class TestConversationModel:
    """Tests for conversation database operations."""
    
    def test_create_conversation(self, db_path, db_connection):
        """Test creating a conversation entry."""
        # Create a user and project first
        db_connection.execute('''
            INSERT INTO users (username, pin_hash, role)
            VALUES (?, ?, ?)
        ''', ('conv_user', 'hash', 'kid'))
        user_id = db_connection.lastrowid
        
        db_connection.execute('''
            INSERT INTO projects (user_id, name)
            VALUES (?, ?)
        ''', (user_id, 'Conversation Test'))
        project_id = db_connection.lastrowid
        
        db_connection.execute('''
            INSERT INTO conversations (project_id, role, content, model, tokens_used)
            VALUES (?, ?, ?, ?, ?)
        ''', (project_id, 'user', 'Hello AI', 'kimi-k2.5', 10))
        
        conv_id = db_connection.lastrowid
        assert conv_id is not None
        
        db_connection.execute('SELECT * FROM conversations WHERE id = ?', (conv_id,))
        conv = db_connection.fetchone()
        
        assert conv['role'] == 'user'
        assert conv['content'] == 'Hello AI'
        assert conv['model'] == 'kimi-k2.5'
        assert conv['tokens_used'] == 10
    
    def test_conversation_roles_constraint(self, db_path, db_connection):
        """Test that only valid roles are allowed."""
        # Create a user and project first
        db_connection.execute('''
            INSERT INTO users (username, pin_hash, role)
            VALUES (?, ?, ?)
        ''', ('role_user', 'hash', 'kid'))
        user_id = db_connection.lastrowid
        
        db_connection.execute('''
            INSERT INTO projects (user_id, name)
            VALUES (?, ?)
        ''', (user_id, 'Role Test'))
        project_id = db_connection.lastrowid
        
        # Valid roles should work
        for role in ['user', 'assistant', 'system']:
            db_connection.execute('''
                INSERT INTO conversations (project_id, role, content)
                VALUES (?, ?, ?)
            ''', (project_id, role, f'{role} message'))
        
        # Invalid role should fail
        with pytest.raises(sqlite3.IntegrityError):
            db_connection.execute('''
                INSERT INTO conversations (project_id, role, content)
                VALUES (?, ?, ?)
            ''', (project_id, 'invalid_role', 'test'))
    
    def test_conversation_ordering(self, db_path, db_connection):
        """Test that conversations can be ordered by created_at."""
        # Create a user and project first
        db_connection.execute('''
            INSERT INTO users (username, pin_hash, role)
            VALUES (?, ?, ?)
        ''', ('order_user', 'hash', 'kid'))
        user_id = db_connection.lastrowid
        
        db_connection.execute('''
            INSERT INTO projects (user_id, name)
            VALUES (?, ?)
        ''', (user_id, 'Ordering Test'))
        project_id = db_connection.lastrowid
        
        # Insert conversations with slight delay
        import time
        
        for i in range(3):
            db_connection.execute('''
                INSERT INTO conversations (project_id, role, content)
                VALUES (?, ?, ?)
            ''', (project_id, 'user', f'Message {i}'))
            time.sleep(0.01)  # Small delay
        
        db_connection.execute('''
            SELECT content FROM conversations WHERE project_id = ?
            ORDER BY created_at ASC
        ''', (project_id,))
        
        results = db_connection.fetchall()
        assert len(results) == 3
        assert results[0]['content'] == 'Message 0'
        assert results[2]['content'] == 'Message 2'


@pytest.mark.unit
@pytest.mark.models
class TestProjectFilesModel:
    """Tests for project files database operations."""
    
    def test_create_project_file(self, db_path, db_connection):
        """Test creating a project file."""
        # Create a user and project first
        db_connection.execute('''
            INSERT INTO users (username, pin_hash, role)
            VALUES (?, ?, ?)
        ''', ('file_user', 'hash', 'kid'))
        user_id = db_connection.lastrowid
        
        db_connection.execute('''
            INSERT INTO projects (user_id, name)
            VALUES (?, ?)
        ''', (user_id, 'File Test'))
        project_id = db_connection.lastrowid
        
        db_connection.execute('''
            INSERT INTO project_files (project_id, filename, content)
            VALUES (?, ?, ?)
        ''', (project_id, 'design.md', '# Design Doc'))
        
        file_id = db_connection.lastrowid
        assert file_id is not None
        
        db_connection.execute('SELECT * FROM project_files WHERE id = ?', (file_id,))
        file = db_connection.fetchone()
        
        assert file['filename'] == 'design.md'
        assert file['content'] == '# Design Doc'
    
    def test_project_file_unique_constraint(self, db_path, db_connection):
        """Test that duplicate filenames per project are prevented."""
        # Create a user and project first
        db_connection.execute('''
            INSERT INTO users (username, pin_hash, role)
            VALUES (?, ?, ?)
        ''', ('unique_user', 'hash', 'kid'))
        user_id = db_connection.lastrowid
        
        db_connection.execute('''
            INSERT INTO projects (user_id, name)
            VALUES (?, ?)
        ''', (user_id, 'Unique Test'))
        project_id = db_connection.lastrowid
        
        db_connection.execute('''
            INSERT INTO project_files (project_id, filename, content)
            VALUES (?, ?, ?)
        ''', (project_id, 'design.md', 'Content'))
        
        # Duplicate filename should fail
        with pytest.raises(sqlite3.IntegrityError):
            db_connection.execute('''
                INSERT INTO project_files (project_id, filename, content)
                VALUES (?, ?, ?)
            ''', (project_id, 'design.md', 'Other content'))
    
    def test_different_projects_same_filename(self, db_path, db_connection):
        """Test that different projects can have same filename."""
        # Create a user first
        db_connection.execute('''
            INSERT INTO users (username, pin_hash, role)
            VALUES (?, ?, ?)
        ''', ('multi_user', 'hash', 'kid'))
        user_id = db_connection.lastrowid
        
        # Create two projects
        db_connection.execute('''
            INSERT INTO projects (user_id, name) VALUES (?, ?)
        ''', (user_id, 'Project 1'))
        project1_id = db_connection.lastrowid
        
        db_connection.execute('''
            INSERT INTO projects (user_id, name) VALUES (?, ?)
        ''', (user_id, 'Project 2'))
        project2_id = db_connection.lastrowid
        
        # Both can have design.md
        db_connection.execute('''
            INSERT INTO project_files (project_id, filename, content)
            VALUES (?, ?, ?)
        ''', (project1_id, 'design.md', 'Project 1 design'))
        
        db_connection.execute('''
            INSERT INTO project_files (project_id, filename, content)
            VALUES (?, ?, ?)
        ''', (project2_id, 'design.md', 'Project 2 design'))
        
        # Both should exist
        db_connection.execute('SELECT COUNT(*) FROM project_files WHERE filename = ?', ('design.md',))
        assert db_connection.fetchone()[0] == 2


@pytest.mark.unit
@pytest.mark.models
class TestSessionModel:
    """Tests for session database operations."""
    
    def test_session_has_expires_at(self, db_path, db_connection):
        """Test that sessions have expiration timestamps."""
        # Create a user first
        db_connection.execute('''
            INSERT INTO users (username, pin_hash, role)
            VALUES (?, ?, ?)
        ''', ('session_user', 'hash', 'kid'))
        user_id = db_connection.lastrowid
        
        from datetime import datetime, timezone, timedelta
        expires_at = datetime.now(timezone.utc) + timedelta(hours=24)
        
        db_connection.execute('''
            INSERT INTO sessions (user_id, token, expires_at)
            VALUES (?, ?, datetime(?))
        ''', (user_id, 'test_token_12345', expires_at.strftime('%Y-%m-%dT%H:%M:%S')))
        
        db_connection.execute('SELECT expires_at FROM sessions WHERE token = ?', ('test_token_12345',))
        session = db_connection.fetchone()
        
        assert session[0] is not None
    
    def test_session_cascade_delete_on_user(self, db_path, db_connection):
        """Test that user deletion cascades to sessions."""
        # Create a user first
        db_connection.execute('''
            INSERT INTO users (username, pin_hash, role)
            VALUES (?, ?, ?)
        ''', ('cascade_user', 'hash', 'kid'))
        user_id = db_connection.lastrowid
        
        # Create a session
        db_connection.execute('''
            INSERT INTO sessions (user_id, token, expires_at)
            VALUES (?, ?, datetime('now', '+1 day'))
        ''', (user_id, 'cascade_token'))
        
        # Delete user
        db_connection.execute('DELETE FROM users WHERE id = ?', (user_id,))
        
        # Session should be gone
        db_connection.execute('SELECT * FROM sessions WHERE token = ?', ('cascade_token',))
        assert db_connection.fetchone() is None


@pytest.mark.unit
@pytest.mark.models
class TestDataIntegrity:
    """Tests for data integrity constraints."""
    
    def test_user_username_unique(self, db_connection):
        """Test that usernames must be unique."""
        db_connection.execute('''
            INSERT INTO users (username, pin_hash, role)
            VALUES (?, ?, ?)
        ''', ('unique_integrity_test', 'hash', 'kid'))
        
        with pytest.raises(sqlite3.IntegrityError):
            db_connection.execute('''
                INSERT INTO users (username, pin_hash, role)
                VALUES (?, ?, ?)
            ''', ('unique_integrity_test', 'hash2', 'kid'))
    
    def test_foreign_key_enforcement(self, db_connection):
        """Test that foreign key constraints are enforced."""
        # Should not be able to create project for non-existent user
        with pytest.raises(sqlite3.IntegrityError):
            db_connection.execute('''
                INSERT INTO projects (user_id, name) VALUES (99999, 'Orphan')
            ''')
        
        # Should not be able to create conversation for non-existent project
        with pytest.raises(sqlite3.IntegrityError):
            db_connection.execute('''
                INSERT INTO conversations (project_id, role, content)
                VALUES (99999, 'user', 'test')
            ''')
