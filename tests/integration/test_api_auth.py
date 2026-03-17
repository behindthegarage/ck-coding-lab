# tests/integration/test_api_auth.py - Authentication API integration tests
"""
Integration tests for authentication API endpoints.

Tests cover:
- Registration endpoint
- Login endpoint
- Logout endpoint
- Protected routes
- Token validation
- Error responses
"""

import pytest
import json


@pytest.fixture(autouse=True)
def reset_auth_rate_limit():
    """Reset the auth rate limit store before each test."""
    import routes
    routes._rate_limit_store.clear()
    yield
    routes._rate_limit_store.clear()


@pytest.mark.integration
@pytest.mark.api
@pytest.mark.auth
class TestRegistrationAPI:
    """Tests for the registration endpoint."""

    def test_register_requires_admin_when_self_registration_disabled(self, client):
        """Public self-registration should be blocked by default."""
        response = client.post('/api/auth/register',
                              json={'username': 'newkid', 'pin': '1234'})

        assert response.status_code == 403
        data = response.get_json()
        assert data['success'] is False
        assert 'disabled' in data['error'].lower()

    def test_register_success_for_admin(self, client, admin_auth_headers):
        """Admins can create users through the registration endpoint."""
        response = client.post('/api/auth/register',
                              headers=admin_auth_headers,
                              json={'username': 'newkid', 'pin': '1234'})

        assert response.status_code == 201
        data = response.get_json()
        assert data['success'] is True
        assert 'user' in data
        assert data['user']['username'] == 'newkid'
        assert data['user']['role'] == 'kid'
        assert 'id' in data['user']
        assert 'pin_hash' not in data['user']

    def test_register_admin_role_requires_admin_auth(self, client, admin_auth_headers):
        """Only admins may create admin users."""
        response = client.post('/api/auth/register',
                              headers=admin_auth_headers,
                              json={'username': 'newadmin', 'pin': '1234', 'role': 'admin'})

        assert response.status_code == 201
        assert response.get_json()['user']['role'] == 'admin'

    def test_register_missing_fields(self, client, admin_auth_headers):
        """Test registration with missing fields."""
        response = client.post('/api/auth/register',
                              headers=admin_auth_headers,
                              json={'pin': '1234'})
        assert response.status_code == 400
        assert response.get_json()['success'] is False

        response = client.post('/api/auth/register',
                              headers=admin_auth_headers,
                              json={'username': 'newkid'})
        assert response.status_code == 400
        assert response.get_json()['success'] is False

    def test_register_invalid_pin_format(self, client, admin_auth_headers):
        """Test registration with invalid PIN format."""
        invalid_pins = ['123', '12345', 'abcd', '12ab', '']

        for pin in invalid_pins:
            response = client.post('/api/auth/register',
                                  headers=admin_auth_headers,
                                  json={'username': f'user_{pin}', 'pin': pin})
            assert response.status_code == 400, f"PIN '{pin}' should be rejected"
            assert response.get_json()['success'] is False

    def test_register_duplicate_username(self, client, admin_auth_headers):
        """Test registration with duplicate username."""
        response = client.post('/api/auth/register',
                              headers=admin_auth_headers,
                              json={'username': 'duplicate', 'pin': '1234'})
        assert response.status_code == 201

        response = client.post('/api/auth/register',
                              headers=admin_auth_headers,
                              json={'username': 'duplicate', 'pin': '5678'})
        assert response.status_code == 409
        data = response.get_json()
        assert data['success'] is False
        assert 'already taken' in data['error'].lower()

    def test_register_non_json_request(self, client, admin_auth_headers):
        """Test registration with non-JSON request."""
        response = client.post('/api/auth/register',
                              headers=admin_auth_headers,
                              data='username=test&pin=1234',
                              content_type='application/x-www-form-urlencoded')

        assert response.status_code == 400
        assert response.get_json()['success'] is False


@pytest.mark.integration
@pytest.mark.api
@pytest.mark.auth
class TestLoginAPI:
    """Tests for the login endpoint."""
    
    def test_login_success(self, client, test_user):
        """Test successful login."""
        response = client.post('/api/auth/login',
                              json={'username': test_user['username'], 'pin': '1234'})
        
        assert response.status_code == 200
        data = response.get_json()
        assert data['success'] is True
        assert 'token' in data
        assert 'user' in data
        assert data['user']['username'] == test_user['username']
        assert len(data['token']) == 64  # 32 bytes hex
    
    def test_login_sets_cookie(self, client, test_user):
        """Test that login sets auth cookie."""
        response = client.post('/api/auth/login',
                              json={'username': test_user['username'], 'pin': '1234'})
        
        assert response.status_code == 200
        # Check for auth_token cookie
        cookies = response.headers.getlist('Set-Cookie')
        assert any('auth_token' in c for c in cookies)
    
    def test_login_wrong_pin(self, client, test_user):
        """Test login with wrong PIN."""
        response = client.post('/api/auth/login',
                              json={'username': 'testuser', 'pin': '9999'})
        
        assert response.status_code == 401
        data = response.get_json()
        assert data['success'] is False
        assert 'invalid' in data['error'].lower()
    
    def test_login_nonexistent_user(self, client):
        """Test login with non-existent user."""
        response = client.post('/api/auth/login',
                              json={'username': 'nonexistent', 'pin': '1234'})
        
        assert response.status_code == 401
        data = response.get_json()
        assert data['success'] is False
    
    def test_login_missing_fields(self, client):
        """Test login with missing fields."""
        # Missing username
        response = client.post('/api/auth/login',
                              json={'pin': '1234'})
        assert response.status_code == 400
        
        # Missing PIN
        response = client.post('/api/auth/login',
                              json={'username': 'test'})
        assert response.status_code == 400
    
    def test_login_invalid_pin_format(self, client):
        """Test login with invalid PIN format."""
        response = client.post('/api/auth/login',
                              json={'username': 'test', 'pin': '123'})
        
        assert response.status_code == 400
        data = response.get_json()
        assert data['success'] is False
    
    def test_login_rate_limiting(self, client, test_user):
        """Test that rate limiting works on login."""
        # Make 6 failed login attempts
        for i in range(6):
            response = client.post('/api/auth/login',
                                  json={'username': 'testuser', 'pin': '9999'})
        
        # 6th attempt should be rate limited
        assert response.status_code == 429
        data = response.get_json()
        assert data['success'] is False
        assert 'too many' in data['error'].lower()


@pytest.mark.integration
@pytest.mark.api
@pytest.mark.auth
class TestProtectedRoutesAPI:
    """Tests for protected API routes."""
    
    def test_get_me_success(self, client, test_user, auth_headers):
        """Test getting current user with valid token."""
        response = client.get('/api/auth/me', headers=auth_headers)
        
        assert response.status_code == 200
        data = response.get_json()
        assert 'user' in data
        assert data['user']['username'] == test_user['username']
    
    def test_get_me_no_token(self, client):
        """Test getting current user without token."""
        response = client.get('/api/auth/me')
        
        assert response.status_code == 401
        data = response.get_json()
        assert data['success'] is False
    
    def test_get_me_invalid_token(self, client):
        """Test getting current user with invalid token."""
        response = client.get('/api/auth/me',
                             headers={'Authorization': 'Bearer invalid-token'})
        
        assert response.status_code == 401
        data = response.get_json()
        assert data['success'] is False
    
    def test_get_me_malformed_header(self, client):
        """Test with malformed authorization header."""
        response = client.get('/api/auth/me',
                             headers={'Authorization': 'invalid-header'})
        
        assert response.status_code == 401
    
    def test_get_me_wrong_header_format(self, client):
        """Test with wrong authorization header format."""
        response = client.get('/api/auth/me',
                             headers={'Authorization': 'Basic dGVzdDp0ZXN0'})
        
        assert response.status_code == 401


@pytest.mark.integration
@pytest.mark.api
@pytest.mark.auth
class TestLogoutAPI:
    """Tests for the logout endpoint."""
    
    def test_logout_success(self, client, test_user, auth_headers):
        """Test successful logout."""
        # First verify token works
        response = client.get('/api/auth/me', headers=auth_headers)
        assert response.status_code == 200
        
        # Logout
        response = client.post('/api/auth/logout', headers=auth_headers)
        assert response.status_code == 200
        data = response.get_json()
        assert data['success'] is True
        
        # Token should no longer work
        response = client.get('/api/auth/me', headers=auth_headers)
        assert response.status_code == 401
    
    def test_logout_no_token(self, client):
        """Test logout without token."""
        response = client.post('/api/auth/logout')
        
        assert response.status_code == 401
    
    def test_logout_invalid_token(self, client):
        """Test logout with invalid token."""
        response = client.post('/api/auth/logout',
                              headers={'Authorization': 'Bearer invalid'})
        
        assert response.status_code == 401
    
    def test_logout_deletes_cookie(self, client, test_user, auth_headers):
        """Test that logout clears the auth cookie."""
        response = client.post('/api/auth/logout', headers=auth_headers)
        
        # Check for deleted cookie
        cookies = response.headers.getlist('Set-Cookie')
        assert any('auth_token=;' in c for c in cookies)


@pytest.mark.integration
@pytest.mark.api
class TestHealthAPI:
    """Tests for health check endpoint."""
    
    def test_health_check(self, client):
        """Test health check endpoint."""
        response = client.get('/api/auth/health')
        
        assert response.status_code == 200
        data = response.get_json()
        assert data['status'] == 'ok'
        assert 'service' in data
    
    def test_health_no_auth_required(self, client):
        """Test that health check doesn't require authentication."""
        response = client.get('/api/auth/health')
        
        assert response.status_code == 200
        data = response.get_json()
        assert 'status' in data
        assert data['status'] == 'ok'


@pytest.mark.integration
@pytest.mark.api
class TestCompleteAuthFlow:
    """End-to-end authentication flow tests."""
    
    def test_full_auth_flow(self, client, test_user_factory):
        """Test complete create → login → access → logout flow."""
        import uuid
        
        username = f'flow_{uuid.uuid4().hex[:8]}'
        test_user_factory(username=username, pin='1234')
        
        # 2. Login
        response = client.post('/api/auth/login',
                              json={'username': username, 'pin': '1234'})
        assert response.status_code == 200
        token = response.get_json()['token']
        
        # 3. Access protected route
        response = client.get('/api/auth/me',
                             headers={'Authorization': f'Bearer {token}'})
        assert response.status_code == 200
        assert response.get_json()['user']['username'] == username
        
        # 4. Logout
        response = client.post('/api/auth/logout',
                              headers={'Authorization': f'Bearer {token}'})
        assert response.status_code == 200
        
        # 5. Verify token is invalidated
        response = client.get('/api/auth/me',
                             headers={'Authorization': f'Bearer {token}'})
        assert response.status_code == 401
    
    def test_multiple_sessions_same_user(self, client, test_user_factory):
        """Test that a user can have multiple active sessions."""
        import uuid
        
        username = f'multi_{uuid.uuid4().hex[:8]}'
        test_user_factory(username=username, pin='5555')
        
        # Login twice
        response1 = client.post('/api/auth/login',
                               json={'username': username, 'pin': '5555'})
        token1 = response1.get_json()['token']
        
        response2 = client.post('/api/auth/login',
                               json={'username': username, 'pin': '5555'})
        token2 = response2.get_json()['token']
        
        # Both tokens should work
        assert client.get('/api/auth/me',
                         headers={'Authorization': f'Bearer {token1}'}).status_code == 200
        assert client.get('/api/auth/me',
                         headers={'Authorization': f'Bearer {token2}'}).status_code == 200
        
        # Logout one, other should still work
        client.post('/api/auth/logout',
                   headers={'Authorization': f'Bearer {token1}'})
        
        assert client.get('/api/auth/me',
                         headers={'Authorization': f'Bearer {token1}'}).status_code == 401
        assert client.get('/api/auth/me',
                         headers={'Authorization': f'Bearer {token2}'}).status_code == 200


@pytest.mark.integration
@pytest.mark.api
class TestAPIErrorResponses:
    """Tests for API error response format consistency."""
    
    def test_error_response_format(self, client):
        """Test that error responses follow consistent format."""
        response = client.get('/api/auth/me')  # No token
        
        assert response.status_code == 401
        data = response.get_json()
        
        # Check standard error format
        assert 'success' in data
        assert data['success'] is False
        assert 'error' in data
        assert isinstance(data['error'], str)
    
    def test_404_handler(self, client):
        """Test 404 error handling."""
        response = client.get('/api/nonexistent')
        
        assert response.status_code == 404
        data = response.get_json()
        assert data['success'] is False
        assert 'not found' in data['error'].lower()
    
    def test_method_not_allowed(self, client):
        """Test 405 method not allowed."""
        response = client.get('/api/auth/login')  # POST only
        
        assert response.status_code == 405
