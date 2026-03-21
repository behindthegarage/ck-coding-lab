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

import json
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

    def test_save_version_prefers_project_files_snapshot_for_multifile_projects(self, client, auth_headers, project_factory, db_path):
        """Multi-file saves should snapshot project_files even if current_code is stale."""
        import sqlite3
        import json

        project = project_factory(language='html')
        project_id = project['id']

        conn = sqlite3.connect(db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        cursor.execute('UPDATE projects SET current_code = ? WHERE id = ?', ('stale code', project_id))
        cursor.execute('''
            INSERT INTO project_files (project_id, filename, content)
            VALUES (?, ?, ?)
        ''', (project_id, 'index.html', '<html><body>Hello</body></html>'))
        cursor.execute('''
            INSERT INTO project_files (project_id, filename, content)
            VALUES (?, ?, ?)
        ''', (project_id, 'main.js', 'console.log("hello")'))
        conn.commit()

        response = client.post(
            f'/api/projects/{project_id}/versions',
            headers=auth_headers,
            json={'description': 'Multifile snapshot'}
        )

        assert response.status_code == 200
        version_id = response.get_json()['version_id']

        cursor.execute('''
            SELECT code, files_snapshot, entry_filename
            FROM code_versions
            WHERE id = ?
        ''', (version_id,))
        result = cursor.fetchone()
        conn.close()

        files_snapshot = json.loads(result['files_snapshot'])
        assert result['code'] == '<html><body>Hello</body></html>'
        assert result['entry_filename'] == 'index.html'
        assert files_snapshot['index.html'] == '<html><body>Hello</body></html>'
        assert files_snapshot['main.js'] == 'console.log("hello")'


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
            INSERT INTO code_versions (project_id, code, description, files_snapshot, entry_filename)
            VALUES (?, ?, ?, ?, ?)
        ''', (
            project_id,
            'code1',
            'Version 1',
            json.dumps({'index.html': '<html></html>'}),
            'index.html'
        ))
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

        version_by_description = {v['description']: v for v in data['versions']}
        assert version_by_description['Version 1']['entry_filename'] == 'index.html'
        assert version_by_description['Version 1']['has_files_snapshot'] == 1
        assert version_by_description['Version 1']['file_count'] == 1
        assert version_by_description['Version 1']['code_size'] == len('code1')
        assert version_by_description['Version 1']['matches_live_state'] is False
        assert version_by_description['Version 1']['is_recovery'] is False
        assert version_by_description['Version 1']['version_type'] == 'manual'
        assert version_by_description['Version 1']['recovery_reason'] is None
        assert version_by_description['Version 1']['checkpoint_kind'] == 'manual'
        assert version_by_description['Version 1']['checkpoint_label'] == 'Save point'
        assert version_by_description['Version 1']['display_description'] == 'Version 1'
        assert version_by_description['Version 2']['has_files_snapshot'] == 0
        assert version_by_description['Version 2']['entry_filename'] == 'sketch.js'
        assert version_by_description['Version 2']['file_count'] == 1
        assert version_by_description['Version 2']['code_size'] == len('code2')
        assert version_by_description['Version 2']['matches_live_state'] is False
        assert version_by_description['Version 2']['is_recovery'] is False
        assert version_by_description['Version 2']['version_type'] == 'manual'
        assert version_by_description['Version 2']['recovery_reason'] is None
        assert version_by_description['Version 2']['checkpoint_kind'] == 'manual'
        assert version_by_description['Version 2']['checkpoint_label'] == 'Save point'
        assert version_by_description['Version 2']['display_description'] == 'Version 2'

    def test_list_versions_marks_live_project_checkpoint(self, client, auth_headers, project_factory, db_path):
        """Listing versions should identify which save matches the current project state."""
        project = project_factory(language='html')
        project_id = project['id']

        live_files = {
            'index.html': '<html><body>live</body></html>',
            'main.js': 'console.log("live")',
        }
        old_files = {
            'index.html': '<html><body>old</body></html>',
            'main.js': 'console.log("old")',
        }

        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        cursor.execute('UPDATE projects SET current_code = ? WHERE id = ?', (live_files['index.html'], project_id))
        cursor.executemany(
            'INSERT INTO project_files (project_id, filename, content) VALUES (?, ?, ?)',
            [(project_id, filename, content) for filename, content in live_files.items()]
        )
        cursor.execute('''
            INSERT INTO code_versions (project_id, code, description, files_snapshot, entry_filename)
            VALUES (?, ?, ?, ?, ?)
        ''', (
            project_id,
            old_files['index.html'],
            'Old checkpoint',
            json.dumps(old_files),
            'index.html'
        ))
        cursor.execute('''
            INSERT INTO code_versions (project_id, code, description, files_snapshot, entry_filename)
            VALUES (?, ?, ?, ?, ?)
        ''', (
            project_id,
            live_files['index.html'],
            'Current checkpoint',
            json.dumps(live_files),
            'index.html'
        ))
        conn.commit()
        conn.close()

        response = client.get(
            f'/api/projects/{project_id}/versions',
            headers=auth_headers
        )

        assert response.status_code == 200
        versions = response.get_json()['versions']
        version_by_description = {v['description']: v for v in versions}

        assert version_by_description['Current checkpoint']['matches_live_state'] is True
        assert version_by_description['Current checkpoint']['file_count'] == 2
        assert version_by_description['Current checkpoint']['entry_filename'] == 'index.html'
        assert version_by_description['Old checkpoint']['matches_live_state'] is False
        assert version_by_description['Old checkpoint']['file_count'] == 2



    def test_list_versions_includes_recovery_metadata(self, client, auth_headers, project_factory, db_path):
        """Recovery checkpoints should be labeled distinctly from manual saves."""
        project = project_factory(language='html')
        project_id = project['id']

        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        cursor.execute(
            '''
            INSERT INTO code_versions (project_id, code, description, files_snapshot, entry_filename)
            VALUES (?, ?, ?, ?, ?)
        ''',
            (
                project_id,
                '<html><body>Recovered</body></html>',
                '__ckcl_recovery__:After AI update',
                json.dumps({'index.html': '<html><body>Recovered</body></html>'}),
                'index.html',
            ),
        )
        conn.commit()
        conn.close()

        response = client.get(
            f'/api/projects/{project_id}/versions',
            headers=auth_headers,
        )

        assert response.status_code == 200
        version = response.get_json()['versions'][0]
        assert version['is_recovery'] is True
        assert version['version_type'] == 'recovery'
        assert version['recovery_reason'] == 'After AI update'
        assert version['checkpoint_kind'] == 'recovery'
        assert version['checkpoint_label'] == 'Automatic checkpoint'
        assert version['description'] == '__ckcl_recovery__:After AI update'

    def test_list_versions_can_seed_baseline_recovery_when_history_is_opened(self, client, auth_headers, db_path):
        """Opening history can lazily backfill a baseline recovery checkpoint for older work."""
        create_response = client.post(
            '/api/projects',
            headers=auth_headers,
            json={'name': 'Pitfall', 'language': 'html'},
        )
        project_id = create_response.get_json()['project']['id']

        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        cursor.execute(
            "UPDATE projects SET created_at = '2026-03-18 12:00:00', updated_at = '2026-03-20 15:00:00' WHERE id = ?",
            (project_id,),
        )
        cursor.execute(
            "UPDATE project_files SET updated_at = '2026-03-20 15:00:00' WHERE project_id = ? AND filename = 'index.html'",
            (project_id,),
        )
        conn.commit()
        conn.close()

        response = client.get(
            f'/api/projects/{project_id}/versions',
            headers=auth_headers,
        )

        assert response.status_code == 200
        data = response.get_json()
        assert data['created_baseline_recovery'] is True
        assert data['baseline_recovery_version_id'] is not None
        assert len(data['versions']) == 1
        assert data['versions'][0]['is_recovery'] is True
        assert data['versions'][0]['version_type'] == 'recovery'
        assert data['versions'][0]['recovery_reason'] == 'Current project when version history was first opened'
        assert data['versions'][0]['checkpoint_origin'] == 'baseline'
        assert data['versions'][0]['matches_live_state'] is True

    def test_list_versions_does_not_seed_recovery_for_fresh_starter_project(self, client, auth_headers):
        """Fresh starter projects should not get a synthetic checkpoint just from opening history."""
        create_response = client.post(
            '/api/projects',
            headers=auth_headers,
            json={'name': 'Fresh Starter', 'language': 'html'},
        )
        project_id = create_response.get_json()['project']['id']

        response = client.get(
            f'/api/projects/{project_id}/versions',
            headers=auth_headers,
        )

        assert response.status_code == 200
        data = response.get_json()
        assert data['created_baseline_recovery'] is False
        assert data['baseline_recovery_version_id'] is None
        assert data['versions'] == []

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
        assert data['version']['files'] == {'sketch.js': 'saved code here'}
        assert data['version']['entry_filename'] == 'sketch.js'
        assert data['version']['checkpoint_kind'] == 'manual'
        assert data['version']['checkpoint_label'] == 'Save point'

    def test_get_version_exposes_recovery_checkpoint_metadata(self, client, auth_headers, project_factory, db_path):
        """Version retrieval should expose recovery metadata without making the UI parse prefixes."""
        project = project_factory(language='html')
        project_id = project['id']

        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        cursor.execute(
            '''
            INSERT INTO code_versions (project_id, code, description, files_snapshot, entry_filename)
            VALUES (?, ?, ?, ?, ?)
            ''',
            (
                project_id,
                '<html><body>Recovered</body></html>',
                '__ckcl_recovery__:After AI update',
                json.dumps({'index.html': '<html><body>Recovered</body></html>'}),
                'index.html',
            ),
        )
        version_id = cursor.lastrowid
        conn.commit()
        conn.close()

        response = client.get(
            f'/api/projects/{project_id}/versions/{version_id}',
            headers=auth_headers,
        )

        assert response.status_code == 200
        version = response.get_json()['version']
        assert version['checkpoint_kind'] == 'recovery'
        assert version['checkpoint_label'] == 'Automatic checkpoint'
        assert version['checkpoint_detail'] == 'After AI update'
        assert version['display_description'] == 'Automatic checkpoint'

    def test_get_version_returns_stored_file_snapshot(self, client, auth_headers, project_factory, db_path):
        """Version retrieval should include the saved multi-file snapshot."""
        import sqlite3
        import json

        project = project_factory(language='html')
        project_id = project['id']

        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        cursor.execute('''
            INSERT INTO code_versions (project_id, code, description, files_snapshot, entry_filename)
            VALUES (?, ?, ?, ?, ?)
        ''', (
            project_id,
            '<html></html>',
            'Saved html version',
            json.dumps({'index.html': '<html></html>', 'main.js': 'console.log(1)'}),
            'index.html'
        ))
        version_id = cursor.lastrowid
        conn.commit()
        conn.close()

        response = client.get(
            f'/api/projects/{project_id}/versions/{version_id}',
            headers=auth_headers
        )

        assert response.status_code == 200
        version = response.get_json()['version']
        assert version['entry_filename'] == 'index.html'
        assert version['files']['index.html'] == '<html></html>'
        assert version['files']['main.js'] == 'console.log(1)'
    
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
class TestRestoreVersionAPI:
    """Tests for restoring saved versions into live project state."""

    def test_restore_version_replaces_multifile_project_state_from_snapshot(self, client, auth_headers, project_factory, db_path):
        """Restore should replace project_files from files_snapshot and heal current_code."""
        project = project_factory(language='html')
        project_id = project['id']

        conn = sqlite3.connect(db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()

        cursor.execute('UPDATE projects SET current_code = ? WHERE id = ?', ('stale current code', project_id))
        cursor.execute('''
            INSERT INTO project_files (project_id, filename, content)
            VALUES (?, ?, ?)
        ''', (project_id, 'index.html', '<html><body>old</body></html>'))
        cursor.execute('''
            INSERT INTO project_files (project_id, filename, content)
            VALUES (?, ?, ?)
        ''', (project_id, 'notes.md', 'old note that should disappear'))

        snapshot = {
            'index.html': '<html><body>restored</body></html>',
            'main.js': 'console.log("restored")',
            'styles.css': 'body { background: black; }',
        }
        cursor.execute('''
            INSERT INTO code_versions (project_id, code, description, files_snapshot, entry_filename)
            VALUES (?, ?, ?, ?, ?)
        ''', (
            project_id,
            'stale version code that should be ignored',
            'Restore point',
            json.dumps(snapshot, sort_keys=True),
            'index.html'
        ))
        version_id = cursor.lastrowid
        conn.commit()

        response = client.post(
            f'/api/projects/{project_id}/versions/{version_id}/restore',
            headers=auth_headers,
        )

        assert response.status_code == 200
        data = response.get_json()
        assert data['success'] is True
        assert data['entry_filename'] == 'index.html'
        assert data['restored_files_count'] == 3

        cursor.execute(
            'SELECT filename, content FROM project_files WHERE project_id = ? ORDER BY filename',
            (project_id,)
        )
        files = {row['filename']: row['content'] for row in cursor.fetchall()}
        cursor.execute('SELECT current_code FROM projects WHERE id = ?', (project_id,))
        project_row = cursor.fetchone()
        conn.close()

        assert files == {
            'index.html': '<html><body>restored</body></html>',
            'main.js': 'console.log("restored")',
            'styles.css': 'body { background: black; }',
        }
        assert project_row['current_code'] == '<html><body>restored</body></html>'

    def test_restore_version_legacy_single_file_rebuilds_live_project_files(self, client, auth_headers, project_factory, db_path):
        """Legacy versions with only code should restore into a single authoritative file."""
        project = project_factory(language='p5js')
        project_id = project['id']

        conn = sqlite3.connect(db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        cursor.execute('UPDATE projects SET current_code = ? WHERE id = ?', ('stale current code', project_id))
        cursor.execute('''
            INSERT INTO project_files (project_id, filename, content)
            VALUES (?, ?, ?)
        ''', (project_id, 'main.js', 'console.log("old")'))
        cursor.execute('''
            INSERT INTO project_files (project_id, filename, content)
            VALUES (?, ?, ?)
        ''', (project_id, 'design.md', '# old design'))
        cursor.execute('''
            INSERT INTO code_versions (project_id, code, description)
            VALUES (?, ?, ?)
        ''', (project_id, 'function draw() { circle(50, 50, 25); }', 'Legacy restore point'))
        version_id = cursor.lastrowid
        conn.commit()

        response = client.post(
            f'/api/projects/{project_id}/versions/{version_id}/restore',
            headers=auth_headers,
        )

        assert response.status_code == 200
        data = response.get_json()
        assert data['success'] is True
        assert data['entry_filename'] == 'sketch.js'
        assert data['restored_files_count'] == 1

        cursor.execute(
            'SELECT filename, content FROM project_files WHERE project_id = ? ORDER BY filename',
            (project_id,)
        )
        files = {row['filename']: row['content'] for row in cursor.fetchall()}
        cursor.execute('SELECT current_code FROM projects WHERE id = ?', (project_id,))
        project_row = cursor.fetchone()
        conn.close()

        assert files == {'sketch.js': 'function draw() { circle(50, 50, 25); }'}
        assert project_row['current_code'] == 'function draw() { circle(50, 50, 25); }'

    def test_restore_version_wrong_project_returns_not_found(self, client, auth_headers, project_factory, db_path):
        """A version cannot be restored through another project's endpoint."""
        project1 = project_factory(language='html')
        project2 = project_factory(language='html')

        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        cursor.execute('''
            INSERT INTO code_versions (project_id, code, description)
            VALUES (?, ?, ?)
        ''', (project1['id'], '<html>one</html>', 'Project 1 version'))
        version_id = cursor.lastrowid
        conn.commit()
        conn.close()

        response = client.post(
            f'/api/projects/{project2["id"]}/versions/{version_id}/restore',
            headers=auth_headers,
        )

        assert response.status_code == 404
        assert response.get_json()['success'] is False

    def test_restore_version_unauthorized(self, client, project_factory, db_path):
        """Restore should require authentication."""
        project = project_factory(language='html')

        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        cursor.execute('''
            INSERT INTO code_versions (project_id, code, description)
            VALUES (?, ?, ?)
        ''', (project['id'], '<html>saved</html>', 'Saved version'))
        version_id = cursor.lastrowid
        conn.commit()
        conn.close()

        response = client.post(f'/api/projects/{project["id"]}/versions/{version_id}/restore')

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
        version_id = cursor.lastrowid
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

        # User2 tries to restore user1's version
        response = client.post(
            f'/api/projects/{project1_id}/versions/{version_id}/restore',
            headers=headers2,
        )
        assert response.status_code == 404
