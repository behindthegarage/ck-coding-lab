# tests/unit/test_ai_parser.py - AI response parsing tests
"""
Unit tests for AI response parsing and code extraction.

Tests cover:
- Code block extraction from markdown
- Response parsing
- Tool call handling
"""

import pytest
import re

from ai.parser import parse_response


@pytest.mark.unit
class TestCodeExtraction:
    """Tests for extracting code from AI responses."""
    
    def test_extract_code_from_markdown_block(self):
        """Test extracting code from markdown code blocks."""
        response = '''
Here's your code:

```javascript
function setup() {
    createCanvas(400, 400);
}
```

Let me know if you need help!
'''
        # Extract code between ```javascript and ```
        pattern = r'```(?:javascript|js)?\n(.*?)```'
        match = re.search(pattern, response, re.DOTALL)
        
        assert match is not None
        code = match.group(1).strip()
        assert 'function setup()' in code
    
    def test_extract_code_without_language_tag(self):
        """Test extracting code from plain code blocks."""
        response = '''
Here's the code:

```
function draw() {
    ellipse(100, 100, 50, 50);
}
```
'''
        pattern = r'```\n(.*?)```'
        match = re.search(pattern, response, re.DOTALL)
        
        assert match is not None
        assert 'function draw()' in match.group(1)
    
    def test_no_code_block_returns_none(self):
        """Test that responses without code blocks are handled."""
        response = "Here's an explanation without code."
        
        pattern = r'```(?:\w+)?\n(.*?)```'
        match = re.search(pattern, response, re.DOTALL)
        
        assert match is None
    
    def test_extract_python_code(self):
        """Test extracting Python code blocks."""
        response = '''
Here's a Python example:

```python
def hello():
    print("Hello, World!")
```
'''
        pattern = r'```(?:python)?\n(.*?)```'
        match = re.search(pattern, response, re.DOTALL)
        
        assert match is not None
        assert 'def hello():' in match.group(1)
    
    def test_extract_html_code(self):
        """Test extracting HTML code blocks."""
        response = '''
Here's the HTML:

```html
<!DOCTYPE html>
<html>
<head><title>Test</title></head>
<body><h1>Hello</h1></body>
</html>
```
'''
        pattern = r'```(?:html)?\n(.*?)```'
        match = re.search(pattern, response, re.DOTALL)
        
        assert match is not None
        assert '<!DOCTYPE html>' in match.group(1)
    
    def test_multiple_code_blocks(self):
        """Test handling responses with multiple code blocks."""
        response = '''
First function:
```javascript
function setup() {
    createCanvas(400, 400);
}
```

Then draw:
```javascript
function draw() {
    background(220);
}
```
'''
        pattern = r'```(?:javascript|js)?\n(.*?)```'
        matches = re.findall(pattern, response, re.DOTALL)
        
        assert len(matches) == 2
        assert 'function setup()' in matches[0]
        assert 'function draw()' in matches[1]


@pytest.mark.unit
class TestResponseStructure:
    """Tests for AI response structure handling."""
    
    def test_response_has_required_fields(self, mock_ai_response):
        """Test that mock response has all required fields."""
        required_fields = ['success', 'code', 'explanation', 'suggestions', 'model', 'tokens_used']
        
        for field in required_fields:
            assert field in mock_ai_response
    
    def test_successful_response_structure(self):
        """Test successful response format."""
        response = {
            'success': True,
            'code': 'function setup() {}',
            'explanation': 'Creates a canvas',
            'suggestions': ['Add color'],
            'model': 'kimi-k2.5',
            'tokens_used': 100
        }
        
        assert response['success'] is True
        assert isinstance(response['code'], str)
        assert isinstance(response['suggestions'], list)
        assert isinstance(response['tokens_used'], int)
    
    def test_error_response_structure(self):
        """Test error response format."""
        response = {
            'success': False,
            'error': 'Rate limit exceeded',
            'code': None,
            'explanation': None
        }
        
        assert response['success'] is False
        assert 'error' in response


@pytest.mark.unit
class TestToolCallParsing:
    """Tests for parsing tool calls from AI responses."""
    
    def test_simple_tool_call_format(self):
        """Test parsing a simple tool call."""
        tool_call = {
            'tool': 'write_file',
            'input': {
                'filename': 'design.md',
                'content': '# Design'
            },
            'result': {
                'success': True,
                'action': 'created'
            }
        }
        
        assert tool_call['tool'] == 'write_file'
        assert tool_call['input']['filename'] == 'design.md'
        assert tool_call['result']['success'] is True
    
    def test_tool_call_list(self):
        """Test parsing multiple tool calls."""
        tool_calls = [
            {
                'tool': 'read_file',
                'input': {'filename': 'design.md'},
                'result': {'content': '# Design', 'exists': True}
            },
            {
                'tool': 'write_file',
                'input': {'filename': 'todo.md', 'content': '# Todo'},
                'result': {'success': True, 'action': 'created'}
            }
        ]
        
        assert len(tool_calls) == 2
        assert tool_calls[0]['tool'] == 'read_file'
        assert tool_calls[1]['tool'] == 'write_file'
    
    def test_tool_call_with_error_result(self):
        """Test parsing tool call with error result."""
        tool_call = {
            'tool': 'write_file',
            'input': {'filename': 'test.md', 'content': 'content'},
            'result': {
                'success': False,
                'error': 'Permission denied'
            }
        }
        
        assert tool_call['result']['success'] is False
        assert 'error' in tool_call['result']


@pytest.mark.unit
class TestParserFileRecovery:
    """Tests for recovering filename-tagged files from imperfect model output."""

    def test_saves_filename_tagged_file_without_closing_fence(self, db_connection):
        """If the model response is clipped, recover and persist the file anyway."""
        db_connection.execute('''
            INSERT INTO users (username, pin_hash, role, is_active)
            VALUES (?, ?, ?, ?)
        ''', ('parser_user', 'hash', 'kid', 1))
        user_id = db_connection.lastrowid

        db_connection.execute('''
            INSERT INTO projects (user_id, name, description, language)
            VALUES (?, ?, ?, ?)
        ''', (user_id, 'Parser Test', 'Recover truncated file', 'html'))
        project_id = db_connection.lastrowid
        db_connection.connection.commit()

        content = '''
Here you go — writing the file now.

```html index.html
<!DOCTYPE html>
<html>
  <head><title>Recovered</title></head>
  <body>Hello</body>
</html>
'''

        result = parse_response(content, 'html', project_id)

        assert any(f['filename'] == 'index.html' for f in result['created_files'])

        db_connection.execute(
            'SELECT content FROM project_files WHERE project_id = ? AND filename = ?',
            (project_id, 'index.html')
        )
        saved = db_connection.fetchone()
        assert saved is not None
        assert '<title>Recovered</title>' in saved['content']

    def test_ignores_tool_summary_when_recovering_truncated_file(self, db_connection):
        """Tool call summaries should not be written into recovered file contents."""
        db_connection.execute('''
            INSERT INTO users (username, pin_hash, role, is_active)
            VALUES (?, ?, ?, ?)
        ''', ('parser_user_2', 'hash', 'kid', 1))
        user_id = db_connection.lastrowid

        db_connection.execute('''
            INSERT INTO projects (user_id, name, description, language)
            VALUES (?, ?, ?, ?)
        ''', (user_id, 'Parser Test 2', 'Ignore tool summary', 'html'))
        project_id = db_connection.lastrowid
        db_connection.connection.commit()

        content = '''
The file wasn't created. Let me write it properly now:

```html index.html
<!DOCTYPE html>
<html>
  <body>Asteroids</body>
</html>

---

**Tool Calls:**
- `read_file`: index.html → executed
'''

        result = parse_response(content, 'html', project_id)

        assert any(f['filename'] == 'index.html' for f in result['created_files'])

        db_connection.execute(
            'SELECT content FROM project_files WHERE project_id = ? AND filename = ?',
            (project_id, 'index.html')
        )
        saved = db_connection.fetchone()
        assert saved is not None
        assert '**Tool Calls:**' not in saved['content']
        assert 'read_file' not in saved['content']


@pytest.mark.unit
class TestCodeValidationIntegration:
    """Tests for integration between AI parsing and sandbox."""
    
    def test_extracted_code_passes_sandbox(self):
        """Test that extracted code can be validated by sandbox."""
        from sandbox import CodeValidator
        
        ai_response = '''
Here's your code:

```javascript
function setup() {
    createCanvas(400, 400);
    background(220);
}

function draw() {
    ellipse(200, 200, 100, 100);
}
```

This creates a canvas with a circle.
'''
        # Extract code
        pattern = r'```(?:javascript|js)?\n(.*?)```'
        match = re.search(pattern, ai_response, re.DOTALL)
        assert match is not None
        
        code = match.group(1).strip()
        
        # Validate with sandbox
        validator = CodeValidator()
        is_valid, violations = validator.validate(code)
        
        assert is_valid, f"Valid code should pass sandbox: {violations}"
    
    def test_malicious_code_in_response_detected(self):
        """Test that malicious code in AI response is detected."""
        from sandbox import CodeValidator
        
        malicious_response = '''
```javascript
function setup() {
    eval("fetch('https://evil.com')");
}
```
'''
        # Extract code
        pattern = r'```(?:javascript|js)?\n(.*?)```'
        match = re.search(pattern, malicious_response, re.DOTALL)
        code = match.group(1).strip()
        
        # Validate
        validator = CodeValidator()
        is_valid, violations = validator.validate(code)
        
        assert not is_valid, "Malicious code should be blocked"
        assert any("eval" in v or "fetch" in v for v in violations)


@pytest.mark.unit
class TestTokenCounting:
    """Tests for token usage tracking."""
    
    def test_tokens_used_is_numeric(self, mock_ai_response):
        """Test that tokens_used is a number."""
        assert isinstance(mock_ai_response['tokens_used'], int)
        assert mock_ai_response['tokens_used'] >= 0
    
    def test_tokens_used_present_in_response(self):
        """Test that response includes token count."""
        response = {
            'success': True,
            'code': 'test',
            'tokens_used': 50
        }
        
        assert 'tokens_used' in response
        assert response['tokens_used'] == 50
