# tests/integration/test_api_projects.py - Project API integration tests
"""
Integration tests for project management API endpoints.

Tests cover:
- Project CRUD operations
- File management
- Version control
- Authorization checks
"""

import pytest
import json


@pytest.mark.integration
@pytest.mark.api
class TestListProjectsAPI:
    """Tests for listing projects."""
    
    def test_list_projects_empty(self, client, auth_headers):
        """Test listing projects when user has none."""
        response = client.get('/api/projects', headers=auth_headers)
        
        assert response.status_code == 200
        data = response.get_json()
        assert data['success'] is True
        assert data['projects'] == []
    
    def test_list_projects_with_data(self, client, auth_headers, project_factory):
        """Test listing projects with existing projects."""
        project_factory(name='Project 1')
        project_factory(name='Project 2')
        
        response = client.get('/api/projects', headers=auth_headers)
        
        assert response.status_code == 200
        data = response.get_json()
        assert data['success'] is True
        assert len(data['projects']) == 2
        
        names = [p['name'] for p in data['projects']]
        assert 'Project 1' in names
        assert 'Project 2' in names
    
    def test_list_projects_unauthorized(self, client):
        """Test listing projects without authentication."""
        response = client.get('/api/projects')
        
        assert response.status_code == 401
        assert response.get_json()['success'] is False
    
    def test_list_projects_only_own_projects(self, client, auth_headers, 
                                              test_user_factory, auth_headers_factory):
        """Test that users only see their own projects."""
        # Create another user with a project
        other_user = test_user_factory('otheruser', '9999')
        other_headers = auth_headers_factory(other_user['id'])
        
        # Other user creates a project
        client.post('/api/projects', headers=other_headers,
                   json={'name': 'Other Project', 'description': 'Not mine'})
        
        # Current user lists projects
        response = client.get('/api/projects', headers=auth_headers)
        
        assert response.status_code == 200
        projects = response.get_json()['projects']
        names = [p['name'] for p in projects]
        assert 'Other Project' not in names


@pytest.mark.integration
@pytest.mark.api
class TestCreateProjectAPI:
    """Tests for creating projects."""
    
    def test_create_project_success(self, client, auth_headers):
        """Test successful project creation."""
        response = client.post('/api/projects', headers=auth_headers,
                              json={'name': 'My Game', 'description': 'A cool game'})
        
        assert response.status_code == 201
        data = response.get_json()
        assert data['success'] is True
        assert 'project' in data
        assert data['project']['name'] == 'My Game'
        assert data['project']['description'] == 'A cool game'
        assert 'id' in data['project']
    
    def test_create_project_minimal(self, client, auth_headers):
        """Test creating project with just a name."""
        response = client.post('/api/projects', headers=auth_headers,
                              json={'name': 'Minimal'})
        
        assert response.status_code == 201
        assert response.get_json()['project']['name'] == 'Minimal'
    
    def test_create_project_missing_name(self, client, auth_headers):
        """Test creating project without name."""
        response = client.post('/api/projects', headers=auth_headers,
                              json={'description': 'No name'})
        
        assert response.status_code == 400
        data = response.get_json()
        assert data['success'] is False
        assert 'name is required' in data['error'].lower()
    
    def test_create_project_empty_name(self, client, auth_headers):
        """Test creating project with empty name."""
        response = client.post('/api/projects', headers=auth_headers,
                              json={'name': '   '})
        
        assert response.status_code == 400
        assert response.get_json()['success'] is False
    
    def test_create_project_name_too_long(self, client, auth_headers):
        """Test creating project with name over 100 characters."""
        response = client.post('/api/projects', headers=auth_headers,
                              json={'name': 'A' * 101})
        
        assert response.status_code == 400
        assert response.get_json()['success'] is False
    
    def test_create_project_with_language(self, client, auth_headers):
        """Test creating project with language specified."""
        response = client.post('/api/projects', headers=auth_headers,
                              json={'name': 'Python Project', 'language': 'python'})
        
        assert response.status_code == 201
        assert response.get_json()['project']['language'] == 'python'
    
    def test_create_project_unauthorized(self, client):
        """Test creating project without authentication."""
        response = client.post('/api/projects',
                              json={'name': 'Test'})
        
        assert response.status_code == 401


@pytest.mark.integration
@pytest.mark.api
class TestGetProjectAPI:
    """Tests for getting single project."""
    
    def test_get_project_success(self, client, auth_headers, project_factory):
        """Test getting project details."""
        project = project_factory(name='Test Project')
        
        response = client.get(f'/api/projects/{project["id"]}', headers=auth_headers)
        
        assert response.status_code == 200
        data = response.get_json()
        assert data['success'] is True
        assert data['project']['name'] == 'Test Project'
        assert 'conversations' in data
        assert 'files' in data
    
    def test_get_project_not_found(self, client, auth_headers):
        """Test getting non-existent project."""
        response = client.get('/api/projects/99999', headers=auth_headers)
        
        assert response.status_code == 404
        data = response.get_json()
        assert data['success'] is False
        assert 'not found' in data['error'].lower()
    
    def test_get_other_users_project(self, client, test_user_factory, auth_headers_factory):
        """Test that users can't access others' projects."""
        # Create another user and their project
        other_user = test_user_factory('projectowner', '9999')
        other_headers = auth_headers_factory(other_user['id'])
        
        response = client.post('/api/projects', headers=other_headers,
                              json={'name': 'Private Project'})
        project_id = response.get_json()['project']['id']
        
        # Create a different user
        different_user = test_user_factory('intruder', '8888')
        intruder_headers = auth_headers_factory(different_user['id'])
        
        # Try to access the project
        response = client.get(f'/api/projects/{project_id}', headers=intruder_headers)
        
        assert response.status_code == 404  # Should not reveal existence

    def test_get_project_uses_authoritative_project_files_for_current_code(self, client, auth_headers, project_factory, db_path):
        """Project loads should heal stale current_code from project_files."""
        import sqlite3

        project = project_factory(language='html')
        project_id = project['id']

        conn = sqlite3.connect(db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        cursor.execute('UPDATE projects SET current_code = ? WHERE id = ?', ('stale code', project_id))
        cursor.execute('''
            INSERT INTO project_files (project_id, filename, content)
            VALUES (?, ?, ?)
        ''', (project_id, 'index.html', '<html><body>Fresh</body></html>'))
        conn.commit()
        conn.close()

        response = client.get(f'/api/projects/{project_id}', headers=auth_headers)

        assert response.status_code == 200
        data = response.get_json()
        assert data['project']['current_code'] == '<html><body>Fresh</body></html>'


@pytest.mark.integration
@pytest.mark.api
class TestUpdateProjectAPI:
    """Tests for updating projects."""
    
    def test_update_project_name(self, client, auth_headers, project_factory):
        """Test updating project name."""
        project = project_factory(name='Old Name')
        
        response = client.put(f'/api/projects/{project["id"]}', headers=auth_headers,
                             json={'name': 'New Name'})
        
        assert response.status_code == 200
        data = response.get_json()
        assert data['project']['name'] == 'New Name'
    
    def test_update_project_description(self, client, auth_headers, project_factory):
        """Test updating project description."""
        project = project_factory(name='Test', description='Old desc')
        
        response = client.put(f'/api/projects/{project["id"]}', headers=auth_headers,
                             json={'description': 'New description'})
        
        assert response.status_code == 200
        assert response.get_json()['project']['description'] == 'New description'
    
    def test_update_project_no_fields(self, client, auth_headers, project_factory):
        """Test update with no fields to update."""
        project = project_factory()
        
        response = client.put(f'/api/projects/{project["id"]}', headers=auth_headers,
                             json={})
        
        assert response.status_code == 400
        assert response.get_json()['success'] is False
    
    def test_update_project_not_found(self, client, auth_headers):
        """Test updating non-existent project."""
        response = client.put('/api/projects/99999', headers=auth_headers,
                             json={'name': 'New Name'})
        
        assert response.status_code == 404


@pytest.mark.integration
@pytest.mark.api
class TestDeleteProjectAPI:
    """Tests for deleting projects."""
    
    def test_delete_project_success(self, client, auth_headers, project_factory):
        """Test successful project deletion."""
        project = project_factory()
        
        response = client.delete(f'/api/projects/{project["id"]}', headers=auth_headers)
        
        assert response.status_code == 200
        assert response.get_json()['success'] is True
        
        # Verify project is gone
        response = client.get(f'/api/projects/{project["id"]}', headers=auth_headers)
        assert response.status_code == 404
    
    def test_delete_project_cascades(self, client, auth_headers, project_factory, db_path):
        """Test that deleting project removes related data."""
        import sqlite3
        
        project = project_factory()
        project_id = project['id']
        
        # Add conversation
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        cursor.execute('''
            INSERT INTO conversations (project_id, role, content)
            VALUES (?, ?, ?)
        ''', (project_id, 'user', 'Test message'))
        conn.commit()
        conn.close()
        
        # Delete project
        client.delete(f'/api/projects/{project_id}', headers=auth_headers)
        
        # Verify conversation is gone
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        cursor.execute('SELECT * FROM conversations WHERE project_id = ?', (project_id,))
        assert cursor.fetchone() is None
        conn.close()
    
    def test_delete_project_not_found(self, client, auth_headers):
        """Test deleting non-existent project."""
        response = client.delete('/api/projects/99999', headers=auth_headers)
        
        assert response.status_code == 404


@pytest.mark.integration
@pytest.mark.api
class TestProjectVersionsAPI:
    """Tests for project version control."""
    
    def test_save_version_success(self, client, auth_headers, project_factory, db_path):
        """Test saving a code version."""
        import sqlite3
        
        project = project_factory()
        project_id = project['id']
        
        # Set some code in the project
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        cursor.execute('''
            UPDATE projects SET current_code = ? WHERE id = ?
        ''', ('function setup() {}', project_id))
        conn.commit()
        conn.close()
        
        response = client.post(f'/api/projects/{project_id}/versions', headers=auth_headers,
                              json={'description': 'Initial version'})
        
        assert response.status_code == 200
        data = response.get_json()
        assert data['success'] is True
        assert 'version_id' in data
        assert data['description'] == 'Initial version'
    
    def test_save_version_no_code(self, client, auth_headers, project_factory):
        """Test saving version when project has no code."""
        project = project_factory()
        project_id = project['id']
        
        response = client.post(f'/api/projects/{project_id}/versions', headers=auth_headers,
                              json={'description': 'Empty'})
        
        assert response.status_code == 400
        assert response.get_json()['success'] is False
    
    def test_list_versions(self, client, auth_headers, project_factory, db_path):
        """Test listing saved versions."""
        import sqlite3
        
        project = project_factory()
        project_id = project['id']
        
        # Create versions directly in DB
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        cursor.execute('''
            INSERT INTO code_versions (project_id, code, description)
            VALUES (?, ?, ?)
        ''', (project_id, 'code1', 'Version 1'))
        cursor.execute('''
            INSERT INTO code_versions (project_id, code, description)
            VALUES (?, ?, ?)
        ''', (project_id, 'code2', 'Version 2'))
        conn.commit()
        conn.close()
        
        response = client.get(f'/api/projects/{project_id}/versions', headers=auth_headers)
        
        assert response.status_code == 200
        data = response.get_json()
        assert len(data['versions']) == 2
    
    def test_get_version(self, client, auth_headers, project_factory, db_path):
        """Test getting a specific version."""
        import sqlite3
        
        project = project_factory()
        project_id = project['id']
        
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        cursor.execute('''
            INSERT INTO code_versions (project_id, code, description)
            VALUES (?, ?, ?)
        ''', (project_id, 'saved code', 'Saved version'))
        version_id = cursor.lastrowid
        conn.commit()
        conn.close()
        
        response = client.get(f'/api/projects/{project_id}/versions/{version_id}',
                             headers=auth_headers)
        
        assert response.status_code == 200
        data = response.get_json()
        assert data['version']['code'] == 'saved code'


@pytest.mark.integration
@pytest.mark.api
class TestProjectFilesAPI:
    """Tests for project file management."""
    
    def test_default_files_created(self, client, auth_headers):
        """Test that default files are created with new project."""
        response = client.post('/api/projects', headers=auth_headers,
                              json={'name': 'File Test'})
        
        project_id = response.get_json()['project']['id']
        
        # Get project and check files
        response = client.get(f'/api/projects/{project_id}', headers=auth_headers)
        files = response.get_json()['files']
        
        filenames = [f['filename'] for f in files]
        assert 'design.md' in filenames
        assert 'architecture.md' in filenames
        assert 'todo.md' in filenames
        assert 'notes.md' in filenames

    def test_creating_first_primary_code_file_syncs_project_current_code(self, client, auth_headers, project_factory, db_path):
        """Creating the first primary code file should seed projects.current_code."""
        import sqlite3

        project = project_factory(language='html')
        project_id = project['id']

        response = client.post(
            f'/api/projects/{project_id}/files',
            headers=auth_headers,
            json={'filename': 'index.html', 'content': '<html><body>Created</body></html>'}
        )

        assert response.status_code == 201
        data = response.get_json()
        assert data['success'] is True
        assert data['file']['filename'] == 'index.html'

        conn = sqlite3.connect(db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        cursor.execute('SELECT current_code FROM projects WHERE id = ?', (project_id,))
        row = cursor.fetchone()
        conn.close()

        assert row['current_code'] == '<html><body>Created</body></html>'

    def test_nested_index_file_can_become_primary_current_code(self, client, auth_headers, project_factory, db_path):
        """Nested index files should still seed current_code when they are the best HTML entry candidate."""
        import sqlite3

        project = project_factory(language='html')
        project_id = project['id']

        response = client.post(
            f'/api/projects/{project_id}/files',
            headers=auth_headers,
            json={'filename': 'pages/index.html', 'content': '<html><body>Nested entry</body></html>'}
        )

        assert response.status_code == 201
        assert response.get_json()['file']['filename'] == 'pages/index.html'

        conn = sqlite3.connect(db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        cursor.execute('SELECT current_code FROM projects WHERE id = ?', (project_id,))
        row = cursor.fetchone()
        conn.close()

        assert row['current_code'] == '<html><body>Nested entry</body></html>'

    def test_updating_primary_code_file_syncs_project_current_code(self, client, auth_headers, project_factory, db_path):
        """File edits should keep projects.current_code aligned with the primary file."""
        import sqlite3

        project = project_factory(language='p5js')
        project_id = project['id']

        conn = sqlite3.connect(db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        cursor.execute('UPDATE projects SET current_code = ? WHERE id = ?', ('old code', project_id))
        cursor.execute('''
            INSERT INTO project_files (project_id, filename, content)
            VALUES (?, ?, ?)
        ''', (project_id, 'sketch.js', 'function setup() {}'))
        conn.commit()
        conn.close()

        response = client.put(
            f'/api/projects/{project_id}/files/sketch.js',
            headers=auth_headers,
            json={'content': 'function draw() { ellipse(10, 10, 10, 10); }'}
        )

        assert response.status_code == 200

        conn = sqlite3.connect(db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        cursor.execute('SELECT current_code FROM projects WHERE id = ?', (project_id,))
        row = cursor.fetchone()
        conn.close()

        assert 'ellipse' in row['current_code']

    def test_updating_file_by_id_returns_saved_content_and_syncs_current_code(self, client, auth_headers, project_factory, db_path):
        """The direct file update endpoint should return saved content and refresh current_code."""
        import sqlite3

        project = project_factory(language='html')
        project_id = project['id']

        conn = sqlite3.connect(db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        cursor.execute('UPDATE projects SET current_code = ? WHERE id = ?', ('stale code', project_id))
        cursor.execute('''
            INSERT INTO project_files (project_id, filename, content)
            VALUES (?, ?, ?)
        ''', (project_id, 'index.html', '<html><body>Old</body></html>'))
        file_id = cursor.lastrowid
        conn.commit()
        conn.close()

        response = client.put(
            f'/api/files/{file_id}',
            headers=auth_headers,
            json={'content': '<html><body>Saved from modal</body></html>'}
        )

        assert response.status_code == 200
        data = response.get_json()
        assert data['success'] is True
        assert data['file']['id'] == file_id
        assert data['file']['content'] == '<html><body>Saved from modal</body></html>'

        conn = sqlite3.connect(db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        cursor.execute('SELECT current_code FROM projects WHERE id = ?', (project_id,))
        row = cursor.fetchone()
        conn.close()

        assert row['current_code'] == '<html><body>Saved from modal</body></html>'

    def test_renaming_file_by_id_updates_filename_and_keeps_current_code_synced(self, client, auth_headers, project_factory, db_path):
        """Renaming a file should update the filename without losing primary code state."""
        import sqlite3

        project = project_factory(language='html')
        project_id = project['id']

        conn = sqlite3.connect(db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        cursor.execute('''
            INSERT INTO project_files (project_id, filename, content)
            VALUES (?, ?, ?)
        ''', (project_id, 'index.html', '<html><body>Rename me</body></html>'))
        file_id = cursor.lastrowid
        conn.commit()
        conn.close()

        response = client.put(
            f'/api/files/{file_id}/rename',
            headers=auth_headers,
            json={'filename': 'page.html'}
        )

        assert response.status_code == 200
        data = response.get_json()
        assert data['success'] is True
        assert data['file']['filename'] == 'page.html'

        conn = sqlite3.connect(db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        cursor.execute('SELECT current_code FROM projects WHERE id = ?', (project_id,))
        row = cursor.fetchone()
        conn.close()

        assert row['current_code'] == '<html><body>Rename me</body></html>'

    def test_get_and_update_file_by_nested_path(self, client, auth_headers, project_factory):
        """Nested file paths should work through the filename-based API routes."""
        project = project_factory(language='html')
        project_id = project['id']

        put_response = client.put(
            f'/api/projects/{project_id}/files/js/player.js',
            headers=auth_headers,
            json={'content': 'export const speed = 3;'}
        )
        assert put_response.status_code == 200
        assert put_response.get_json()['file']['filename'] == 'js/player.js'

        get_response = client.get(
            f'/api/projects/{project_id}/files/js/player.js',
            headers=auth_headers,
        )
        assert get_response.status_code == 200
        assert get_response.get_json()['file']['content'] == 'export const speed = 3;'

    def test_deleting_primary_code_file_clears_current_code(self, client, auth_headers, project_factory, db_path):
        """Deleting the only primary code file should clear projects.current_code."""
        import sqlite3

        project = project_factory(language='html')
        project_id = project['id']

        conn = sqlite3.connect(db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        cursor.execute('''
            INSERT INTO project_files (project_id, filename, content)
            VALUES (?, ?, ?)
        ''', (project_id, 'index.html', '<html><body>Delete me</body></html>'))
        file_id = cursor.lastrowid
        conn.commit()
        conn.close()

        response = client.delete(
            f'/api/files/{file_id}',
            headers=auth_headers
        )

        assert response.status_code == 200
        assert response.get_json()['success'] is True

        conn = sqlite3.connect(db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        cursor.execute('SELECT current_code FROM projects WHERE id = ?', (project_id,))
        row = cursor.fetchone()
        conn.close()

        assert row['current_code'] == ''
