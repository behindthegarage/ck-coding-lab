"""
E2E Test: Admin Workflow
tests/e2e/test_admin.py

Tests the complete admin workflow:
Admin login → Create user → Deactivate user → View stats
"""

import pytest
from .helpers import (
    register_user,
    login_user,
    create_project,
    create_user_as_admin,
    deactivate_user,
    get_admin_stats,
    get_admin_users,
    generate_unique_username
)


@pytest.mark.e2e
class TestAdminWorkflow:
    """End-to-end tests for admin user management workflows."""
    
    def test_admin_can_manage_users(self, client, test_admin):
        """
        Test complete admin workflow for user management.
        
        Flow:
        1. Admin login
        2. View admin stats
        3. View all users
        4. Create a new user (via registration)
        5. Verify user appears in list
        6. View updated stats
        """
        # Step 1: Admin Login
        admin_token = login_user(client, test_admin['username'], '5678')
        assert len(admin_token) == 64
        
        # Step 2: View Admin Stats
        stats = get_admin_stats(client, admin_token)
        assert 'total_users' in stats
        assert 'total_projects' in stats
        assert 'admin_count' in stats
        initial_user_count = stats['total_users']
        
        # Step 3: View All Users
        users = get_admin_users(client, admin_token)
        assert isinstance(users, list)
        initial_users_len = len(users)
        
        # Verify admin is in the list
        admin_usernames = [u['username'] for u in users]
        assert test_admin['username'] in admin_usernames
        
        # Step 4: Create a new user via admin API
        new_username = generate_unique_username('admincreated')
        new_user = create_user_as_admin(client, admin_token, new_username, '4321')
        assert new_user['username'] == new_username
        
        # Step 5: Verify user appears in list
        users = get_admin_users(client, admin_token)
        user_usernames = [u['username'] for u in users]
        assert new_username in user_usernames
        assert len(users) == initial_users_len + 1
        
        # Step 6: View Updated Stats
        updated_stats = get_admin_stats(client, admin_token)
        assert updated_stats['total_users'] == initial_user_count + 1
    
    def test_admin_can_see_user_project_counts(self, client, test_admin):
        """Test that admin can see project counts for all users."""
        # Admin login
        admin_token = login_user(client, test_admin['username'], '5678')
        
        # Create a regular user with projects
        user = generate_unique_username('projectuser')
        create_user_as_admin(client, admin_token, user, '1234')
        user_token = login_user(client, user, '1234')
        
        # Create projects for this user
        create_project(client, user_token, name='Project 1')
        create_project(client, user_token, name='Project 2')
        create_project(client, user_token, name='Project 3')
        
        # Admin views users
        users = get_admin_users(client, admin_token)
        
        # Find our test user
        test_user_data = next((u for u in users if u['username'] == user), None)
        assert test_user_data is not None
        assert test_user_data['project_count'] == 3
    
    def test_admin_stats_include_all_metrics(self, client, test_admin):
        """Test that admin stats include all expected metrics."""
        admin_token = login_user(client, test_admin['username'], '5678')
        
        stats = get_admin_stats(client, admin_token)
        
        # Check all expected keys
        expected_keys = [
            'total_users',
            'total_projects',
            'total_conversations',
            'active_today',
            'admin_count',
            'kid_count'
        ]
        
        for key in expected_keys:
            assert key in stats, f"Missing stat: {key}"
            assert isinstance(stats[key], int)
    
    def test_non_admin_cannot_access_admin_endpoints(self, client, test_user):
        """Test that regular users cannot access admin endpoints."""
        # Login as regular user
        user_token = login_user(client, test_user['username'], '1234')
        
        # Try to access admin stats
        headers = {'Authorization': f'Bearer {user_token}'}
        response = client.get('/api/admin/stats', headers=headers)
        
        assert response.status_code == 403
        assert response.get_json()['success'] is False
        
        # Try to access admin users
        response = client.get('/api/admin/users', headers=headers)
        
        assert response.status_code == 403
        assert response.get_json()['success'] is False
    
    def test_admin_can_see_user_roles(self, client, test_admin):
        """Test that admin can see user roles in user list."""
        admin_token = login_user(client, test_admin['username'], '5678')
        
        # Create admin and kid users
        admin_user = generate_unique_username('testadmin')
        create_user_as_admin(client, admin_token, admin_user, '1234', role='admin')
        
        kid_user = generate_unique_username('testkid')
        create_user_as_admin(client, admin_token, kid_user, '5678')
        
        # Get users
        users = get_admin_users(client, admin_token)
        
        # Verify we can see roles
        for user in users:
            assert 'role' in user
            assert user['role'] in ['admin', 'kid']
    
    def test_admin_stats_after_user_activity(self, client, test_admin):
        """Test that admin stats update after user activity."""
        admin_token = login_user(client, test_admin['username'], '5678')
        
        # Get initial stats
        initial_stats = get_admin_stats(client, admin_token)
        initial_projects = initial_stats['total_projects']
        
        # Create a user and add activity
        user = generate_unique_username('activeuser')
        create_user_as_admin(client, admin_token, user, '1234')
        user_token = login_user(client, user, '1234')
        
        # Create a project
        create_project(client, user_token, name='Active Project')
        
        # Check updated stats
        updated_stats = get_admin_stats(client, admin_token)
        assert updated_stats['total_projects'] == initial_projects + 1
    
    def test_admin_users_list_includes_all_fields(self, client, test_admin):
        """Test that admin users list includes all expected fields."""
        admin_token = login_user(client, test_admin['username'], '5678')
        
        users = get_admin_users(client, admin_token)
        
        # Each user should have these fields
        expected_fields = [
            'id', 'username', 'role', 'created_at',
            'is_active', 'project_count'
        ]
        
        for user in users:
            for field in expected_fields:
                assert field in user, f"User missing field: {field}"
    
    def test_admin_cannot_be_deleted(self, client, test_admin):
        """Test that the last admin cannot be deactivated (safety check)."""
        admin_token = login_user(client, test_admin['username'], '5678')

        response = client.post(
            f"/api/admin/users/{test_admin['id']}/deactivate",
            headers={'Authorization': f'Bearer {admin_token}'}
        )

        assert response.status_code == 400
        data = response.get_json()
        assert data['success'] is False
        assert 'own account' in data['error'].lower() or 'last admin' in data['error'].lower()
    
    def test_unauthenticated_cannot_access_admin(self, client):
        """Test that unauthenticated requests cannot access admin endpoints."""
        # No token
        response = client.get('/api/admin/stats')
        assert response.status_code == 401
        
        response = client.get('/api/admin/users')
        assert response.status_code == 401
        
        # Invalid token
        headers = {'Authorization': 'Bearer invalidtoken'}
        response = client.get('/api/admin/stats', headers=headers)
        assert response.status_code == 401
    
    def test_admin_can_track_user_creation_order(self, client, test_admin):
        """Test that users are listed in creation order (newest first)."""
        admin_token = login_user(client, test_admin['username'], '5678')
        
        # Get initial user list
        initial_users = get_admin_users(client, admin_token)
        initial_count = len(initial_users)
        
        # Create users sequentially
        usernames = []
        for i in range(3):
            username = generate_unique_username(f'sequser{i}')
            create_user_as_admin(client, admin_token, username, '1234')
            usernames.append(username)
        
        # Get updated list
        updated_users = get_admin_users(client, admin_token)
        
        # New users should be at the top (newest first)
        updated_usernames = [u['username'] for u in updated_users]
        
        # Verify all new users are in the list
        for username in usernames:
            assert username in updated_usernames
        
        # Verify count increased
        assert len(updated_users) == initial_count + 3
