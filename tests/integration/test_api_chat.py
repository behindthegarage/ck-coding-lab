# tests/integration/test_api_chat.py - Chat/AI API integration tests (mocked)
"""
Integration tests for chat/AI API endpoints with mocked AI responses.

Tests cover:
- Chat endpoint
- Message storage
- Response parsing
- Error handling
"""

import pytest
import json
from unittest.mock import patch, MagicMock


@pytest.mark.integration
@pytest.mark.api
class TestChatAPI:
    """Tests for chat/AI endpoints."""
    
    @patch('ai_client.get_ai_client')
    def test_chat_success(self, mock_get_client, client, auth_headers, project_factory):
        """Test successful chat interaction."""
        # Setup mock
        mock_ai = MagicMock()
        mock_ai.generate_code.return_value = {
            'success': True,
            'code': 'function setup() { createCanvas(400, 400); }',
            'explanation': 'Creates a canvas',
            'suggestions': ['Add color'],
            'full_response': 'Here\'s the code:\n```javascript\nfunction setup() {}\n```',
            'model': 'kimi-k2.5',
            'tokens_used': 100,
            'tool_calls': [],
            'created_files': []
        }
        mock_get_client.return_value = mock_ai
        
        project = project_factory()
        
        response = client.post(f'/api/projects/{project["id"]}/chat', headers=auth_headers,
                              json={'message': 'Create a canvas', 'model': 'kimi-k2.5'})
        
        assert response.status_code == 200
        data = response.get_json()
        assert data['success'] is True
        assert 'response' in data
        assert data['response']['code'] is not None
        assert data['response']['explanation'] is not None
    
    @patch('ai_client.get_ai_client')
    def test_chat_stores_conversation(self, mock_get_client, client, auth_headers, 
                                       project_factory, db_path):
        """Test that chat messages are stored in database."""
        import sqlite3
        
        mock_ai = MagicMock()
        mock_ai.generate_code.return_value = {
            'success': True,
            'code': 'test code',
            'explanation': 'test explanation',
            'suggestions': [],
            'full_response': 'response',
            'model': 'kimi-k2.5',
            'tokens_used': 50,
            'tool_calls': [],
            'created_files': []
        }
        mock_get_client.return_value = mock_ai
        
        project = project_factory()
        project_id = project['id']
        
        # Send message
        client.post(f'/api/projects/{project_id}/chat', headers=auth_headers,
                   json={'message': 'Hello AI'})
        
        # Verify stored in database
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        cursor.execute('''
            SELECT role, content FROM conversations WHERE project_id = ?
            ORDER BY created_at ASC
        ''', (project_id,))
        messages = cursor.fetchall()
        conn.close()
        
        assert len(messages) >= 1  # At least user message
        assert messages[0]['role'] == 'user'
        assert messages[0]['content'] == 'Hello AI'
    
    @patch('ai_client.get_ai_client')
    def test_chat_updates_project_code(self, mock_get_client, client, auth_headers, 
                                        project_factory, db_path):
        """Test that generated code updates the project."""
        import sqlite3
        
        mock_ai = MagicMock()
        mock_ai.generate_code.return_value = {
            'success': True,
            'code': 'function draw() { ellipse(100, 100, 50, 50); }',
            'explanation': 'Draws a circle',
            'suggestions': [],
            'full_response': 'response',
            'model': 'kimi-k2.5',
            'tokens_used': 75,
            'tool_calls': [],
            'created_files': []
        }
        mock_get_client.return_value = mock_ai
        
        project = project_factory()
        project_id = project['id']
        
        client.post(f'/api/projects/{project_id}/chat', headers=auth_headers,
                   json={'message': 'Draw a circle'})
        
        # Verify code was updated
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        cursor.execute('SELECT current_code FROM projects WHERE id = ?', (project_id,))
        result = cursor.fetchone()
        conn.close()
        
        assert 'ellipse' in result['current_code']
    
    @patch('ai_client.get_ai_client')
    def test_chat_ai_error(self, mock_get_client, client, auth_headers, project_factory):
        """Test handling of AI generation error."""
        mock_ai = MagicMock()
        mock_ai.generate_code.return_value = {
            'success': False,
            'error': 'Rate limit exceeded'
        }
        mock_get_client.return_value = mock_ai
        
        project = project_factory()
        
        response = client.post(f'/api/projects/{project["id"]}/chat', headers=auth_headers,
                              json={'message': 'Test'})
        
        assert response.status_code == 500
        data = response.get_json()
        assert data['success'] is False
        assert 'rate limit' in data['error'].lower()
    
    def test_chat_missing_message(self, client, auth_headers, project_factory):
        """Test chat with missing message."""
        project = project_factory()
        
        response = client.post(f'/api/projects/{project["id"]}/chat', headers=auth_headers,
                              json={})
        
        assert response.status_code == 400
        assert response.get_json()['success'] is False
    
    def test_chat_message_too_long(self, client, auth_headers, project_factory):
        """Test chat with message over 2000 characters."""
        project = project_factory()
        
        response = client.post(f'/api/projects/{project["id"]}/chat', headers=auth_headers,
                              json={'message': 'A' * 2001})
        
        assert response.status_code == 400
        assert response.get_json()['success'] is False
    
    def test_chat_unauthorized(self, client, project_factory):
        """Test chat without authentication."""
        project = project_factory()
        
        response = client.post(f'/api/projects/{project["id"]}/chat',
                              json={'message': 'Test'})
        
        assert response.status_code == 401
    
    def test_chat_wrong_project(self, client, test_user_factory, auth_headers_factory):
        """Test chat on non-existent project."""
        user = test_user_factory('chatuser', '1234')
        headers = auth_headers_factory(user['id'])
        
        response = client.post('/api/projects/99999/chat', headers=headers,
                              json={'message': 'Test'})
        
        assert response.status_code == 404


@pytest.mark.integration
@pytest.mark.api
class TestCodeValidationAPI:
    """Tests for code validation endpoint."""
    
    def test_validate_safe_code(self, client, auth_headers, project_factory):
        """Test validating safe code."""
        project = project_factory()
        
        response = client.post(f'/api/projects/{project["id"]}/validate', headers=auth_headers,
                              json={'code': 'function setup() { createCanvas(400, 400); }'})
        
        assert response.status_code == 200
        data = response.get_json()
        assert data['success'] is True
        assert data['valid'] is True
        assert data['issues'] == []
    
    def test_validate_dangerous_code(self, client, auth_headers, project_factory):
        """Test validating code with dangerous patterns."""
        project = project_factory()
        
        response = client.post(f'/api/projects/{project["id"]}/validate', headers=auth_headers,
                              json={'code': "eval('alert(1)')"})
        
        assert response.status_code == 200
        data = response.get_json()
        assert data['success'] is True
        assert data['valid'] is False
        assert len(data['issues']) > 0
    
    def test_validate_missing_code(self, client, auth_headers, project_factory):
        """Test validation with missing code."""
        project = project_factory()
        
        response = client.post(f'/api/projects/{project["id"]}/validate', headers=auth_headers,
                              json={})
        
        assert response.status_code == 400
        assert response.get_json()['success'] is False


@pytest.mark.integration
@pytest.mark.api
class TestChatConversationFlow:
    """Tests for multi-message conversation flows."""
    
    @patch('ai_client.get_ai_client')
    def test_conversation_history_included(self, mock_get_client, client, auth_headers, 
                                            project_factory):
        """Test that conversation history is passed to AI."""
        mock_ai = MagicMock()
        mock_ai.generate_code.return_value = {
            'success': True,
            'code': 'code',
            'explanation': 'explanation',
            'suggestions': [],
            'full_response': 'response',
            'model': 'kimi-k2.5',
            'tokens_used': 50,
            'tool_calls': [],
            'created_files': []
        }
        mock_get_client.return_value = mock_ai
        
        project = project_factory()
        
        # Send multiple messages
        for i in range(3):
            client.post(f'/api/projects/{project["id"]}/chat', headers=auth_headers,
                       json={'message': f'Message {i}'})
        
        # Verify AI was called with conversation history
        calls = mock_ai.generate_code.call_args_list
        assert len(calls) == 3
        
        # Later calls should include history
        last_call = calls[2][1]  # kwargs of last call
        assert 'conversation_history' in last_call
        assert len(last_call['conversation_history']) > 0
    
    @patch('ai_client.get_ai_client')
    def test_chat_with_tool_calls(self, mock_get_client, client, auth_headers, project_factory):
        """Test chat that includes tool calls."""
        mock_ai = MagicMock()
        mock_ai.generate_code.return_value = {
            'success': True,
            'code': '',
            'explanation': 'Updated the file',
            'suggestions': [],
            'full_response': 'response',
            'model': 'kimi-k2.5',
            'tokens_used': 100,
            'tool_calls': [
                {
                    'tool': 'write_file',
                    'input': {'filename': 'todo.md', 'content': '- [ ] Task'},
                    'result': {'success': True, 'action': 'updated'}
                }
            ],
            'created_files': []
        }
        mock_get_client.return_value = mock_ai
        
        project = project_factory()
        
        response = client.post(f'/api/projects/{project["id"]}/chat', headers=auth_headers,
                              json={'message': 'Add a todo', 'enable_tools': True})
        
        assert response.status_code == 200
        data = response.get_json()
        assert 'tool_calls' in data['response']
        assert len(data['response']['tool_calls']) == 1
