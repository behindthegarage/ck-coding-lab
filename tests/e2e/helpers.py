"""
E2E Test Helpers - CK Coding Lab
Helper functions for end-to-end user flow tests.
"""

import uuid
from unittest.mock import patch, MagicMock


def register_user(client, username, pin, role='kid'):
    """
    Create a test user directly in the database.

    This helper is for end-to-end setup, not for exercising the public
    registration API. Public self-registration is disabled by default.
    
    Args:
        client: Flask test client (unused; kept for call-site compatibility)
        username: Username for the new user
        pin: 4-digit PIN
        role: User role ('kid' by default)
    
    Returns:
        dict: Created user data
    """
    from auth import create_user

    user = create_user(username, pin, role)
    assert user['username'] == username
    return user


def login_user(client, username, pin):
    """
    Login a user and return the authentication token.
    
    Args:
        client: Flask test client
        username: Username to login
        pin: 4-digit PIN
    
    Returns:
        str: Authentication token (Bearer token)
    """
    response = client.post('/api/auth/login',
                          json={'username': username, 'pin': pin})
    assert response.status_code == 200, f"Login failed: {response.get_json()}"
    data = response.get_json()
    assert data['success'] is True
    return data['token']


def create_project(client, token, name, language='p5js', description=None):
    """
    Create a new project.
    
    Args:
        client: Flask test client
        token: Authentication token
        name: Project name
        language: Programming language (default: 'p5js')
        description: Optional project description
    
    Returns:
        dict: Project data from creation response
    """
    headers = {'Authorization': f'Bearer {token}'}
    payload = {'name': name, 'language': language}
    if description:
        payload['description'] = description
    
    response = client.post('/api/projects', headers=headers, json=payload)
    assert response.status_code == 201, f"Project creation failed: {response.get_json()}"
    data = response.get_json()
    assert data['success'] is True
    return data['project']


def send_chat(client, token, project_id, message, model='kimi-k2.5', enable_tools=False):
    """
    Send a chat message to a project.
    
    Note: This function patches the AI client to return a mock response
    for consistent testing without making real API calls.
    
    Args:
        client: Flask test client
        token: Authentication token
        project_id: Project ID
        message: Chat message
        model: AI model to use (default: 'kimi-k2.5')
        enable_tools: Whether to enable tool calls
    
    Returns:
        dict: Chat response data
    """
    headers = {'Authorization': f'Bearer {token}'}
    payload = {'message': message, 'model': model}
    if enable_tools:
        payload['enable_tools'] = True
    
    # Mock AI response for consistent testing
    with patch('chat.routes.get_ai_client') as mock_get_client:
        mock_ai = MagicMock()
        mock_ai.generate_code.return_value = {
            'success': True,
            'code': '''function setup() {
    createCanvas(400, 400);
}

function draw() {
    background(220);
    // Bouncing ball
    ellipse(200, 200, 50, 50);
}''',
            'explanation': f'Created code for: {message}',
            'suggestions': ['Add color', 'Make it interactive'],
            'full_response': f'Here\'s the code for {message}',
            'model': model,
            'tokens_used': 150,
            'tool_calls': [],
            'created_files': []
        }
        mock_get_client.return_value = mock_ai
        
        response = client.post(f'/api/projects/{project_id}/chat',
                              headers=headers, json=payload)
    
    assert response.status_code == 200, f"Chat failed: {response.get_json()}"
    data = response.get_json()
    assert data['success'] is True
    return data['response']


def save_version(client, token, project_id, description):
    """
    Save a version of the project's code.
    
    Args:
        client: Flask test client
        token: Authentication token
        project_id: Project ID
        description: Version description
    
    Returns:
        dict: Version data from save response
    """
    headers = {'Authorization': f'Bearer {token}'}
    response = client.post(f'/api/projects/{project_id}/versions',
                          headers=headers,
                          json={'description': description})
    
    assert response.status_code == 200, f"Save version failed: {response.get_json()}"
    data = response.get_json()
    assert data['success'] is True
    return data


def get_project(client, token, project_id):
    """
    Get project details.
    
    Args:
        client: Flask test client
        token: Authentication token
        project_id: Project ID
    
    Returns:
        dict: Project data
    """
    headers = {'Authorization': f'Bearer {token}'}
    response = client.get(f'/api/projects/{project_id}', headers=headers)
    
    assert response.status_code == 200, f"Get project failed: {response.get_json()}"
    data = response.get_json()
    assert data['success'] is True
    return data['project']


def update_project(client, token, project_id, name=None, description=None):
    """
    Update a project.
    
    Args:
        client: Flask test client
        token: Authentication token
        project_id: Project ID
        name: New project name (optional)
        description: New description (optional)
    
    Returns:
        dict: Updated project data
    """
    headers = {'Authorization': f'Bearer {token}'}
    payload = {}
    if name:
        payload['name'] = name
    if description:
        payload['description'] = description
    
    response = client.put(f'/api/projects/{project_id}', headers=headers, json=payload)
    
    assert response.status_code == 200, f"Update project failed: {response.get_json()}"
    data = response.get_json()
    assert data['success'] is True
    return data['project']


def list_projects(client, token):
    """
    List all projects for the authenticated user.
    
    Args:
        client: Flask test client
        token: Authentication token
    
    Returns:
        list: List of project dicts
    """
    headers = {'Authorization': f'Bearer {token}'}
    response = client.get('/api/projects', headers=headers)
    
    assert response.status_code == 200, f"List projects failed: {response.get_json()}"
    data = response.get_json()
    assert data['success'] is True
    return data['projects']


def list_versions(client, token, project_id):
    """
    List all versions for a project.
    
    Args:
        client: Flask test client
        token: Authentication token
        project_id: Project ID
    
    Returns:
        list: List of version dicts
    """
    headers = {'Authorization': f'Bearer {token}'}
    response = client.get(f'/api/projects/{project_id}/versions', headers=headers)
    
    assert response.status_code == 200, f"List versions failed: {response.get_json()}"
    data = response.get_json()
    return data['versions']


def delete_project(client, token, project_id):
    """
    Delete a project.
    
    Args:
        client: Flask test client
        token: Authentication token
        project_id: Project ID
    
    Returns:
        bool: True if deletion was successful
    """
    headers = {'Authorization': f'Bearer {token}'}
    response = client.delete(f'/api/projects/{project_id}', headers=headers)
    
    assert response.status_code == 200, f"Delete project failed: {response.get_json()}"
    data = response.get_json()
    assert data['success'] is True
    return True


def create_user_as_admin(client, admin_token, username, pin, role='kid'):
    """
    Create a new user through the admin JSON API.
    
    Args:
        client: Flask test client
        admin_token: Admin authentication token
        username: Username for new user
        pin: 4-digit PIN
        role: User role ('admin' or 'kid')
    
    Returns:
        dict: Created user data
    """
    headers = {'Authorization': f'Bearer {admin_token}'}
    response = client.post('/api/admin/users',
                          headers=headers,
                          json={'username': username, 'pin': pin, 'role': role})

    assert response.status_code == 201, f"Admin user creation failed: {response.get_json()}"
    data = response.get_json()
    assert data['success'] is True
    return data['user']


def deactivate_user(client, admin_token, user_id):
    """
    Deactivate a user account (admin only).
    
    Args:
        client: Flask test client
        admin_token: Admin authentication token
        user_id: User ID to deactivate
    
    Returns:
        bool: True if deactivation was successful
    """
    headers = {'Authorization': f'Bearer {admin_token}'}
    response = client.post(f'/api/admin/users/{user_id}/deactivate', headers=headers)

    assert response.status_code == 200, f"Deactivate user failed: {response.get_json()}"
    data = response.get_json()
    assert data['success'] is True
    return True


def get_admin_stats(client, admin_token):
    """
    Get admin dashboard statistics.
    
    Args:
        client: Flask test client
        admin_token: Admin authentication token
    
    Returns:
        dict: Admin statistics
    """
    headers = {'Authorization': f'Bearer {admin_token}'}
    response = client.get('/api/admin/stats', headers=headers)
    
    assert response.status_code == 200, f"Get admin stats failed: {response.get_json()}"
    data = response.get_json()
    assert data['success'] is True
    return data['stats']


def get_admin_users(client, admin_token):
    """
    Get all users with project counts (admin only).
    
    Args:
        client: Flask test client
        admin_token: Admin authentication token
    
    Returns:
        list: List of user dicts with project counts
    """
    headers = {'Authorization': f'Bearer {admin_token}'}
    response = client.get('/api/admin/users', headers=headers)
    
    assert response.status_code == 200, f"Get admin users failed: {response.get_json()}"
    data = response.get_json()
    assert data['success'] is True
    return data['users']


def generate_unique_username(prefix='user'):
    """
    Generate a unique username for testing.
    
    Args:
        prefix: Username prefix
    
    Returns:
        str: Unique username
    """
    return f'{prefix}_{uuid.uuid4().hex[:8]}'
