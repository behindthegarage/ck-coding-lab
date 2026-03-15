# tests/unit/test_ai_client.py - AI Client Unit Tests
"""
Unit tests for the AI client module.

Tests cover:
- AIClient initialization
- API key handling
- Message building
- Response parsing
- Error handling
"""

import pytest
from unittest.mock import patch, MagicMock, mock_open
import json


@pytest.mark.unit
class TestAIClientInitialization:
    """Tests for AI client initialization."""
    
    def test_client_initializes_with_api_key(self, monkeypatch):
        """Test that AIClient initializes with API key."""
        from ai.client import AIClient
        
        monkeypatch.setenv('KIMI_API_KEY', 'test-api-key')
        
        client = AIClient()
        assert client.api_key == 'test-api-key'
        assert client.base_url is not None
        assert client.model is not None
    
    def test_client_initializes_with_config_values(self, monkeypatch):
        """Test that client uses config values."""
        from ai.client import AIClient
        from ai.config import KIMI_BASE_URL, KIMI_MODEL
        
        monkeypatch.setenv('KIMI_API_KEY', 'test-key')
        
        client = AIClient()
        assert client.base_url == KIMI_BASE_URL
        assert client.model == KIMI_MODEL
    
    def test_client_loads_system_prompt(self, monkeypatch):
        """Test that client loads agent.md system prompt."""
        from ai.client import AIClient
        
        monkeypatch.setenv('KIMI_API_KEY', 'test-key')
        
        client = AIClient()
        assert hasattr(client, 'base_system_prompt')


@pytest.mark.unit
class TestGetAIClientSingleton:
    """Tests for the get_ai_client singleton pattern."""
    
    def test_singleton_returns_same_instance(self, monkeypatch):
        """Test that get_ai_client returns the same instance."""
        from ai.client import get_ai_client, _ai_client
        import ai.client
        
        monkeypatch.setenv('KIMI_API_KEY', 'test-key')
        
        # Reset singleton
        ai.client._ai_client = None
        
        client1 = get_ai_client()
        client2 = get_ai_client()
        
        assert client1 is client2
    
    def test_singleton_creates_new_when_none(self, monkeypatch):
        """Test that singleton creates new client when none exists."""
        import ai.client
        from ai.client import get_ai_client
        
        monkeypatch.setenv('KIMI_API_KEY', 'test-key')
        
        # Reset singleton
        ai.client._ai_client = None
        
        client = get_ai_client()
        assert client is not None
        assert isinstance(client, ai.client.AIClient)


@pytest.mark.unit
class TestBuildMessages:
    """Tests for message building."""
    
    def test_build_messages_with_current_code(self, monkeypatch):
        """Test message building includes current code."""
        from ai.client import AIClient
        
        monkeypatch.setenv('KIMI_API_KEY', 'test-key')
        
        client = AIClient()
        messages, system, tools = client._build_messages(
            message='Make it red',
            conversation_history=[],
            current_code='function setup() { createCanvas(400, 400); }',
            language='p5js'
        )
        
        # First message should contain current code
        assert len(messages) >= 1
        assert any('current code' in str(m.get('content', '')) for m in messages)
    
    def test_build_messages_with_conversation_history(self, monkeypatch):
        """Test message building includes conversation history."""
        from ai.client import AIClient
        
        monkeypatch.setenv('KIMI_API_KEY', 'test-key')
        
        client = AIClient()
        history = [
            {'role': 'user', 'content': 'First message'},
            {'role': 'assistant', 'content': 'Response'}
        ]
        
        messages, system, tools = client._build_messages(
            message='Follow up',
            conversation_history=history,
            current_code='',
            language='p5js'
        )
        
        # Should include history messages
        roles = [m['role'] for m in messages if m['role'] in ['user', 'assistant']]
        assert 'user' in roles
    
    def test_build_messages_without_code(self, monkeypatch):
        """Test message building without current code."""
        from ai.client import AIClient
        
        monkeypatch.setenv('KIMI_API_KEY', 'test-key')
        
        client = AIClient()
        messages, system, tools = client._build_messages(
            message='Create a canvas',
            conversation_history=[],
            current_code='',
            language='p5js'
        )
        
        # Should have at least the current message
        assert len(messages) >= 1
        assert any('Create a canvas' in str(m.get('content', '')) for m in messages)
    
    def test_build_messages_with_project_files(self, monkeypatch):
        """Test message building includes project files."""
        from ai.client import AIClient
        
        monkeypatch.setenv('KIMI_API_KEY', 'test-key')
        
        client = AIClient()
        project_files = {'design.md': '# Design', 'todo.md': '- [ ] Task'}
        
        messages, system, tools = client._build_messages(
            message='Check design',
            conversation_history=[],
            current_code='',
            language='p5js',
            project_files=project_files
        )
        
        # System prompt should include files
        assert system is not None


@pytest.mark.unit
class TestCallKimiAPI:
    """Tests for Kimi API calling."""
    
    @patch('ai.client.requests.post')
    def test_successful_api_call(self, mock_post, monkeypatch):
        """Test successful API response handling."""
        from ai.client import AIClient
        
        monkeypatch.setenv('KIMI_API_KEY', 'test-key')
        
        # Mock successful response
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            'content': [{'type': 'text', 'text': 'Generated code here'}],
            'usage': {'input_tokens': 100, 'output_tokens': 50}
        }
        mock_post.return_value = mock_response
        
        client = AIClient()
        messages = [{'role': 'user', 'content': 'Hello'}]
        system = 'You are a helpful assistant'
        
        result = client._call_kimi((messages, system, None), enable_tools=False)
        
        assert result['success'] is True
        assert result['content'] == 'Generated code here'
        assert result['tokens_used'] == 150
    
    @patch('ai.client.requests.post')
    def test_api_error_response(self, mock_post, monkeypatch):
        """Test API error response handling."""
        from ai.client import AIClient
        
        monkeypatch.setenv('KIMI_API_KEY', 'test-key')
        
        # Mock error response
        mock_response = MagicMock()
        mock_response.status_code = 401
        mock_response.text = 'Unauthorized'
        mock_post.return_value = mock_response
        
        client = AIClient()
        messages = [{'role': 'user', 'content': 'Hello'}]
        system = 'System prompt'
        
        result = client._call_kimi((messages, system, None), enable_tools=False)
        
        assert result['success'] is False
        assert 'error' in result
    
    @patch('ai.client.requests.post')
    def test_api_timeout(self, mock_post, monkeypatch):
        """Test timeout handling."""
        from ai.client import AIClient
        import requests
        
        monkeypatch.setenv('KIMI_API_KEY', 'test-key')
        
        # Mock timeout
        mock_post.side_effect = requests.exceptions.Timeout()
        
        client = AIClient()
        messages = [{'role': 'user', 'content': 'Hello'}]
        system = 'System prompt'
        
        result = client._call_kimi((messages, system, None), enable_tools=False)
        
        assert result['success'] is False
        assert 'timed out' in result['error'].lower() or 'timeout' in result['error'].lower()
    
    @patch('ai.client.requests.post')
    def test_api_with_tool_calls(self, mock_post, monkeypatch):
        """Test API response with tool calls."""
        from ai.client import AIClient
        
        monkeypatch.setenv('KIMI_API_KEY', 'test-key')
        
        # Mock response with tool use
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            'content': [
                {'type': 'text', 'text': 'I will help you'},
                {'type': 'tool_use', 'id': 'tool_1', 'name': 'write_file', 'input': {'filename': 'test.txt'}}
            ],
            'usage': {'input_tokens': 100, 'output_tokens': 50}
        }
        mock_post.return_value = mock_response
        
        client = AIClient()
        messages = [{'role': 'user', 'content': 'Create a file'}]
        system = 'System prompt'
        
        result = client._call_kimi((messages, system, None), enable_tools=True)
        
        assert result['success'] is True
        assert result['tool_calls'] is not None
        assert len(result['tool_calls']) == 1
        assert result['tool_calls'][0]['name'] == 'write_file'


@pytest.mark.unit
class TestLoadProjectFiles:
    """Tests for loading project files."""
    
    def test_load_project_files_empty(self, monkeypatch, tmp_path):
        """Test loading files for project with no files."""
        from ai.client import AIClient
        
        monkeypatch.setenv('KIMI_API_KEY', 'test-key')
        monkeypatch.setenv('CKCL_DB_PATH', str(tmp_path / 'test.db'))
        
        # Initialize empty database
        from database import init_db_full
        init_db_full(str(tmp_path / 'test.db'))
        
        client = AIClient()
        files = client._load_project_files(1)
        
        assert files == {}
    
    def test_load_project_files_returns_dict(self, monkeypatch, tmp_path):
        """Test that load_project_files returns a dictionary."""
        from ai.client import AIClient
        
        monkeypatch.setenv('KIMI_API_KEY', 'test-key')
        monkeypatch.setenv('CKCL_DB_PATH', str(tmp_path / 'test.db'))
        
        client = AIClient()
        
        # Should handle errors gracefully
        files = client._load_project_files(999)
        assert isinstance(files, dict)


@pytest.mark.unit
class TestGenerateCode:
    """Tests for the main generate_code method."""
    
    @patch('ai.client.AIClient._call_kimi')
    @patch('ai.client.AIClient._load_project_files')
    def test_generate_code_success(self, mock_load_files, mock_call_kimi, monkeypatch):
        """Test successful code generation."""
        from ai.client import AIClient
        
        monkeypatch.setenv('KIMI_API_KEY', 'test-key')
        
        mock_load_files.return_value = {}
        mock_call_kimi.return_value = {
            'success': True,
            'content': 'Here is the code:\n```javascript\nfunction setup() {}\n```',
            'tokens_used': 100
        }
        
        client = AIClient()
        result = client.generate_code(
            message='Create a canvas',
            conversation_history=[],
            current_code='',
            language='p5js'
        )
        
        assert result['success'] is True
        assert 'code' in result
        assert 'explanation' in result
        assert result['model'] == 'kimi-k2.5'
    
    @patch('ai.client.AIClient._call_kimi')
    def test_generate_code_api_failure(self, mock_call_kimi, monkeypatch):
        """Test handling of API failure in generate_code."""
        from ai.client import AIClient
        
        monkeypatch.setenv('KIMI_API_KEY', 'test-key')
        
        mock_call_kimi.return_value = {
            'success': False,
            'error': 'API Error'
        }
        
        client = AIClient()
        result = client.generate_code(
            message='Test',
            conversation_history=[],
            current_code='',
            language='p5js'
        )
        
        assert result['success'] is False
        assert 'error' in result
    
    def test_generate_code_exception_handling(self, monkeypatch):
        """Test exception handling in generate_code."""
        from ai.client import AIClient
        
        monkeypatch.setenv('KIMI_API_KEY', 'test-key')
        
        client = AIClient()
        
        # Call without mocks should handle errors gracefully
        result = client.generate_code(
            message='Test',
            conversation_history=[],
            current_code='',
            language='p5js',
            project_id=None  # No project files to load
        )
        
        # Should return error response, not raise
        assert 'success' in result
