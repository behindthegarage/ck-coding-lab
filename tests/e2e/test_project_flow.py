"""
E2E Test: Project Collaboration Flow
tests/e2e/test_project_flow.py

Tests the complete project lifecycle:
Create → Update → Multiple chats → List versions → Delete
"""

import pytest
from .helpers import (
    register_user,
    login_user,
    create_project,
    send_chat,
    save_version,
    get_project,
    update_project,
    list_projects,
    list_versions,
    delete_project,
    generate_unique_username
)


@pytest.mark.e2e
class TestProjectLifecycle:
    """End-to-end tests for complete project lifecycle."""
    
    def test_project_lifecycle(self, client):
        """
        Test complete project lifecycle flow.
        
        Flow:
        1. Create a new project
        2. Update project details
        3. Have multiple chat interactions
        4. Save versions at key points
        5. List all versions
        6. Delete the project
        """
        # Setup: Create user
        username = generate_unique_username('lifecycle')
        pin = '1234'
        register_user(client, username, pin)
        token = login_user(client, username, pin)
        
        # Step 1: Create Project
        project = create_project(
            client, token,
            name='Lifecycle Test Project',
            language='p5js',
            description='Testing the full project lifecycle'
        )
        project_id = project['id']
        assert project['name'] == 'Lifecycle Test Project'
        
        # Step 2: Update Project
        updated = update_project(
            client, token, project_id,
            name='Updated Project Name',
            description='Updated description after creation'
        )
        assert updated['name'] == 'Updated Project Name'
        assert updated['description'] == 'Updated description after creation'
        
        # Step 3: Multiple Chat Interactions
        chat_messages = [
            'Create a canvas with size 400x400',
            'Add a bouncing ball',
            'Make the ball change color on bounce'
        ]
        
        for message in chat_messages:
            response = send_chat(client, token, project_id, message)
            assert 'code' in response
        
        # Step 4: Save Versions at Key Points
        versions_to_save = [
            'v1 - Initial canvas setup',
            'v2 - Added bouncing ball',
            'v3 - Color changing effects'
        ]
        
        saved_versions = []
        for desc in versions_to_save:
            version = save_version(client, token, project_id, desc)
            saved_versions.append(version)
            assert 'version_id' in version
        
        # Step 5: List All Versions
        versions = list_versions(client, token, project_id)
        assert len(versions) == 3
        
        # Verify version descriptions
        version_descriptions = [v['description'] for v in versions]
        for desc in versions_to_save:
            assert desc in version_descriptions
        
        # Step 6: Delete Project
        delete_project(client, token, project_id)
        
        # Verify deletion by trying to get project
        headers = {'Authorization': f'Bearer {token}'}
        response = client.get(f'/api/projects/{project_id}', headers=headers)
        assert response.status_code == 404
    
    def test_project_update_only_name(self, client):
        """Test updating only the project name."""
        username = generate_unique_username('update_name')
        register_user(client, username, '1234')
        token = login_user(client, username, '1234')
        
        project = create_project(client, token, name='Original Name', description='Desc')
        
        updated = update_project(
            client, token, project['id'],
            name='New Name Only'
        )
        
        assert updated['name'] == 'New Name Only'
        assert updated['description'] == 'Desc'  # Unchanged
    
    def test_project_update_only_description(self, client):
        """Test updating only the project description."""
        username = generate_unique_username('update_desc')
        register_user(client, username, '1234')
        token = login_user(client, username, '1234')
        
        project = create_project(client, token, name='Name', description='Original Desc')
        
        updated = update_project(
            client, token, project['id'],
            description='New Description Only'
        )
        
        assert updated['name'] == 'Name'  # Unchanged
        assert updated['description'] == 'New Description Only'
    
    def test_multiple_projects_isolation(self, client):
        """Test that multiple projects are properly isolated."""
        username = generate_unique_username('isolation')
        register_user(client, username, '1234')
        token = login_user(client, username, '1234')
        
        # Create multiple projects
        project1 = create_project(client, token, name='Project One', language='p5js')
        project2 = create_project(client, token, name='Project Two', language='python')
        project3 = create_project(client, token, name='Project Three', language='p5js')
        
        # Add chat to each project
        send_chat(client, token, project1['id'], 'Create a canvas for project 1')
        send_chat(client, token, project2['id'], 'Create a canvas for project 2')
        send_chat(client, token, project3['id'], 'Create a canvas for project 3')
        
        # Save version in each
        save_version(client, token, project1['id'], 'v1 - Project One')
        save_version(client, token, project2['id'], 'v1 - Project Two')
        save_version(client, token, project3['id'], 'v1 - Project Three')
        
        # List all projects
        projects = list_projects(client, token)
        assert len(projects) == 3
        
        # Verify each project has its own versions
        for project in [project1, project2, project3]:
            versions = list_versions(client, token, project['id'])
            assert len(versions) == 1
            assert project['name'] in versions[0]['description']
    
    def test_project_deletion_cascades_data(self, client, db_path):
        """Test that deleting a project removes all related data."""
        import sqlite3
        
        username = generate_unique_username('cascade')
        register_user(client, username, '1234')
        token = login_user(client, username, '1234')
        
        project = create_project(client, token, name='Cascade Test')
        project_id = project['id']
        
        # Add chat messages (creates conversations)
        send_chat(client, token, project_id, 'Message 1')
        send_chat(client, token, project_id, 'Message 2')
        
        # Save a version
        save_version(client, token, project_id, 'Version to be deleted')
        
        # Delete the project
        delete_project(client, token, project_id)
        
        # Verify conversations are deleted
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        cursor.execute(
            'SELECT COUNT(*) FROM conversations WHERE project_id = ?',
            (project_id,)
        )
        conv_count = cursor.fetchone()[0]
        
        # Verify versions are deleted
        cursor.execute(
            'SELECT COUNT(*) FROM code_versions WHERE project_id = ?',
            (project_id,)
        )
        version_count = cursor.fetchone()[0]
        
        # Verify project files are deleted
        cursor.execute(
            'SELECT COUNT(*) FROM project_files WHERE project_id = ?',
            (project_id,)
        )
        file_count = cursor.fetchone()[0]
        
        conn.close()
        
        assert conv_count == 0
        assert version_count == 0
        assert file_count == 0
    
    def test_chat_with_multiple_messages(self, client):
        """Test that multiple chat messages can be sent successfully."""
        username = generate_unique_username('history')
        register_user(client, username, '1234')
        token = login_user(client, username, '1234')
        
        project = create_project(client, token, name='History Test')
        project_id = project['id']
        
        # Send multiple messages - all should succeed
        messages = ['First message', 'Second message', 'Third message']
        for msg in messages:
            response = send_chat(client, token, project_id, msg)
            assert 'code' in response
            assert 'explanation' in response
        
        # Verify we can still interact with the project
        project_data = get_project(client, token, project_id)
        assert project_data['id'] == project_id
    
    def test_version_retrieval(self, client):
        """Test that saved versions can be retrieved correctly."""
        username = generate_unique_username('retrieve')
        register_user(client, username, '1234')
        token = login_user(client, username, '1234')
        
        project = create_project(client, token, name='Retrieve Test')
        project_id = project['id']
        
        # Generate code and save version
        send_chat(client, token, project_id, 'Create a canvas')
        version = save_version(client, token, project_id, 'Retrievable version')
        version_id = version['version_id']
        
        # Retrieve specific version
        headers = {'Authorization': f'Bearer {token}'}
        response = client.get(
            f'/api/projects/{project_id}/versions/{version_id}',
            headers=headers
        )
        
        assert response.status_code == 200
        data = response.get_json()
        assert data['version']['description'] == 'Retrievable version'
        assert 'code' in data['version']
