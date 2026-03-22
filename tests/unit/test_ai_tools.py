# tests/unit/test_ai_tools.py - FileTools Unit Tests
"""
Unit tests for the AI FileTools module.

Tests cover:
- File reading operations
- File writing operations
- File appending operations
- File listing operations
- Tool definitions
- Error handling
"""

import pytest
import sqlite3
import os


@pytest.fixture
def fresh_db(tmp_path, monkeypatch):
    """Create a fresh database for each test with proper isolation."""
    db_path = str(tmp_path / 'test.db')
    
    # Set environment BEFORE any imports
    monkeypatch.setenv('CKCL_DB_PATH', db_path)
    
    # Import and initialize after setting env
    from database import init_db_full
    init_db_full(db_path)
    
    return db_path


@pytest.mark.unit
class TestFileToolsInitialization:
    """Tests for FileTools initialization."""
    
    def test_tools_initializes_with_project_id(self):
        """Test that FileTools initializes with project_id."""
        from ai.tools import FileTools
        
        tools = FileTools(project_id=1)
        assert tools.project_id == 1
    
    def test_tools_different_project_ids(self):
        """Test that different instances have different project IDs."""
        from ai.tools import FileTools
        
        tools1 = FileTools(project_id=1)
        tools2 = FileTools(project_id=2)
        
        assert tools1.project_id != tools2.project_id


@pytest.mark.unit
class TestReadFile:
    """Tests for file reading operations."""
    
    def test_read_existing_file(self, fresh_db):
        """Test reading a file that exists."""
        from ai.tools import FileTools
        import sqlite3
        
        # Create project and file in database
        conn = sqlite3.connect(fresh_db)
        cursor = conn.cursor()
        
        # Create a user and project first
        cursor.execute('''
            INSERT INTO users (username, pin_hash, role)
            VALUES (?, ?, ?)
        ''', ('testuser', 'hash', 'kid'))
        user_id = cursor.lastrowid
        
        cursor.execute('''
            INSERT INTO projects (user_id, name, description, language)
            VALUES (?, ?, ?, ?)
        ''', (user_id, 'Test Project', 'Desc', 'p5js'))
        project_id = cursor.lastrowid
        
        # Create file
        cursor.execute('''
            INSERT INTO project_files (project_id, filename, content)
            VALUES (?, ?, ?)
        ''', (project_id, 'test.txt', 'Hello World'))
        
        conn.commit()
        conn.close()
        
        tools = FileTools(project_id=project_id)
        result = tools.read_file('test.txt')
        
        assert result['success'] is True
        assert result['filename'] == 'test.txt'
        assert result['content'] == 'Hello World'
        assert result['exists'] is True
    
    def test_read_nonexistent_file(self, fresh_db):
        """Test reading a file that doesn't exist."""
        from ai.tools import FileTools
        import sqlite3
        
        # Create project
        conn = sqlite3.connect(fresh_db)
        cursor = conn.cursor()
        cursor.execute('''
            INSERT INTO users (username, pin_hash, role)
            VALUES (?, ?, ?)
        ''', ('testuser2', 'hash', 'kid'))
        user_id = cursor.lastrowid
        cursor.execute('''
            INSERT INTO projects (user_id, name, description, language)
            VALUES (?, ?, ?, ?)
        ''', (user_id, 'Test', 'Desc', 'p5js'))
        project_id = cursor.lastrowid
        conn.commit()
        conn.close()
        
        tools = FileTools(project_id=project_id)
        result = tools.read_file('nonexistent.txt')
        
        assert result['success'] is True
        assert result['exists'] is False
        assert result['content'] == ''
    
    def test_read_file_wrong_project(self, fresh_db):
        """Test that files are isolated by project."""
        from ai.tools import FileTools
        import sqlite3
        
        # Create two projects
        conn = sqlite3.connect(fresh_db)
        cursor = conn.cursor()
        cursor.execute('''
            INSERT INTO users (username, pin_hash, role)
            VALUES (?, ?, ?)
        ''', ('testuser3', 'hash', 'kid'))
        user_id = cursor.lastrowid
        
        cursor.execute('''
            INSERT INTO projects (user_id, name, description, language)
            VALUES (?, ?, ?, ?)
        ''', (user_id, 'Project 1', 'Desc', 'p5js'))
        project1_id = cursor.lastrowid
        
        cursor.execute('''
            INSERT INTO projects (user_id, name, description, language)
            VALUES (?, ?, ?, ?)
        ''', (user_id, 'Project 2', 'Desc', 'p5js'))
        project2_id = cursor.lastrowid
        
        # Add file to project 1
        cursor.execute('''
            INSERT INTO project_files (project_id, filename, content)
            VALUES (?, ?, ?)
        ''', (project1_id, 'shared.txt', 'Project 1 content'))
        
        conn.commit()
        conn.close()
        
        # Try to read from project 2
        tools = FileTools(project_id=project2_id)
        result = tools.read_file('shared.txt')
        
        assert result['exists'] is False


@pytest.mark.unit
class TestWriteFile:
    """Tests for file writing operations."""
    
    def test_write_new_file(self, fresh_db):
        """Test creating a new file."""
        from ai.tools import FileTools
        import sqlite3
        
        # Create project
        conn = sqlite3.connect(fresh_db)
        cursor = conn.cursor()
        cursor.execute('''
            INSERT INTO users (username, pin_hash, role)
            VALUES (?, ?, ?)
        ''', ('testuser4', 'hash', 'kid'))
        user_id = cursor.lastrowid
        cursor.execute('''
            INSERT INTO projects (user_id, name, description, language)
            VALUES (?, ?, ?, ?)
        ''', (user_id, 'Test', 'Desc', 'p5js'))
        project_id = cursor.lastrowid
        conn.commit()
        conn.close()
        
        tools = FileTools(project_id=project_id)
        result = tools.write_file('newfile.txt', 'New content')
        
        assert result['success'] is True
        assert result['filename'] == 'newfile.txt'
        assert result['action'] == 'created'
        assert result['content_length'] == len('New content')
        assert tools.get_change_log()[-1] == {
            'filename': 'newfile.txt',
            'action': 'created',
            'before_content': '',
            'after_content': 'New content'
        }
    
    def test_update_existing_file(self, fresh_db):
        """Test updating an existing file."""
        from ai.tools import FileTools
        import sqlite3
        
        # Create project with file
        conn = sqlite3.connect(fresh_db)
        cursor = conn.cursor()
        cursor.execute('''
            INSERT INTO users (username, pin_hash, role)
            VALUES (?, ?, ?)
        ''', ('testuser5', 'hash', 'kid'))
        user_id = cursor.lastrowid
        cursor.execute('''
            INSERT INTO projects (user_id, name, description, language)
            VALUES (?, ?, ?, ?)
        ''', (user_id, 'Test', 'Desc', 'p5js'))
        project_id = cursor.lastrowid
        cursor.execute('''
            INSERT INTO project_files (project_id, filename, content)
            VALUES (?, ?, ?)
        ''', (project_id, 'existing.txt', 'Old content'))
        conn.commit()
        conn.close()
        
        tools = FileTools(project_id=project_id)
        result = tools.write_file('existing.txt', 'Updated content')
        
        assert result['success'] is True
        assert result['action'] == 'updated'
        
        # Verify content changed
        read_result = tools.read_file('existing.txt')
        assert read_result['content'] == 'Updated content'
    
    def test_write_empty_content(self, fresh_db):
        """Test writing empty content."""
        from ai.tools import FileTools
        import sqlite3
        
        conn = sqlite3.connect(fresh_db)
        cursor = conn.cursor()
        cursor.execute('''
            INSERT INTO users (username, pin_hash, role)
            VALUES (?, ?, ?)
        ''', ('testuser6', 'hash', 'kid'))
        user_id = cursor.lastrowid
        cursor.execute('''
            INSERT INTO projects (user_id, name, description, language)
            VALUES (?, ?, ?, ?)
        ''', (user_id, 'Test', 'Desc', 'p5js'))
        project_id = cursor.lastrowid
        conn.commit()
        conn.close()
        
        tools = FileTools(project_id=project_id)
        result = tools.write_file('empty.txt', '')
        
        assert result['success'] is True
        assert result['content_length'] == 0


@pytest.mark.unit
class TestAppendFile:
    """Tests for file append operations."""
    
    def test_append_to_existing_file(self, fresh_db):
        """Test appending to existing file."""
        from ai.tools import FileTools
        import sqlite3
        
        conn = sqlite3.connect(fresh_db)
        cursor = conn.cursor()
        cursor.execute('''
            INSERT INTO users (username, pin_hash, role)
            VALUES (?, ?, ?)
        ''', ('testuser7', 'hash', 'kid'))
        user_id = cursor.lastrowid
        cursor.execute('''
            INSERT INTO projects (user_id, name, description, language)
            VALUES (?, ?, ?, ?)
        ''', (user_id, 'Test', 'Desc', 'p5js'))
        project_id = cursor.lastrowid
        cursor.execute('''
            INSERT INTO project_files (project_id, filename, content)
            VALUES (?, ?, ?)
        ''', (project_id, 'append.txt', 'Original'))
        conn.commit()
        conn.close()
        
        tools = FileTools(project_id=project_id)
        result = tools.append_file('append.txt', ' Appended')
        
        assert result['success'] is True
        assert result['action'] == 'appended'
        
        # Verify content
        read_result = tools.read_file('append.txt')
        assert read_result['content'] == 'Original Appended'
        assert tools.get_change_log()[-1] == {
            'filename': 'append.txt',
            'action': 'appended',
            'before_content': 'Original',
            'after_content': 'Original Appended'
        }
    
    def test_append_creates_new_file(self, fresh_db):
        """Test that append creates file if it doesn't exist."""
        from ai.tools import FileTools
        import sqlite3
        
        conn = sqlite3.connect(fresh_db)
        cursor = conn.cursor()
        cursor.execute('''
            INSERT INTO users (username, pin_hash, role)
            VALUES (?, ?, ?)
        ''', ('testuser8', 'hash', 'kid'))
        user_id = cursor.lastrowid
        cursor.execute('''
            INSERT INTO projects (user_id, name, description, language)
            VALUES (?, ?, ?, ?)
        ''', (user_id, 'Test', 'Desc', 'p5js'))
        project_id = cursor.lastrowid
        conn.commit()
        conn.close()
        
        tools = FileTools(project_id=project_id)
        result = tools.append_file('newappend.txt', 'New content')
        
        assert result['success'] is True
        assert result['action'] == 'created'


@pytest.mark.unit
class TestListFiles:
    """Tests for file listing operations."""
    
    def test_list_files_empty_project(self, fresh_db):
        """Test listing files when project has none."""
        from ai.tools import FileTools
        import sqlite3
        
        conn = sqlite3.connect(fresh_db)
        cursor = conn.cursor()
        cursor.execute('''
            INSERT INTO users (username, pin_hash, role)
            VALUES (?, ?, ?)
        ''', ('testuser9', 'hash', 'kid'))
        user_id = cursor.lastrowid
        cursor.execute('''
            INSERT INTO projects (user_id, name, description, language)
            VALUES (?, ?, ?, ?)
        ''', (user_id, 'Test', 'Desc', 'p5js'))
        project_id = cursor.lastrowid
        conn.commit()
        conn.close()
        
        tools = FileTools(project_id=project_id)
        result = tools.list_files()
        
        assert result['success'] is True
        assert result['files'] == []
        assert result['count'] == 0
    
    def test_list_files_with_files(self, fresh_db):
        """Test listing files when project has files."""
        from ai.tools import FileTools
        import sqlite3
        
        conn = sqlite3.connect(fresh_db)
        cursor = conn.cursor()
        cursor.execute('''
            INSERT INTO users (username, pin_hash, role)
            VALUES (?, ?, ?)
        ''', ('testuser10', 'hash', 'kid'))
        user_id = cursor.lastrowid
        cursor.execute('''
            INSERT INTO projects (user_id, name, description, language)
            VALUES (?, ?, ?, ?)
        ''', (user_id, 'Test', 'Desc', 'p5js'))
        project_id = cursor.lastrowid
        
        # Add files
        for filename in ['a.txt', 'b.txt', 'c.txt']:
            cursor.execute('''
                INSERT INTO project_files (project_id, filename, content)
                VALUES (?, ?, ?)
            ''', (project_id, filename, f'Content of {filename}'))
        
        conn.commit()
        conn.close()
        
        tools = FileTools(project_id=project_id)
        result = tools.list_files()
        
        assert result['success'] is True
        assert result['count'] == 3
        filenames = [f['filename'] for f in result['files']]
        assert sorted(filenames) == ['a.txt', 'b.txt', 'c.txt']
    
    def test_list_files_sorted(self, fresh_db):
        """Test that files are returned sorted by filename."""
        from ai.tools import FileTools
        import sqlite3
        
        conn = sqlite3.connect(fresh_db)
        cursor = conn.cursor()
        cursor.execute('''
            INSERT INTO users (username, pin_hash, role)
            VALUES (?, ?, ?)
        ''', ('testuser11', 'hash', 'kid'))
        user_id = cursor.lastrowid
        cursor.execute('''
            INSERT INTO projects (user_id, name, description, language)
            VALUES (?, ?, ?, ?)
        ''', (user_id, 'Test', 'Desc', 'p5js'))
        project_id = cursor.lastrowid
        
        # Add files in reverse order
        for filename in ['z.txt', 'a.txt', 'm.txt']:
            cursor.execute('''
                INSERT INTO project_files (project_id, filename, content)
                VALUES (?, ?, ?)
            ''', (project_id, filename, 'content'))
        
        conn.commit()
        conn.close()
        
        tools = FileTools(project_id=project_id)
        result = tools.list_files()
        
        filenames = [f['filename'] for f in result['files']]
        assert filenames == sorted(filenames)


@pytest.mark.unit
class TestToolDefinitions:
    """Tests for tool definitions."""
    
    def test_get_tool_definitions(self):
        """Test getting tool definitions."""
        from ai.tools import FileTools
        
        tools = FileTools(project_id=1)
        definitions = tools.get_tool_definitions()
        
        assert isinstance(definitions, list)
        assert len(definitions) == 4
        
        # Check for required tools
        tool_names = [d['name'] for d in definitions]
        assert 'read_file' in tool_names
        assert 'write_file' in tool_names
        assert 'append_file' in tool_names
        assert 'list_files' in tool_names
    
    def test_tool_definitions_have_schema(self):
        """Test that tool definitions include input schema."""
        from ai.tools import FileTools
        
        tools = FileTools(project_id=1)
        definitions = tools.get_tool_definitions()
        
        for definition in definitions:
            assert 'name' in definition
            assert 'description' in definition
            assert 'input_schema' in definition
    
    def test_write_file_schema_has_required_fields(self):
        """Test write_file schema has required fields."""
        from ai.tools import FileTools
        
        tools = FileTools(project_id=1)
        definitions = tools.get_tool_definitions()
        
        write_file = next(d for d in definitions if d['name'] == 'write_file')
        required = write_file['input_schema'].get('required', [])
        
        assert 'filename' in required
        assert 'content' in required


@pytest.mark.unit
class TestExecuteTool:
    """Tests for execute_tool method."""
    
    def test_execute_read_file(self, fresh_db):
        """Test executing read_file tool."""
        from ai.tools import FileTools
        import sqlite3
        
        conn = sqlite3.connect(fresh_db)
        cursor = conn.cursor()
        cursor.execute('''
            INSERT INTO users (username, pin_hash, role)
            VALUES (?, ?, ?)
        ''', ('testuser12', 'hash', 'kid'))
        user_id = cursor.lastrowid
        cursor.execute('''
            INSERT INTO projects (user_id, name, description, language)
            VALUES (?, ?, ?, ?)
        ''', (user_id, 'Test', 'Desc', 'p5js'))
        project_id = cursor.lastrowid
        cursor.execute('''
            INSERT INTO project_files (project_id, filename, content)
            VALUES (?, ?, ?)
        ''', (project_id, 'exec.txt', 'test content'))
        conn.commit()
        conn.close()
        
        tools = FileTools(project_id=project_id)
        result = tools.execute_tool('read_file', {'filename': 'exec.txt'})
        
        assert result['success'] is True
        assert result['content'] == 'test content'
    
    def test_execute_write_file(self, fresh_db):
        """Test executing write_file tool."""
        from ai.tools import FileTools
        import sqlite3
        
        conn = sqlite3.connect(fresh_db)
        cursor = conn.cursor()
        cursor.execute('''
            INSERT INTO users (username, pin_hash, role)
            VALUES (?, ?, ?)
        ''', ('testuser13', 'hash', 'kid'))
        user_id = cursor.lastrowid
        cursor.execute('''
            INSERT INTO projects (user_id, name, description, language)
            VALUES (?, ?, ?, ?)
        ''', (user_id, 'Test', 'Desc', 'p5js'))
        project_id = cursor.lastrowid
        conn.commit()
        conn.close()
        
        tools = FileTools(project_id=project_id)
        result = tools.execute_tool('write_file', {
            'filename': 'toolwrite.txt',
            'content': 'written via tool'
        })
        
        assert result['success'] is True
        assert result['action'] == 'created'
    
    def test_reject_invalid_filename_on_write(self, fresh_db):
        """Code-like filenames should be rejected before they hit the DB."""
        from ai.tools import FileTools
        import sqlite3

        conn = sqlite3.connect(fresh_db)
        cursor = conn.cursor()
        cursor.execute('''
            INSERT INTO users (username, pin_hash, role)
            VALUES (?, ?, ?)
        ''', ('testuser_invalid', 'hash', 'kid'))
        user_id = cursor.lastrowid
        cursor.execute('''
            INSERT INTO projects (user_id, name, description, language)
            VALUES (?, ?, ?, ?)
        ''', (user_id, 'Test', 'Desc', 'p5js'))
        project_id = cursor.lastrowid
        conn.commit()
        conn.close()

        tools = FileTools(project_id=project_id)
        result = tools.write_file('circle(mouseX, mouseY, 48);', 'oops')

        assert result['success'] is False
        assert result['error'] == 'Invalid filename'

        conn = sqlite3.connect(fresh_db)
        cursor = conn.cursor()
        cursor.execute('SELECT COUNT(*) FROM project_files WHERE project_id = ?', (project_id,))
        count = cursor.fetchone()[0]
        conn.close()

        assert count == 0

    def test_execute_unknown_tool(self):
        """Test executing unknown tool returns error."""
        from ai.tools import FileTools
        
        tools = FileTools(project_id=1)
        result = tools.execute_tool('unknown_tool', {})
        
        assert result['success'] is False
        assert 'error' in result
        assert 'Unknown tool' in result['error']
