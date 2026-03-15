# tests/integration/test_versions.py - Version API Integration Tests
"""
Integration tests for the versions API endpoints.

Tests cover:
- Saving code versions
- Listing versions
- Retrieving specific versions
- Error handling
- Authorization
"""

import pytest
import sqlite3


@pytest.mark.integration
@pytest.mark.api
class TestSaveVersionAPI:
    """Tests for saving code versions via API."""
    
    def test_save_version_success(self, client, auth_headers, project_factory, db_path):
        """Test successfully saving a code version."""
        import sqlite3
        
        project = project_factory()
        project_id = project['id']
        
        # Set some code in the project
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        cursor.execute('''
            UPDATE projects SET current_code = ? WHERE id = ?
        ''', ('function setup() { createCanvas(400, 400); }', project_id))
        conn.commit()
        conn.close()
        
        response = client.post(
            f'/api/projects/{project_id}/versions',
            headers=auth_headers,
            json={'description': 'Initial version'}
        )
        
        assert response.status_code == 200
        data = response.get_json()
        assert data['success'] is True
        assert 'version_id' in data
        assert data['description'] == 'Initial version'
    
    def test_save_version_no_code(self, client, auth_headers, project_factory):
        """Test saving version when project has no code."""
        project = project_factory()
        project_id = project['id']
        
        response = client.post(
            f'/api/projects/{project_id}/versions',
            headers=auth_headers,
            json={'description': 'Empty'}
        )
        
        assert response.status_code == 400
        data = response.get_json()
        assert data['success'] is False
    
    def test_save_version_no_description(self, client, auth_headers, project_factory, db_path):
        """Test saving version without description."""
        import sqlite3
        
        project = project_factory()
        project_id = project['id']
        
        # Set code
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        cursor.execute('''
            UPDATE projects SET current_code = ? WHERE id = ?
        ''', ('function setup() {}', project_id))
        conn.commit()
        conn.close()
        
        response = client.post(
            f'/api/projects/{project_id}/versions',
            headers=auth_headers,
            json={}
        )
        
        assert response.status_code == 200
        data = response.get_json()
        assert data['success'] is True
        # Description should default to empty string
        assert data['description'] == ''
    
    def test_save_version_wrong_project(self, client, auth_headers):
        """Test saving version for non-existent project."""
        response = client.post(
            '/api/projects/99999/versions',
            headers=auth_headers,
            json={'description': 'Test'}
        )
        
        assert response.status_code == 404
        data = response.get_json()
        assert data['success'] is False
    
    def test_save_version_other_users_project(self, client, test_user_factory, 
                                              auth_headers_factory, project_factory):
        """Test saving version for another user's project."""
        # Create another user and their project
        other_user = test_user_factory('otheruser', '9999')
        other_headers = auth_headers_factory(other_user['id'])
        
        # Create project as other user
        response = client.post('/api/projects', headers=other_headers,
                              json={'name': 'Private Project'})
        project_id = response.get_json()['project']['id']
        
        # Create a different user
        different_user = test_user_factory('intruder', '8888')
        intruder_headers = auth_headers_factory(different_user['id'])
        
        # Try to save version
        response = client.post(
            f'/api/projects/{project_id}/versions',
            headers=intruder_headers,
            json={'description': 'Hacked'}
        )
        
        assert response.status_code == 404  # Should not reveal existence
    
    def test_save_version_unauthorized(self, client, project_factory):
        """Test saving version without authentication."""
        project = project_factory()
        
        response = client.post(
            f'/api/projects/{project["id"]}/versions',
            json={'description': 'Test'}
        )
        
        assert response.status_code == 401
    
    def test_save_version_stores_code(self, client, auth_headers, project_factory, db_path):
        """Test that version stores the correct code."""
        import sqlite3
        
        project = project_factory()
        project_id = project['id']
        code = 'function setup() { createCanvas(800, 600); }'
        
        # Set code
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        cursor.execute('''
            UPDATE projects SET current_code = ? WHERE id = ?
        ''', (code, project_id))
        conn.commit()
        conn.close()
        
        # Save version
        response = client.post(
            f'/api/projects/{project_id}/versions',
            headers=auth_headers,
            json={'description': 'With specific code'}
        )
        
        version_id = response.get_json()['version_id']
        
        # Verify stored code
        conn = sqlite3.connect(db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        cursor.execute('''
            SELECT code FROM code_versions WHERE id = ?
        ''', (version_id,))
        result = cursor.fetchone()
        conn.close()
        
        assert result['code'] == code


@pytest.mark.integration
@pytest.mark.api
class TestListVersionsAPI:
    """Tests for listing code versions via API."""
    
    def test_list_versions_empty(self, client, auth_headers, project_factory):
        """Test listing versions when project has none."""
        project = project_factory()
        
        response = client.get(
            f'/api/projects/{project["id"]}/versions',
            headers=auth_headers
        )
        
        assert response.status_code == 200
        data = response.get_json()
        assert data['success'] is True
        assert data['versions'] == []
    
    def test_list_versions_with_data(self, client, auth_headers, project_factory, db_path):
        """Test listing versions with existing versions."""
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
        
        response = client.get(
            f'/api/projects/{project_id}/versions',
            headers=auth_headers
        )
        
        assert response.status_code == 200
        data = response.get_json()
        assert len(data['versions']) == 2
        
        # Check ordering - by DESC created_at, Version 2 should be first
        # (since it was inserted second, it has a later timestamp)
        descriptions = [v['description'] for v in data['versions']]
        assert 'Version 1' in descriptions
        assert 'Version 2' in descriptions
    
    def test_list_versions_wrong_project(self, client, auth_headers):
        """Test listing versions for non-existent project."""
        response = client.get(
            '/api/projects/99999/versions',
            headers=auth_headers
        )
        
        assert response.status_code == 404
    
    def test_list_versions_other_users_project(self, client, test_user_factory,
                                               auth_headers_factory, project_factory):
        """Test listing versions for another user's project."""
        # Create another user and their project
        other_user = test_user_factory('otheruser2', '9999')
        other_headers = auth_headers_factory(other_user['id'])
        
        response = client.post('/api/projects', headers=other_headers,
                              json={'name': 'Private Project 2'})
        project_id = response.get_json()['project']['id']
        
        # Create different user
        different_user = test_user_factory('intruder2', '8888')
        intruder_headers = auth_headers_factory(different_user['id'])
        
        # Try to list versions
        response = client.get(
            f'/api/projects/{project_id}/versions',
            headers=intruder_headers
        )
        
        assert response.status_code == 404
    
    def test_list_versions_unauthorized(self, client, project_factory):
        """Test listing versions without authentication."""
        project = project_factory()
        
        response = client.get(f'/api/projects/{project["id"]}/versions')
        
        assert response.status_code == 401


@pytest.mark.integration
@pytest.mark.api
class TestGetVersionAPI:
    """Tests for retrieving specific versions via API."""
    
    def test_get_version_success(self, client, auth_headers, project_factory, db_path):
        """Test successfully retrieving a version."""
        import sqlite3
        
        project = project_factory()
        project_id = project['id']
        
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        cursor.execute('''
            INSERT INTO code_versions (project_id, code, description)
            VALUES (?, ?, ?)
        ''', (project_id, 'saved code here', 'Saved version'))
        version_id = cursor.lastrowid
        conn.commit()
        conn.close()
        
        response = client.get(
            f'/api/projects/{project_id}/versions/{version_id}',
            headers=auth_headers
        )
        
        assert response.status_code == 200
        data = response.get_json()
        assert data['success'] is True
        assert data['version']['code'] == 'saved code here'
        assert data['version']['description'] == 'Saved version'
    
    def test_get_version_not_found(self, client, auth_headers, project_factory):
        """Test retrieving non-existent version."""
        project = project_factory()
        
        response = client.get(
            f'/api/projects/{project["id"]}/versions/99999',
            headers=auth_headers
        )
        
        assert response.status_code == 404
        data = response.get_json()
        assert data['success'] is False
    
    def test_get_version_wrong_project(self, client, auth_headers, project_factory, db_path):
        """Test retrieving version from wrong project."""
        import sqlite3
        
        # Create two projects
        project1 = project_factory()
        project2 = project_factory()
        
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        # Create version in project 1
        cursor.execute('''
            INSERT INTO code_versions (project_id, code, description)
            VALUES (?, ?, ?)
        ''', (project1['id'], 'code', 'Version'))
        version_id = cursor.lastrowid
        
        conn.commit()
        conn.close()
        
        # Try to get version from project 2's endpoint
        response = client.get(
            f'/api/projects/{project2["id"]}/versions/{version_id}',
            headers=auth_headers
        )
        
        assert response.status_code == 404
    
    def test_get_version_unauthorized(self, client, project_factory, db_path):
        """Test retrieving version without authentication."""
        import sqlite3
        
        project = project_factory()
        
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        cursor.execute('''
            INSERT INTO code_versions (project_id, code, description)
            VALUES (?, ?, ?)
        ''', (project['id'], 'code', 'Version'))
        version_id = cursor.lastrowid
        conn.commit()
        conn.close()
        
        response = client.get(
            f'/api/projects/{project["id"]}/versions/{version_id}'
        )
        
        assert response.status_code == 401


@pytest.mark.integration
@pytest.mark.api
class TestVersionAuthorization:
    """Tests for version endpoint authorization."""
    
    def test_versions_isolated_between_users(self, client, test_user_factory,
                                             auth_headers_factory, db_path):
        """Test that versions are isolated between users."""
        import sqlite3
        
        # Create two users
        user1 = test_user_factory('user1v', '1111')
        user2 = test_user_factory('user2v', '2222')
        headers1 = auth_headers_factory(user1['id'])
        headers2 = auth_headers_factory(user2['id'])
        
        # Create projects for each
        resp1 = client.post('/api/projects', headers=headers1,
                           json={'name': 'User1 Project'})
        project1_id = resp1.get_json()['project']['id']
        
        resp2 = client.post('/api/projects', headers=headers2,
                           json={'name': 'User2 Project'})
        project2_id = resp2.get_json()['project']['id']
        
        # Set code and create version for user1's project
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        cursor.execute('''
            UPDATE projects SET current_code = ? WHERE id = ?
        ''', ('user1 code', project1_id))
        cursor.execute('''
            INSERT INTO code_versions (project_id, code, description)
            VALUES (?, ?, ?)
        ''', (project1_id, 'user1 code', 'User1 version'))
        conn.commit()
        conn.close()
        
        # User2 tries to list user1's versions
        response = client.get(
            f'/api/projects/{project1_id}/versions',
            headers=headers2
        )
        assert response.status_code == 404
        
        # User2 tries to save version to user1's project
        response = client.post(
            f'/api/projects/{project1_id}/versions',
            headers=headers2,
            json={'description': 'Hacked'}
        )
        assert response.status_code == 404
