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
import sqlite3
from unittest.mock import patch, MagicMock


@pytest.mark.integration
@pytest.mark.api
class TestChatAPI:
    """Tests for chat/AI endpoints."""
    
    def test_chat_success(self, client, auth_headers, project_factory, mock_ai_client):
        """Test successful chat interaction."""
        # Setup mock response
        mock_ai_client.generate_code.return_value = {
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
        
        project = project_factory()
        
        response = client.post(f'/api/projects/{project["id"]}/chat', headers=auth_headers,
                              json={'message': 'Create a canvas', 'model': 'kimi-k2.5'})
        
        assert response.status_code == 200
        data = response.get_json()
        assert data['success'] is True
        assert 'response' in data
        assert data['response']['code'] is not None
        assert data['response']['explanation'] is not None
        mock_ai_client.generate_code.assert_called_once()
    
    def test_chat_stores_conversation(self, client, auth_headers, 
                                       project_factory, db_path, mock_ai_client):
        """Test that chat messages are stored in database."""
        import sqlite3
        
        mock_ai_client.generate_code.return_value = {
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
        
        project = project_factory()
        project_id = project['id']
        
        # Send message
        client.post(f'/api/projects/{project_id}/chat', headers=auth_headers,
                   json={'message': 'Hello AI'})
        
        # Verify stored in database
        conn = sqlite3.connect(db_path)
        conn.row_factory = sqlite3.Row
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
    
    def test_chat_updates_project_code(self, client, auth_headers, 
                                        project_factory, db_path, mock_ai_client):
        """Test that generated code updates the project."""
        import sqlite3
        
        mock_ai_client.generate_code.return_value = {
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
        
        project = project_factory()
        project_id = project['id']
        
        client.post(f'/api/projects/{project_id}/chat', headers=auth_headers,
                   json={'message': 'Draw a circle'})
        
        # Verify code was updated
        conn = sqlite3.connect(db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        cursor.execute('SELECT current_code FROM projects WHERE id = ?', (project_id,))
        result = cursor.fetchone()
        conn.close()
        
        assert 'ellipse' in result['current_code']
    
    def test_chat_ai_error(self, client, auth_headers, project_factory, mock_ai_client):
        """Test handling of AI generation error."""
        mock_ai_client.generate_code.return_value = {
            'success': False,
            'error': 'Rate limit exceeded'
        }
        
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
    
    def test_conversation_history_included(self, client, auth_headers, 
                                            project_factory, mock_ai_client):
        """Test that conversation history is passed to AI."""
        mock_ai_client.generate_code.return_value = {
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
        
        project = project_factory()
        
        # Send multiple messages
        for i in range(3):
            client.post(f'/api/projects/{project["id"]}/chat', headers=auth_headers,
                       json={'message': f'Message {i}'})
        
        # Verify AI was called with conversation history
        calls = mock_ai_client.generate_code.call_args_list
        assert len(calls) == 3
        
        # Later calls should include history
        last_call = calls[2][1]  # kwargs of last call
        assert 'conversation_history' in last_call
        assert len(last_call['conversation_history']) > 0
    
    def test_chat_with_tool_calls(self, client, auth_headers, project_factory, mock_ai_client):
        """Test chat that includes tool calls."""
        mock_ai_client.generate_code.return_value = {
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
            'created_files': [
                {
                    'filename': 'todo.md',
                    'action': 'updated',
                    'before_content': '- [ ] Old task',
                    'after_content': '- [ ] Task'
                }
            ]
        }
        
        project = project_factory()
        
        response = client.post(f'/api/projects/{project["id"]}/chat', headers=auth_headers,
                              json={'message': 'Add a todo', 'enable_tools': True})
        
        assert response.status_code == 200
        data = response.get_json()
        assert 'tool_calls' in data['response']
        assert len(data['response']['tool_calls']) == 1
        assert data['response']['change_review'][0]['filename'] == 'todo.md'
        assert data['response']['change_review'][0]['summary']
        assert 'Old task' in data['response']['change_review'][0]['diff_excerpt']
        assert 'Task' in data['response']['change_review'][0]['diff_excerpt']

    def test_chat_persists_review_section_in_assistant_transcript(self, client, auth_headers, project_factory, db_path, mock_ai_client):
        """Assistant transcripts should include a lightweight review section for changed files."""
        project = project_factory(language='html')

        mock_ai_client.generate_code.return_value = {
            'success': True,
            'code': '',
            'explanation': 'I refreshed index.html.',
            'suggestions': [],
            'full_response': 'response',
            'model': 'kimi-k2.5',
            'tokens_used': 33,
            'tool_calls': [],
            'created_files': [
                {
                    'filename': 'index.html',
                    'action': 'updated',
                    'before_content': '<body>Old</body>',
                    'after_content': '<body>New</body>'
                }
            ]
        }

        response = client.post(
            f'/api/projects/{project["id"]}/chat',
            headers=auth_headers,
            json={'message': 'Refresh the page'}
        )

        assert response.status_code == 200

        conn = sqlite3.connect(db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        cursor.execute(
            "SELECT content FROM conversations WHERE project_id = ? AND role = 'assistant' ORDER BY created_at DESC LIMIT 1",
            (project['id'],)
        )
        row = cursor.fetchone()
        conn.close()

        assert row is not None
        assert '## Review' in row['content']
        assert '### `index.html`' in row['content']
        assert '```diff' in row['content']

    def test_chat_summarizes_doc_updates_in_response_and_transcript(self, client, auth_headers, project_factory, db_path, mock_ai_client):
        project = project_factory(language='html')

        mock_ai_client.generate_code.return_value = {
            'success': True,
            'code': '',
            'explanation': 'I tightened the plan before building.',
            'suggestions': [],
            'full_response': 'response',
            'model': 'kimi-k2.5',
            'tokens_used': 28,
            'tool_calls': [],
            'created_files': [
                {
                    'filename': 'design.md',
                    'action': 'updated',
                    'before_content': '# Design\n\n- Feature 1',
                    'after_content': '# Design\n\n- Spooky forest theme\n- Two short levels\n'
                },
                {
                    'filename': 'todo.md',
                    'action': 'updated',
                    'before_content': '# Todo\n\n- [ ] Initial setup',
                    'after_content': '# Todo\n\n- [ ] Build the first level\n- [ ] Add falling stars\n'
                }
            ]
        }

        response = client.post(
            f'/api/projects/{project["id"]}/chat',
            headers=auth_headers,
            json={'message': 'Use the spooky forest idea and plan the next build'}
        )

        assert response.status_code == 200
        data = response.get_json()
        assert len(data['response']['doc_updates']) == 2
        assert data['response']['doc_updates'][0]['filename'] == 'design.md'
        assert 'spooky forest theme' in data['response']['doc_updates'][0]['summary'].lower()

        conn = sqlite3.connect(db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        cursor.execute(
            "SELECT content FROM conversations WHERE project_id = ? AND role = 'assistant' ORDER BY created_at DESC LIMIT 1",
            (project['id'],)
        )
        row = cursor.fetchone()
        conn.close()

        assert row is not None
        assert '## Doc updates' in row['content']
        assert '`design.md`' in row['content']
        assert 'spooky forest theme' in row['content'].lower()

    def test_chat_strips_internal_markup_from_visible_response(self, client, auth_headers, project_factory, db_path, mock_ai_client):
        project = project_factory(language='html')

        mock_ai_client.generate_code.return_value = {
            'success': True,
            'code': '',
            'explanation': 'I cleaned this up.\n\ntool_call_begin\nwrite_file\ntool_call_end',
            'suggestions': [],
            'full_response': 'response',
            'model': 'kimi-k2.5',
            'tokens_used': 21,
            'tool_calls': [],
            'created_files': []
        }

        response = client.post(
            f'/api/projects/{project["id"]}/chat',
            headers=auth_headers,
            json={'message': 'Clean it up'}
        )

        assert response.status_code == 200
        data = response.get_json()
        assert 'tool_call_begin' not in data['response']['explanation']

        conn = sqlite3.connect(db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        cursor.execute(
            "SELECT content FROM conversations WHERE project_id = ? AND role = 'assistant' ORDER BY created_at DESC LIMIT 1",
            (project['id'],)
        )
        row = cursor.fetchone()
        conn.close()

        assert row is not None
        assert 'tool_call_begin' not in row['content']

    def test_chat_returns_synced_code_after_tool_written_primary_file(self, client, auth_headers, project_factory, db_path):
        """Tool-based code writes should refresh current_code from project_files."""

        project = project_factory(language='p5js')
        project_id = project['id']

        class FakeAIClient:
            def generate_code(self, **kwargs):
                conn = sqlite3.connect(db_path)
                cursor = conn.cursor()
                cursor.execute('''
                    INSERT INTO project_files (project_id, filename, content)
                    VALUES (?, ?, ?)
                ''', (project_id, 'sketch.js', 'function draw() { ellipse(20, 20, 20, 20); }'))
                conn.commit()
                conn.close()
                return {
                    'success': True,
                    'code': '',
                    'explanation': 'Wrote sketch.js',
                    'suggestions': [],
                    'full_response': 'response',
                    'model': 'kimi-k2.5',
                    'tokens_used': 42,
                    'tool_calls': [
                        {
                            'tool': 'write_file',
                            'input': {'filename': 'sketch.js'},
                            'result': {'success': True, 'action': 'created'}
                        }
                    ],
                    'created_files': [{'filename': 'sketch.js', 'action': 'created'}]
                }

        with patch('chat.routes.get_ai_client', return_value=FakeAIClient()):
            response = client.post(
                f'/api/projects/{project_id}/chat',
                headers=auth_headers,
                json={'message': 'Create a sketch with tools', 'enable_tools': True}
            )

        assert response.status_code == 200
        data = response.get_json()
        assert 'ellipse' in data['response']['code']

        conn = sqlite3.connect(db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        cursor.execute('SELECT current_code FROM projects WHERE id = ?', (project_id,))
        row = cursor.fetchone()
        conn.close()

        assert 'ellipse' in row['current_code']

    def test_chat_returns_synced_code_after_filename_tagged_multi_file_response(self, client, auth_headers, project_factory, db_path):
        """Filename-tagged multi-file writes should update current_code and report the entry file."""

        project = project_factory(language='html')
        project_id = project['id']

        class FakeAIClient:
            def generate_code(self, **kwargs):
                conn = sqlite3.connect(db_path)
                cursor = conn.cursor()
                cursor.execute('''
                    INSERT INTO project_files (project_id, filename, content)
                    VALUES (?, ?, ?)
                ''', (project_id, 'index.html', '<!DOCTYPE html><html><body><script src="main.js"></script></body></html>'))
                cursor.execute('''
                    INSERT INTO project_files (project_id, filename, content)
                    VALUES (?, ?, ?)
                ''', (project_id, 'main.js', 'console.log("ready");'))
                conn.commit()
                conn.close()
                return {
                    'success': True,
                    'code': '',
                    'explanation': 'I split the project into index.html and main.js.',
                    'suggestions': ['Add a score counter'],
                    'full_response': 'response',
                    'model': 'kimi-k2.5',
                    'tokens_used': 55,
                    'tool_calls': [],
                    'created_files': [
                        {'filename': 'index.html', 'action': 'created'},
                        {'filename': 'main.js', 'action': 'created'}
                    ],
                    'primary_file': 'index.html'
                }

        with patch('chat.routes.get_ai_client', return_value=FakeAIClient()):
            response = client.post(
                f'/api/projects/{project_id}/chat',
                headers=auth_headers,
                json={'message': 'Make this a multi-file web project', 'enable_tools': True}
            )

        assert response.status_code == 200
        data = response.get_json()
        assert data['response']['primary_file'] == 'index.html'
        assert '<!DOCTYPE html>' in data['response']['code']
        assert len(data['response']['changed_files']) == 2

        conn = sqlite3.connect(db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        cursor.execute('SELECT current_code FROM projects WHERE id = ?', (project_id,))
        row = cursor.fetchone()
        conn.close()

        assert '<!DOCTYPE html>' in row['current_code']

    def test_chat_returns_workflow_rationale_and_questions_and_persists_them(self, client, auth_headers, project_factory, db_path, mock_ai_client):
        project = project_factory(language='html')

        mock_ai_client.generate_code.return_value = {
            'success': True,
            'code': '',
            'explanation': 'I turned this into a small playable prototype first.',
            'decision_notes': [
                'Started with one screen so the loop is easier to test.',
                'Kept the controls simple for a first pass.'
            ],
            'assumptions': ['Single player for now.'],
            'follow_up_questions': ['Should collecting stars happen with clicks or movement?'],
            'suggestions': ['Add a score bar'],
            'full_response': 'response',
            'model': 'kimi-k2.5',
            'tokens_used': 61,
            'tool_calls': [],
            'created_files': []
        }

        response = client.post(
            f'/api/projects/{project["id"]}/chat',
            headers=auth_headers,
            json={'message': 'Make a star collecting game'}
        )

        assert response.status_code == 200
        data = response.get_json()
        assert data['response']['decision_notes'][0].startswith('Started with one screen')
        assert data['response']['assumptions'] == ['Single player for now.']
        assert data['response']['follow_up_questions'] == ['Should collecting stars happen with clicks or movement?']
        assert data['response']['workflow']['phase'] == 'guided-kickoff'

        conn = sqlite3.connect(db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        cursor.execute(
            "SELECT content FROM conversations WHERE project_id = ? AND role = 'assistant' ORDER BY created_at DESC LIMIT 1",
            (project['id'],)
        )
        row = cursor.fetchone()
        conn.close()

        assert row is not None
        assert '## Why this approach' in row['content']
        assert '## Assumptions' in row['content']
        assert '## Questions for you' in row['content']
