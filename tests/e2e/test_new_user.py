"""
E2E Test: New User Journey
tests/e2e/test_new_user.py

Tests the complete flow for a new user:
Register → Login → Create Project → Chat → Save Version
"""

import pytest
from helpers import (
    register_user,
    login_user,
    create_project,
    send_chat,
    save_version,
    generate_unique_username
)


@pytest.mark.e2e
class TestNewUserJourney:
    """End-to-end tests for new user onboarding flow."""
    
    def test_complete_new_user_flow(self, client):
        """
        Test complete new user journey from registration to saving code version.
        
        Flow:
        1. Register a new user
        2. Login with credentials
        3. Create a new project
        4. Send chat message to generate code
        5. Save a version of the code
        """
        # Generate unique username to avoid conflicts
        username = generate_unique_username('newkid')
        pin = '1234'
        
        # Step 1: Register → Login
        user = register_user(client, username, pin)
        assert user['username'] == username
        assert 'id' in user
        
        # Step 2: Login → Get Token
        token = login_user(client, username, pin)
        assert len(token) == 64  # 32 bytes hex = 64 chars
        
        # Step 3: Create Project
        project = create_project(
            client, token,
            name='My First Game',
            language='p5js',
            description='A bouncing ball game'
        )
        assert project['name'] == 'My First Game'
        assert project['language'] == 'p5js'
        assert 'id' in project
        
        # Step 4: Chat → Generate Code
        chat_response = send_chat(
            client, token, project['id'],
            message='Make a bouncing ball'
        )
        
        # Verify chat response contains expected code
        assert 'code' in chat_response
        assert 'createCanvas' in chat_response['code']
        assert 'explanation' in chat_response
        assert chat_response['success'] is True
        
        # Step 5: Save Version
        version = save_version(
            client, token, project['id'],
            description='v1 - Initial bouncing ball'
        )
        assert 'version_id' in version
        assert version['description'] == 'v1 - Initial bouncing ball'
    
    def test_new_user_can_create_multiple_projects(self, client):
        """
        Test that a new user can create and manage multiple projects.
        """
        username = generate_unique_username('multiproject')
        pin = '5678'
        
        # Register and login
        register_user(client, username, pin)
        token = login_user(client, username, pin)
        
        # Create multiple projects
        projects = []
        for i in range(3):
            project = create_project(
                client, token,
                name=f'Project {i+1}',
                language='p5js',
                description=f'Test project number {i+1}'
            )
            projects.append(project)
        
        # Verify all projects created
        assert len(projects) == 3
        
        # Each project should have unique ID
        project_ids = [p['id'] for p in projects]
        assert len(set(project_ids)) == 3
    
    def test_new_user_chat_updates_project_code(self, client, db_path):
        """
        Test that chat responses update the project's current_code field.
        """
        import sqlite3
        
        username = generate_unique_username('codeupdate')
        pin = '9012'
        
        # Register, login, create project
        register_user(client, username, pin)
        token = login_user(client, username, pin)
        project = create_project(client, token, name='Code Test')
        
        # Send chat message
        chat_response = send_chat(
            client, token, project['id'],
            message='Draw a circle'
        )
        
        # Verify code was stored in database
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        cursor.execute(
            'SELECT current_code FROM projects WHERE id = ?',
            (project['id'],)
        )
        result = cursor.fetchone()
        conn.close()
        
        assert result is not None
        assert 'ellipse' in result['current_code'] or 'createCanvas' in result['current_code']
    
    def test_new_user_cannot_access_others_projects(self, client):
        """
        Test that a new user cannot access projects created by other users.
        """
        # Create first user and project
        user1 = generate_unique_username('user1')
        register_user(client, user1, '1111')
        token1 = login_user(client, user1, '1111')
        project1 = create_project(client, token1, name='User1 Project')
        
        # Create second user
        user2 = generate_unique_username('user2')
        register_user(client, user2, '2222')
        token2 = login_user(client, user2, '2222')
        
        # Second user tries to access first user's project
        headers = {'Authorization': f'Bearer {token2}'}
        response = client.get(f'/api/projects/{project1["id"]}', headers=headers)
        
        # Should get 404 (not 403) to not reveal existence
        assert response.status_code == 404
        assert response.get_json()['success'] is False
    
    def test_new_user_can_save_multiple_versions(self, client):
        """
        Test that a new user can save multiple versions of their project.
        """
        username = generate_unique_username('versions')
        pin = '3333'
        
        # Setup
        register_user(client, username, pin)
        token = login_user(client, username, pin)
        project = create_project(client, token, name='Version Test')
        
        # Generate some code first via chat
        send_chat(client, token, project['id'], 'Create a canvas')
        
        # Save multiple versions
        versions = []
        for i in range(3):
            version = save_version(
                client, token, project['id'],
                description=f'v{i+1} - Update {i+1}'
            )
            versions.append(version)
        
        # Verify all versions saved
        assert len(versions) == 3
        
        # Each version should have a unique ID
        version_ids = [v['version_id'] for v in versions]
        assert len(set(version_ids)) == 3
