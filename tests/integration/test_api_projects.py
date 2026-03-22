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

    def test_create_project_rejects_description_longer_than_1000_characters(self, client, auth_headers):
        """Create should enforce the same description limit the onboarding UI expects."""
        response = client.post('/api/projects', headers=auth_headers,
                              json={'name': 'Too wordy', 'description': 'A' * 1001})

        assert response.status_code == 400
        data = response.get_json()
        assert data['success'] is False
        assert 'description' in data['error'].lower()

    @pytest.mark.parametrize(
        ('language', 'starter_filename', 'starter_snippet'),
        [
            ('p5js', 'sketch.js', 'function setup()'),
            ('html', 'index.html', '<!DOCTYPE html>'),
            ('python', 'main.py', 'Welcome to your first Python project!'),
        ],
    )
    def test_create_project_seeds_runnable_starter_file(self, client, auth_headers, language, starter_filename, starter_snippet):
        """New projects should open with a friendly starter file instead of a blank editor."""
        response = client.post(
            '/api/projects',
            headers=auth_headers,
            json={
                'name': f'{language} starter',
                'description': 'Help me get going fast',
                'language': language,
            },
        )

        assert response.status_code == 201
        project = response.get_json()['project']
        assert project['language'] == language
        assert starter_snippet in (project.get('current_code') or '')

        project_response = client.get(f"/api/projects/{project['id']}", headers=auth_headers)
        assert project_response.status_code == 200
        files = project_response.get_json()['files']
        filenames = [file['filename'] for file in files]

        assert starter_filename in filenames
        assert 'todo.md' in filenames
    
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

    def test_get_project_sanitizes_legacy_assistant_markup_in_conversation_history(self, client, auth_headers, project_factory, db_path):
        """Legacy tool-call sludge should not leak back into workspace chat history."""
        import sqlite3

        project = project_factory(name='Legacy Transcript Project')

        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        cursor.execute(
            '''
                INSERT INTO conversations (project_id, role, content)
                VALUES (?, 'assistant', ?)
            ''',
            (
                project['id'],
                "I'll work through it. <|tool_calls_section_begin|> <|tool_call_begin|> functions.write_file:1 <|tool_call_argument_begin|> {\"filename\": \"index.html\"} <|tool_call_end|> <|tool_calls_section_end|>\n\n## Questions for you\n- Want sound next?",
            ),
        )
        conn.commit()
        conn.close()

        response = client.get(f'/api/projects/{project["id"]}', headers=auth_headers)

        assert response.status_code == 200
        data = response.get_json()
        assistant_messages = [msg for msg in data['conversations'] if msg['role'] == 'assistant']
        assert assistant_messages
        content = assistant_messages[-1]['content']
        assert '<|tool_calls_section_begin|>' not in content
        assert 'functions.write_file:1' not in content
        assert '## Questions for you' in content

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

    def test_update_project_non_json_request_returns_400_instead_of_500(self, client, auth_headers, project_factory):
        """Malformed update payloads should fail cleanly instead of crashing the onboarding flow."""
        project = project_factory()

        response = client.put(
            f'/api/projects/{project["id"]}',
            headers=auth_headers,
            data='name=Broken payload',
            content_type='application/x-www-form-urlencoded'
        )

        assert response.status_code == 400
        data = response.get_json()
        assert data['success'] is False
        assert 'no fields to update' in data['error'].lower()
    
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

    def test_bulk_reseed_restores_missing_starter_files_without_duplicating_existing_ones(self, client, auth_headers):
        """Starter reseeding should heal partially-empty projects instead of crashing or duplicating files."""
        create_response = client.post(
            '/api/projects',
            headers=auth_headers,
            json={'name': 'Starter Recovery', 'language': 'html'}
        )
        assert create_response.status_code == 201
        project_id = create_response.get_json()['project']['id']

        project_response = client.get(f'/api/projects/{project_id}', headers=auth_headers)
        files = project_response.get_json()['files']
        files_by_name = {file['filename']: file['id'] for file in files}

        delete_index = client.delete(f"/api/files/{files_by_name['index.html']}", headers=auth_headers)
        delete_notes = client.delete(f"/api/files/{files_by_name['notes.md']}", headers=auth_headers)
        assert delete_index.status_code == 200
        assert delete_notes.status_code == 200

        reseed_response = client.post(f'/api/projects/{project_id}/files/bulk', headers=auth_headers)

        assert reseed_response.status_code == 200
        reseed_data = reseed_response.get_json()
        assert reseed_data['success'] is True
        assert reseed_data['created_count'] == 2
        assert sorted(reseed_data['created']) == ['index.html', 'notes.md']

        healed_project = client.get(f'/api/projects/{project_id}', headers=auth_headers).get_json()
        healed_filenames = [file['filename'] for file in healed_project['files']]
        assert 'index.html' in healed_filenames
        assert 'notes.md' in healed_filenames
        assert '<!DOCTYPE html>' in healed_project['project']['current_code']

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

    def test_preview_bundle_returns_resolved_entry_filename_for_nested_html_projects(self, client, auth_headers, project_factory):
        """Preview bundle should identify the actual HTML entry file, even when it is nested."""
        project = project_factory(language='html')
        project_id = project['id']

        entry_response = client.put(
            f'/api/projects/{project_id}/files/pages/index.html',
            headers=auth_headers,
            json={'content': '<html><body><script src="../main.js"></script></body></html>'}
        )
        assert entry_response.status_code == 200

        script_response = client.put(
            f'/api/projects/{project_id}/files/main.js',
            headers=auth_headers,
            json={'content': 'console.log("nested entry");'}
        )
        assert script_response.status_code == 200

        bundle_response = client.get(
            f'/api/projects/{project_id}/preview-bundle',
            headers=auth_headers,
        )
        assert bundle_response.status_code == 200
        data = bundle_response.get_json()
        assert data['success'] is True
        assert data['entry_filename'] == 'pages/index.html'
        assert data['files']['pages/index.html'] == '<html><body><script src="../main.js"></script></body></html>'
        assert data['files']['main.js'] == 'console.log("nested entry");'

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

    def test_delete_file_returns_deleted_file_payload_for_undo(self, client, auth_headers, project_factory, db_path):
        """Deleting a file should return enough data for the UI to offer an immediate undo."""
        import sqlite3

        project = project_factory(language='html')
        project_id = project['id']

        conn = sqlite3.connect(db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        cursor.execute('''
            INSERT INTO project_files (project_id, filename, content)
            VALUES (?, ?, ?)
        ''', (project_id, 'notes.md', '# Keep me safe'))
        file_id = cursor.lastrowid
        conn.commit()
        conn.close()

        response = client.delete(
            f'/api/files/{file_id}',
            headers=auth_headers
        )

        assert response.status_code == 200
        data = response.get_json()
        assert data['success'] is True
        assert data['deleted_file']['id'] == file_id
        assert data['deleted_file']['project_id'] == project_id
        assert data['deleted_file']['filename'] == 'notes.md'
        assert data['deleted_file']['content'] == '# Keep me safe'


@pytest.mark.integration
@pytest.mark.api
class TestProjectOversightAndRecoveryAPI:
    """Teacher/admin oversight and recovery flows should stay safe and useful."""

    def test_admin_list_projects_scope_all_includes_metadata_and_latest_review(
        self,
        client,
        admin_auth_headers,
        test_user_factory,
        auth_headers_factory,
        db_path,
    ):
        import sqlite3

        kid = test_user_factory('kiddo', '1111', role='kid')
        kid_headers = auth_headers_factory(kid['id'])
        create_response = client.post(
            '/api/projects',
            headers=kid_headers,
            json={'name': 'Volcano Lab', 'description': 'Simulate eruptions', 'language': 'html'},
        )
        project_id = create_response.get_json()['project']['id']

        conn = sqlite3.connect(db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        cursor.execute(
            '''
            INSERT INTO conversations (project_id, role, content)
            VALUES (?, 'user', ?)
            ''',
            (project_id, 'Please fix the eruption button and save a review.'),
        )
        cursor.execute(
            '''
            INSERT INTO conversations (project_id, role, content)
            VALUES (?, 'assistant', ?)
            ''',
            (
                project_id,
                'Updated the project.\n\n## Review\n### `index.html`\n- Action: Updated\n- Summary: 3 added\n```diff\n+ button fixed\n```',
            ),
        )
        cursor.execute(
            '''
            INSERT INTO code_versions (project_id, code, description)
            VALUES (?, ?, ?)
            ''',
            (project_id, '<html><body>Ready</body></html>', 'Teacher checkpoint'),
        )
        conn.commit()
        conn.close()

        response = client.get('/api/projects?scope=all', headers=admin_auth_headers)

        assert response.status_code == 200
        data = response.get_json()
        assert data['success'] is True
        assert data['scope'] == 'all'

        project = next(item for item in data['projects'] if item['id'] == project_id)
        assert project['owner_username'] == 'kiddo'
        assert project['file_count'] >= 5
        assert project['version_count'] == 1
        assert project['conversation_count'] == 2
        assert project['latest_review']['headline'] == 'index.html • 3 added'
        assert project['latest_user_message_preview'].startswith('Please fix the eruption button')
        assert project['needs_attention'] is False
        assert project['health_level'] == 'healthy'
        assert project['health']['label'] == 'Healthy'


    def test_recent_runnable_project_without_manual_save_is_not_flagged(self, client, auth_headers):
        create_response = client.post(
            '/api/projects',
            headers=auth_headers,
            json={'name': 'Fresh Starter', 'language': 'html'},
        )
        project_id = create_response.get_json()['project']['id']

        response = client.get('/api/projects', headers=auth_headers)

        assert response.status_code == 200
        project = next(item for item in response.get_json()['projects'] if item['id'] == project_id)
        assert project['version_count'] == 0
        assert project['recovery_version_count'] == 0
        assert project['needs_attention'] is False
        assert project['attention_reasons'] == []

    def test_stale_doc_first_kickoff_is_not_flagged_as_needing_attention(self, client, auth_headers, db_path):
        import sqlite3

        create_response = client.post(
            '/api/projects',
            headers=auth_headers,
            json={'name': 'Planning Maze', 'language': 'html'},
        )
        project_id = create_response.get_json()['project']['id']

        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        cursor.execute("DELETE FROM project_files WHERE project_id = ? AND filename = 'index.html'", (project_id,))
        cursor.execute("UPDATE projects SET current_code = '', created_at = '2026-03-18 12:00:00', updated_at = '2026-03-20 15:00:00' WHERE id = ?", (project_id,))
        cursor.execute("UPDATE project_files SET updated_at = '2026-03-20 15:00:00' WHERE project_id = ?", (project_id,))
        cursor.execute(
            "INSERT INTO conversations (project_id, role, content, created_at) VALUES (?, 'user', ?, '2026-03-20 14:00:00')",
            (project_id, 'I want a spooky maze game with stars and a timer.'),
        )
        cursor.execute(
            "INSERT INTO conversations (project_id, role, content, created_at) VALUES (?, 'assistant', ?, '2026-03-20 14:05:00')",
            (project_id, 'I wrote the plan into design.md and todo.md.'),
        )
        conn.commit()
        conn.close()

        response = client.get('/api/projects', headers=auth_headers)

        assert response.status_code == 200
        project = next(item for item in response.get_json()['projects'] if item['id'] == project_id)
        assert project['doc_file_count'] >= 2
        assert project['code_file_count'] == 0
        assert project['needs_attention'] is False
        assert project['attention_reasons'] == []

    def test_project_list_sanitizes_assistant_preview(self, client, auth_headers, project_factory, db_path):
        import sqlite3

        project = project_factory(name='Legacy Preview Project')

        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        cursor.execute(
            "INSERT INTO conversations (project_id, role, content) VALUES (?, 'assistant', ?)",
            (
                project['id'],
                "I'll fix it. <|tool_calls_section_begin|> functions.write_file:1 <|tool_calls_section_end|>\n\n## Questions for you\n- Want sound next?",
            ),
        )
        conn.commit()
        conn.close()

        response = client.get('/api/projects', headers=auth_headers)

        assert response.status_code == 200
        listed = next(item for item in response.get_json()['projects'] if item['id'] == project['id'])
        assert '<|tool_calls_section_begin|>' not in listed['latest_assistant_preview']
        assert 'functions.write_file:1' not in listed['latest_assistant_preview']
        assert 'Questions for you' in listed['latest_assistant_preview']

    def test_stale_unsaved_progress_is_flagged_without_checkpoint(self, client, auth_headers, db_path):
        import sqlite3

        create_response = client.post(
            '/api/projects',
            headers=auth_headers,
            json={'name': 'Unsaved Volcano', 'language': 'html'},
        )
        project_id = create_response.get_json()['project']['id']

        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        cursor.execute(
            "UPDATE projects SET created_at = '2026-03-18 12:00:00', updated_at = '2026-03-19 15:00:00' WHERE id = ?",
            (project_id,),
        )
        cursor.execute(
            "UPDATE project_files SET updated_at = '2026-03-19 15:00:00' WHERE project_id = ?",
            (project_id,),
        )
        conn.commit()
        conn.close()

        response = client.get('/api/projects', headers=auth_headers)

        assert response.status_code == 200
        project = next(item for item in response.get_json()['projects'] if item['id'] == project_id)
        assert project['version_count'] == 0
        assert project['recovery_version_count'] == 0
        assert project['needs_attention'] is True
        assert project['health_level'] == 'risky'
        assert 'Progress has no save or recovery point yet' in project['attention_reasons']

    def test_doc_first_project_gets_planning_health_without_attention(self, client, auth_headers, db_path):
        import sqlite3

        create_response = client.post(
            '/api/projects',
            headers=auth_headers,
            json={'name': 'Planning Health Project', 'language': 'html'},
        )
        project_id = create_response.get_json()['project']['id']

        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        cursor.execute("DELETE FROM project_files WHERE project_id = ? AND filename = 'index.html'", (project_id,))
        cursor.execute("UPDATE projects SET current_code = '', created_at = '2026-03-18 12:00:00', updated_at = '2026-03-20 15:00:00' WHERE id = ?", (project_id,))
        cursor.execute("UPDATE project_files SET updated_at = '2026-03-20 15:00:00' WHERE project_id = ?", (project_id,))
        cursor.execute(
            "INSERT INTO conversations (project_id, role, content, created_at) VALUES (?, 'user', ?, '2026-03-20 14:00:00')",
            (project_id, 'I want to map out the game before coding it.'),
        )
        cursor.execute(
            "INSERT INTO conversations (project_id, role, content, created_at) VALUES (?, 'assistant', ?, '2026-03-20 14:05:00')",
            (project_id, 'I wrote the plan into design.md and todo.md.'),
        )
        conn.commit()
        conn.close()

        response = client.get('/api/projects', headers=auth_headers)

        assert response.status_code == 200
        project = next(item for item in response.get_json()['projects'] if item['id'] == project_id)
        assert project['needs_attention'] is False
        assert project['health_level'] == 'planning'
        assert project['health']['label'] == 'Planning'

    def test_hidden_recovery_checkpoint_counts_as_protection_without_inflating_save_points(self, client, auth_headers, db_path):
        import sqlite3

        create_response = client.post(
            '/api/projects',
            headers=auth_headers,
            json={'name': 'Recovered Robot', 'language': 'html'},
        )
        project_id = create_response.get_json()['project']['id']

        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        cursor.execute(
            "UPDATE projects SET created_at = '2026-03-18 12:00:00', updated_at = '2026-03-20 16:00:00' WHERE id = ?",
            (project_id,),
        )
        cursor.execute(
            "UPDATE project_files SET updated_at = '2026-03-20 15:00:00' WHERE project_id = ? AND filename = 'index.html'",
            (project_id,),
        )
        cursor.execute(
            '''
            INSERT INTO code_versions (project_id, code, description, files_snapshot, entry_filename, created_at)
            VALUES (?, ?, ?, ?, ?, ?)
            ''',
            (
                project_id,
                '<!DOCTYPE html><html><body>Recovered</body></html>',
                '__ckcl_recovery__:After AI update',
                '{"index.html": "<!DOCTYPE html><html><body>Recovered</body></html>"}',
                'index.html',
                '2026-03-20 16:00:00',
            ),
        )
        conn.commit()
        conn.close()

        response = client.get('/api/projects', headers=auth_headers)

        assert response.status_code == 200
        project = next(item for item in response.get_json()['projects'] if item['id'] == project_id)
        assert project['version_count'] == 0
        assert project['recovery_version_count'] == 1
        assert project['needs_attention'] is False
        assert project['attention_reasons'] == []

    def test_kid_scope_all_request_still_only_returns_own_projects(
        self,
        client,
        auth_headers,
        test_user_factory,
        auth_headers_factory,
    ):
        other_user = test_user_factory('someoneelse', '2222', role='kid')
        other_headers = auth_headers_factory(other_user['id'])
        client.post('/api/projects', headers=other_headers, json={'name': 'Other kid project'})
        client.post('/api/projects', headers=auth_headers, json={'name': 'My own project'})

        response = client.get('/api/projects?scope=all', headers=auth_headers)

        assert response.status_code == 200
        data = response.get_json()
        assert data['scope'] == 'mine'
        names = [project['name'] for project in data['projects']]
        assert 'My own project' in names
        assert 'Other kid project' not in names

    def test_admin_can_open_other_users_project_detail(self, client, admin_auth_headers, test_user_factory, auth_headers_factory):
        kid = test_user_factory('builderkid', '3333', role='kid')
        kid_headers = auth_headers_factory(kid['id'])
        create_response = client.post('/api/projects', headers=kid_headers, json={'name': 'Bridge Builder', 'language': 'p5js'})
        project_id = create_response.get_json()['project']['id']

        response = client.get(f'/api/projects/{project_id}', headers=admin_auth_headers)

        assert response.status_code == 200
        data = response.get_json()
        assert data['project']['name'] == 'Bridge Builder'
        assert data['project']['owner_username'] == 'builderkid'
        assert data['project']['can_administer'] is True
        assert len(data['files']) >= 5

    def test_duplicate_project_copies_live_files_and_version_history(self, client, auth_headers, db_path):
        import sqlite3

        create_response = client.post(
            '/api/projects',
            headers=auth_headers,
            json={'name': 'Maze Quest', 'description': 'Original run', 'language': 'python'},
        )
        original = create_response.get_json()['project']
        project_id = original['id']

        conn = sqlite3.connect(db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        cursor.execute(
            '''
            UPDATE project_files
            SET content = ?
            WHERE project_id = ? AND filename = 'main.py'
            ''',
            ('print("clone me")', project_id),
        )
        cursor.execute(
            '''
            INSERT INTO code_versions (project_id, code, description, entry_filename)
            VALUES (?, ?, ?, ?)
            ''',
            (project_id, 'print("versioned")', 'Checkpoint', 'main.py'),
        )
        conn.commit()
        conn.close()

        duplicate_response = client.post(
            f'/api/projects/{project_id}/duplicate',
            headers=auth_headers,
            json={'name': 'Maze Quest Safe Copy'},
        )

        assert duplicate_response.status_code == 201
        duplicate_data = duplicate_response.get_json()
        duplicate_id = duplicate_data['project']['id']
        assert duplicate_id != project_id
        assert duplicate_data['project']['name'] == 'Maze Quest Safe Copy'
        assert duplicate_data['copied_versions'] == 1
        assert duplicate_data['copied_files'] >= 5

        duplicate_project = client.get(f'/api/projects/{duplicate_id}', headers=auth_headers).get_json()
        duplicate_versions = client.get(f'/api/projects/{duplicate_id}/versions', headers=auth_headers).get_json()

        filenames = [file['filename'] for file in duplicate_project['files']]
        assert 'main.py' in filenames
        assert duplicate_project['project']['current_code'] == 'print("clone me")'
        assert len(duplicate_versions['versions']) == 1
        assert duplicate_versions['versions'][0]['description'] == 'Checkpoint'

    def test_archive_project_toggles_archived_state(self, client, auth_headers):
        create_response = client.post('/api/projects', headers=auth_headers, json={'name': 'Shelf Project'})
        project_id = create_response.get_json()['project']['id']

        archive_response = client.post(
            f'/api/projects/{project_id}/archive',
            headers=auth_headers,
            json={'archived': True},
        )
        assert archive_response.status_code == 200
        assert archive_response.get_json()['project']['is_archived'] is True

        restore_response = client.post(
            f'/api/projects/{project_id}/archive',
            headers=auth_headers,
            json={'archived': False},
        )
        assert restore_response.status_code == 200
        assert restore_response.get_json()['project']['is_archived'] is False

    def test_reset_project_reseeds_starter_files_and_creates_hidden_recovery_version(self, client, auth_headers, db_path):
        import sqlite3

        create_response = client.post(
            '/api/projects',
            headers=auth_headers,
            json={'name': 'Restartable Web', 'description': 'Needs a clean slate', 'language': 'html'},
        )
        project_id = create_response.get_json()['project']['id']

        conn = sqlite3.connect(db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        cursor.execute(
            '''
            UPDATE project_files
            SET content = ?
            WHERE project_id = ? AND filename = 'index.html'
            ''',
            ('<html><body>Before reset</body></html>', project_id),
        )
        cursor.execute(
            '''
            INSERT INTO project_files (project_id, filename, content)
            VALUES (?, ?, ?)
            ''',
            (project_id, 'scratch.txt', 'temporary notes'),
        )
        conn.commit()
        conn.close()

        reset_response = client.post(f'/api/projects/{project_id}/reset', headers=auth_headers)

        assert reset_response.status_code == 200
        reset_data = reset_response.get_json()
        assert reset_data['success'] is True
        assert reset_data['recovery_version_id'] is not None
        assert 'index.html' in reset_data['created_files']

        project_response = client.get(f'/api/projects/{project_id}', headers=auth_headers)
        versions_response = client.get(f'/api/projects/{project_id}/versions', headers=auth_headers)

        files = [file['filename'] for file in project_response.get_json()['files']]
        assert 'scratch.txt' not in files
        assert 'index.html' in files
        assert '<!DOCTYPE html>' in project_response.get_json()['project']['current_code']

        recovery_descriptions = [version['description'] for version in versions_response.get_json()['versions']]
        assert any(description.startswith('__ckcl_recovery__:Before reset to starter') for description in recovery_descriptions)

    def test_admin_can_access_other_users_file_and_version_endpoints(self, client, admin_auth_headers, test_user_factory, auth_headers_factory):
        kid = test_user_factory('filekid', '4444', role='kid')
        kid_headers = auth_headers_factory(kid['id'])
        create_response = client.post('/api/projects', headers=kid_headers, json={'name': 'Teacher Peek', 'language': 'python'})
        project_id = create_response.get_json()['project']['id']

        save_response = client.post(
            f'/api/projects/{project_id}/versions',
            headers=kid_headers,
            json={'description': 'Checkpoint one'},
        )
        assert save_response.status_code == 200

        files_response = client.get(f'/api/projects/{project_id}/files', headers=admin_auth_headers)
        versions_response = client.get(f'/api/projects/{project_id}/versions', headers=admin_auth_headers)
        preview_response = client.get(f'/api/projects/{project_id}/preview-bundle', headers=admin_auth_headers)

        assert files_response.status_code == 200
        assert versions_response.status_code == 200
        assert preview_response.status_code == 200
        assert any(file['filename'] == 'main.py' for file in files_response.get_json()['files'])
        assert versions_response.get_json()['versions'][0]['description'] == 'Checkpoint one'
        assert preview_response.get_json()['entry_filename'] == 'main.py'
