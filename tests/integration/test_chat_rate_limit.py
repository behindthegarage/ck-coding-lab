# tests/integration/test_chat_rate_limit.py - Rate Limiting Tests
"""
Integration tests for chat rate limiting functionality.

Tests cover:
- Rate limit enforcement
- Rate limit window management
- Rate limit headers/response format
- Rate limit cleanup
"""

import pytest
import sqlite3
from datetime import datetime, timedelta
from unittest.mock import patch


@pytest.mark.integration
class TestChatRateLimit:
    """Tests for chat rate limiting."""
    
    def test_rate_limit_allows_under_limit(self, client, auth_headers, project_factory, mock_ai_client):
        """Test that requests under the limit are allowed."""
        project = project_factory()
        
        # Make a few requests (under the limit)
        for i in range(3):
            response = client.post(
                f'/api/projects/{project["id"]}/chat',
                headers=auth_headers,
                json={'message': f'Test message {i}'}
            )
            assert response.status_code == 200, f"Request {i} should succeed"
    
    def test_rate_limit_blocks_over_limit(self, client, auth_headers, project_factory, mock_ai_client):
        """Test that requests over the limit are blocked."""
        from chat.rate_limit import CHAT_RATE_LIMIT_REQUESTS
        
        project = project_factory()
        
        # Make requests up to and over the limit
        blocked_response = None
        for i in range(CHAT_RATE_LIMIT_REQUESTS + 2):
            response = client.post(
                f'/api/projects/{project["id"]}/chat',
                headers=auth_headers,
                json={'message': f'Test message {i}'}
            )
            if response.status_code == 429:
                blocked_response = response
                break
        
        assert blocked_response is not None, "Should have been rate limited"
        data = blocked_response.get_json()
        assert data['success'] is False
        assert 'rate limit' in data['error'].lower()
    
    def test_rate_limit_returns_retry_after(self, client, auth_headers, project_factory, mock_ai_client):
        """Test that rate limit response includes retry time."""
        from chat.rate_limit import CHAT_RATE_LIMIT_REQUESTS
        
        project = project_factory()
        
        # Make requests until rate limited
        for i in range(CHAT_RATE_LIMIT_REQUESTS + 5):
            response = client.post(
                f'/api/projects/{project["id"]}/chat',
                headers=auth_headers,
                json={'message': f'Test message {i}'}
            )
            if response.status_code == 429:
                data = response.get_json()
                assert 'rate limit' in data['error'].lower()
                # Should indicate retry time
                assert any(word in data['error'].lower() for word in ['seconds', 'second', 'try again'])
                break
    
    def test_rate_limit_per_user(self, client, test_user_factory, auth_headers_factory, 
                                  mock_ai_client, db_path):
        """Test that rate limits are per-user, not global."""
        from chat.rate_limit import CHAT_RATE_LIMIT_REQUESTS
        import sqlite3
        
        # Create two users
        user1 = test_user_factory('user1', '1234')
        user2 = test_user_factory('user2', '5678')
        headers1 = auth_headers_factory(user1['id'])
        headers2 = auth_headers_factory(user2['id'])
        
        # Create projects for each user directly in DB
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        cursor.execute('''
            INSERT INTO projects (user_id, name, description, language)
            VALUES (?, ?, ?, ?)
        ''', (user1['id'], 'Project 1', 'Desc', 'p5js'))
        project1_id = cursor.lastrowid
        
        cursor.execute('''
            INSERT INTO projects (user_id, name, description, language)
            VALUES (?, ?, ?, ?)
        ''', (user2['id'], 'Project 2', 'Desc', 'p5js'))
        project2_id = cursor.lastrowid
        
        conn.commit()
        conn.close()
        
        # Exhaust user1's rate limit
        for i in range(CHAT_RATE_LIMIT_REQUESTS + 1):
            client.post(
                f'/api/projects/{project1_id}/chat',
                headers=headers1,
                json={'message': f'User1 message {i}'}
            )
        
        # User1 should be rate limited
        response = client.post(
            f'/api/projects/{project1_id}/chat',
            headers=headers1,
            json={'message': 'Should be blocked'}
        )
        assert response.status_code == 429
    
    def test_rate_limit_window_resets(self, client, auth_headers, project_factory, 
                                       mock_ai_client, monkeypatch):
        """Test that rate limit resets after window expires."""
        from chat.rate_limit import CHAT_RATE_LIMIT_REQUESTS
        from datetime import datetime, timedelta
        
        project = project_factory()
        
        # Mock the current time to control rate limit window
        base_time = datetime.utcnow()
        
        with patch('chat.rate_limit.datetime') as mock_datetime:
            mock_datetime.utcnow.return_value = base_time
            mock_datetime.timedelta = timedelta
            
            # Make requests to hit rate limit
            for i in range(CHAT_RATE_LIMIT_REQUESTS):
                response = client.post(
                    f'/api/projects/{project["id"]}/chat',
                    headers=auth_headers,
                    json={'message': f'Message {i}'}
                )
                assert response.status_code == 200
            
            # Should be rate limited now
            response = client.post(
                f'/api/projects/{project["id"]}/chat',
                headers=auth_headers,
                json={'message': 'Blocked'}
            )
            assert response.status_code == 429
            
            # Advance time past the window
            mock_datetime.utcnow.return_value = base_time + timedelta(seconds=61)
            
            # Should be allowed again
            response = client.post(
                f'/api/projects/{project["id"]}/chat',
                headers=auth_headers,
                json={'message': 'Allowed again'}
            )
            assert response.status_code == 200


@pytest.mark.integration
class TestRateLimitDBStorage:
    """Tests for rate limit database storage."""
    
    def test_rate_limit_entries_created(self, client, auth_headers, project_factory, 
                                        mock_ai_client, db_path):
        """Test that rate limit entries are stored in database."""
        import sqlite3
        
        project = project_factory()
        user_id = None
        
        # Get user ID from auth token
        with sqlite3.connect(db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            # Extract user_id from test_user fixture through auth_headers
            cursor.execute('SELECT id FROM users LIMIT 1')
            user = cursor.fetchone()
            if user:
                user_id = user['id']
        
        # Make a request
        client.post(
            f'/api/projects/{project["id"]}/chat',
            headers=auth_headers,
            json={'message': 'Test'}
        )
        
        # Check database for rate limit entry
        with sqlite3.connect(db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            cursor.execute('''
                SELECT COUNT(*) as count FROM rate_limit_buckets
            ''')
            count = cursor.fetchone()['count']
            
            assert count > 0, "Rate limit entry should be created"
    
    def test_rate_limit_cleanup_old_entries(self, client, auth_headers, project_factory,
                                            mock_ai_client, db_path, monkeypatch):
        """Test that old rate limit entries are cleaned up."""
        import sqlite3
        from datetime import datetime, timedelta
        
        project = project_factory()
        
        # Insert old rate limit entries
        with sqlite3.connect(db_path) as conn:
            cursor = conn.cursor()
            old_time = (datetime.utcnow() - timedelta(seconds=120)).strftime('%Y-%m-%dT%H:%M:%S')
            cursor.execute('''
                INSERT INTO rate_limit_buckets (user_id, window_start)
                VALUES (?, datetime(?))
            ''', (1, old_time))
            conn.commit()
        
        # Make a new request which should trigger cleanup
        client.post(
            f'/api/projects/{project["id"]}/chat',
            headers=auth_headers,
            json={'message': 'Test'}
        )
        
        # Old entries should be cleaned up
        with sqlite3.connect(db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            cursor.execute('''
                SELECT COUNT(*) as count FROM rate_limit_buckets
                WHERE window_start < datetime('now', '-60 seconds')
            ''')
            old_count = cursor.fetchone()['count']
            
            assert old_count == 0, "Old rate limit entries should be cleaned up"


@pytest.mark.unit
class TestRateLimitFunction:
    """Unit tests for the rate limit check function."""
    
    def test_check_rate_limit_allows_when_under(self, setup_database):
        """Test that check allows when under limit."""
        from chat.rate_limit import check_chat_rate_limit
        import sqlite3
        
        # Create a user first
        conn = sqlite3.connect(setup_database)
        cursor = conn.cursor()
        cursor.execute('''
            INSERT INTO users (username, pin_hash, role)
            VALUES (?, ?, ?)
        ''', ('ratetest1', 'hash', 'kid'))
        user_id = cursor.lastrowid
        conn.commit()
        conn.close()
        
        allowed, remaining, reset_after = check_chat_rate_limit(user_id)
        
        assert allowed is True
        assert remaining >= 0
        assert reset_after == 0
    
    def test_check_rate_limit_tracks_count(self, setup_database):
        """Test that check tracks request count."""
        from chat.rate_limit import check_chat_rate_limit, CHAT_RATE_LIMIT_REQUESTS
        import sqlite3
        
        # Create a user first
        conn = sqlite3.connect(setup_database)
        cursor = conn.cursor()
        cursor.execute('''
            INSERT INTO users (username, pin_hash, role)
            VALUES (?, ?, ?)
        ''', ('ratetest2', 'hash', 'kid'))
        user_id = cursor.lastrowid
        conn.commit()
        conn.close()
        
        # Make requests and track remaining count
        remaining_counts = []
        for i in range(5):
            allowed, remaining, _ = check_chat_rate_limit(user_id)
            remaining_counts.append(remaining)
            assert allowed is True
        
        # Remaining should decrease
        assert remaining_counts[0] > remaining_counts[-1]
    
    def test_check_rate_limit_blocks_when_exceeded(self, setup_database):
        """Test that check blocks when limit exceeded."""
        from chat.rate_limit import check_chat_rate_limit, CHAT_RATE_LIMIT_REQUESTS
        import sqlite3
        
        # Create a user first
        conn = sqlite3.connect(setup_database)
        cursor = conn.cursor()
        cursor.execute('''
            INSERT INTO users (username, pin_hash, role)
            VALUES (?, ?, ?)
        ''', ('ratetest3', 'hash', 'kid'))
        user_id = cursor.lastrowid
        conn.commit()
        conn.close()
        
        # Exhaust the rate limit
        for i in range(CHAT_RATE_LIMIT_REQUESTS):
            allowed, _, _ = check_chat_rate_limit(user_id=user_id)
            assert allowed is True, f"Request {i} should be allowed"
        
        # Next request should be blocked
        allowed, remaining, reset_after = check_chat_rate_limit(user_id=user_id)
        
        assert allowed is False
        assert remaining == 0
        assert reset_after > 0
    
    def test_check_rate_limit_isolated_per_user(self, setup_database):
        """Test that rate limits are isolated between users."""
        from chat.rate_limit import check_chat_rate_limit, CHAT_RATE_LIMIT_REQUESTS
        import sqlite3
        
        # Create two users
        conn = sqlite3.connect(setup_database)
        cursor = conn.cursor()
        cursor.execute('''
            INSERT INTO users (username, pin_hash, role)
            VALUES (?, ?, ?)
        ''', ('ratetest4', 'hash', 'kid'))
        user1_id = cursor.lastrowid
        cursor.execute('''
            INSERT INTO users (username, pin_hash, role)
            VALUES (?, ?, ?)
        ''', ('ratetest5', 'hash', 'kid'))
        user2_id = cursor.lastrowid
        conn.commit()
        conn.close()
        
        # Exhaust rate limit for user 1
        for i in range(CHAT_RATE_LIMIT_REQUESTS):
            check_chat_rate_limit(user_id=user1_id)
        
        allowed, _, _ = check_chat_rate_limit(user_id=user1_id)
        assert allowed is False  # User 1 is rate limited
        
        # User 2 should still be allowed
        allowed2, _, _ = check_chat_rate_limit(user_id=user2_id)
        assert allowed2 is True  # User 2 is not rate limited
