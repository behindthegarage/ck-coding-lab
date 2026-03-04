# ai_client.py - AI Model Integration for Club Kinawa Coding Lab

"""
ai_client.py - AI Model Integration with Tool Use for Agentic Workflow

CRITICAL: This file calls Kimi K2.5 API DIRECTLY.
    Do NOT route through OpenClaw gateway — it's not an API proxy.
    
    OpenClaw gateway = Control plane for assistants (localhost:18789)
    Kimi API = ai_client.py calls https://api.kimi.com/coding/v1/messages

Uses Anthropic Messages API format with tool use support.
"""

import os
import json
import re
from typing import List, Dict, Optional, Callable
from datetime import datetime

from database import get_db, row_to_dict


# Language-specific context appended to agent.md
LANGUAGE_CONTEXT = {
    "p5js": """
## CURRENT PROJECT: P5.JS

You are helping with a p5.js project (JavaScript creative coding library).

**p5.js specifics:**
- Use `setup()` and `draw()` functions
- `createCanvas(width, height)` in setup
- Use p5.js key constants: UP_ARROW, DOWN_ARROW, LEFT_ARROW, RIGHT_ARROW (not UP, DOWN, LEFT, RIGHT)
- Available: all p5.js functions (circle, rect, fill, background, etc.)

**Output format:**
Generate p5.js code in a markdown block. Brief explanation before, suggestions after.
""",
    "html": """
## CURRENT PROJECT: HTML/CSS/JS

You are helping with an HTML project (web page or web game).

**HTML specifics:**
- Generate complete, valid HTML documents
- Include CSS in <style> tags and JS in <script> tags
- Or use external files if the project has multiple components

**Output format:**
Generate HTML in a markdown block. Brief explanation before, suggestions after.
""",
    "python": """
## CURRENT PROJECT: PYTHON

You are helping with a Python project.

**Python specifics:**
- Write clean, readable Python code
- Use functions and classes appropriately
- Include if __name__ == "__main__": block for runnable scripts
- Use type hints where they add clarity (optional but helpful)

**Output format:**
Generate Python code in a markdown block. Brief explanation before, suggestions after.
"""
}

UNDECIDED_CONTEXT = """
## CURRENT PROJECT: NOT YET DECIDED

The user hasn't chosen a language yet. This is the beginning of the project.

**Your job:** Help them decide on the best technology stack for their idea.

**Questions to ask:**
- What kind of project is this? (Game, website, tool, animation?)
- Where should it run? (Browser, their computer, phone?)
- Do they need to share it with others easily?
- Is it visual or text-based?

**Options to present:**
- **p5.js** — Games, animations, visual art. Runs in browser. Easy to share.
- **HTML/CSS/JS** — Websites, web apps, interactive pages. Runs in browser. Most flexible.
- **Python** — Scripts, data processing, text-based games. Runs on their computer. Great for learning programming concepts.

Once they choose (or you agree on a direction), start building with that choice.
"""


class FileTools:
    """Tools for AI to interact with project files."""
    
    def __init__(self, project_id: int):
        self.project_id = project_id
    
    def read_file(self, filename: str) -> Dict:
        """Read a file from the project."""
        try:
            with get_db() as db:
                db.execute('''
                    SELECT content FROM project_files
                    WHERE project_id = ? AND filename = ?
                ''', (self.project_id, filename))
                
                row = db.fetchone()
                if row:
                    return {
                        "success": True,
                        "filename": filename,
                        "content": row['content'],
                        "exists": True
                    }
                else:
                    return {
                        "success": True,
                        "filename": filename,
                        "content": "",
                        "exists": False
                    }
        except Exception as e:
            return {
                "success": False,
                "error": str(e),
                "filename": filename
            }
    
    def write_file(self, filename: str, content: str) -> Dict:
        """Write or overwrite a file in the project."""
        try:
            with get_db() as db:
                # Check if file exists
                db.execute('''
                    SELECT id FROM project_files
                    WHERE project_id = ? AND filename = ?
                ''', (self.project_id, filename))
                
                existing = db.fetchone()
                
                if existing:
                    # Update
                    db.execute('''
                        UPDATE project_files
                        SET content = ?, updated_at = CURRENT_TIMESTAMP
                        WHERE id = ?
                    ''', (content, existing['id']))
                    action = "updated"
                else:
                    # Create
                    db.execute('''
                        INSERT INTO project_files (project_id, filename, content)
                        VALUES (?, ?, ?)
                    ''', (self.project_id, filename, content))
                    action = "created"
                
                return {
                    "success": True,
                    "filename": filename,
                    "action": action,
                    "content_length": len(content)
                }
        except Exception as e:
            return {
                "success": False,
                "error": str(e),
                "filename": filename
            }
    
    def append_file(self, filename: str, content: str) -> Dict:
        """Append content to a file (creates if doesn't exist)."""
        try:
            with get_db() as db:
                # Check if file exists
                db.execute('''
                    SELECT id, content FROM project_files
                    WHERE project_id = ? AND filename = ?
                ''', (self.project_id, filename))
                
                existing = db.fetchone()
                
                if existing:
                    # Append
                    new_content = existing['content'] + content
                    db.execute('''
                        UPDATE project_files
                        SET content = ?, updated_at = CURRENT_TIMESTAMP
                        WHERE id = ?
                    ''', (new_content, existing['id']))
                    action = "appended"
                else:
                    # Create new
                    db.execute('''
                        INSERT INTO project_files (project_id, filename, content)
                        VALUES (?, ?, ?)
                    ''', (self.project_id, filename, content))
                    action = "created"
                
                return {
                    "success": True,
                    "filename": filename,
                    "action": action,
                    "appended_length": len(content)
                }
        except Exception as e:
            return {
                "success": False,
                "error": str(e),
                "filename": filename
            }
    
    def list_files(self) -> Dict:
        """List all files in the project."""
        try:
            with get_db() as db:
                db.execute('''
                    SELECT filename, updated_at
                    FROM project_files
                    WHERE project_id = ?
                    ORDER BY filename
                ''', (self.project_id,))
                
                files = [{"filename": row['filename'], "updated_at": row['updated_at']} 
                        for row in db.fetchall()]
                
                return {
                    "success": True,
                    "files": files,
                    "count": len(files)
                }
        except Exception as e:
            return {
                "success": False,
                "error": str(e)
            }
    
    def get_tool_definitions(self) -> List[Dict]:
        """Get tool definitions for the AI."""
        return [
            {
                "name": "read_file",
                "description": "Read the content of a project file. Use this to check current state before making changes.",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "filename": {
                            "type": "string",
                            "description": "The name of the file to read (e.g., 'design.md', 'todo.md', 'main.js')"
                        }
                    },
                    "required": ["filename"]
                }
            },
            {
                "name": "write_file",
                "description": "Write or overwrite a project file. Use this to save designs, architecture, todo lists, or code.",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "filename": {
                            "type": "string",
                            "description": "The name of the file to write (e.g., 'design.md', 'main.js')"
                        },
                        "content": {
                            "type": "string",
                            "description": "The content to write to the file"
                        }
                    },
                    "required": ["filename", "content"]
                }
            },
            {
                "name": "append_file",
                "description": "Append content to the end of a project file. Useful for adding to session logs or notes.",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "filename": {
                            "type": "string",
                            "description": "The name of the file to append to (e.g., 'notes.md', 'session.log')"
                        },
                        "content": {
                            "type": "string",
                            "description": "The content to append to the file"
                        }
                    },
                    "required": ["filename", "content"]
                }
            },
            {
                "name": "list_files",
                "description": "List all files in the project to see what exists.",
                "input_schema": {
                    "type": "object",
                    "properties": {}
                }
            }
        ]
    
    def execute_tool(self, tool_name: str, tool_input: Dict) -> Dict:
        """Execute a tool by name."""
        if tool_name == "read_file":
            return self.read_file(tool_input.get("filename"))
        elif tool_name == "write_file":
            return self.write_file(tool_input.get("filename"), tool_input.get("content", ""))
        elif tool_name == "append_file":
            return self.append_file(tool_input.get("filename"), tool_input.get("content", ""))
        elif tool_name == "list_files":
            return self.list_files()
        else:
            return {"success": False, "error": f"Unknown tool: {tool_name}"}


class AIClient:
    """
    Client for Kimi K2.5 API (direct API calls, not through OpenClaw).
    Uses Anthropic Messages API format with tool use support.
    """
    
    def __init__(self):
        # Kimi API configuration
        self.api_key = os.environ.get('KIMI_API_KEY')
        self.base_url = "https://api.kimi.com/coding"
        self.model = "k2p5"  # Kimi K2.5 model ID
        
        if not self.api_key:
            raise ValueError("KIMI_API_KEY environment variable is required")
        
        # Load agent.md system prompt
        self.base_system_prompt = self._load_agent_prompt()
    
    def _load_agent_prompt(self) -> str:
        """Load the agent.md system prompt."""
        prompt_path = os.path.join(os.path.dirname(__file__), 'prompts', 'agent.md')
        try:
            with open(prompt_path, 'r') as f:
                return f.read()
        except FileNotFoundError:
            print(f"Warning: agent.md not found at {prompt_path}, using default")
            return "You are Hari, a helpful coding assistant."
    
    def _get_system_prompt(self, language: str, project_files: Dict[str, str] = None) -> str:
        """Build the full system prompt for a given language."""
        base = self.base_system_prompt
        
        # Add project context if available
        if project_files:
            context_section = "\n\n## CURRENT PROJECT STATE\n\n"
            for filename, content in sorted(project_files.items()):
                # Truncate very long files
                display_content = content if len(content) < 2000 else content[:2000] + "\n... [truncated]"
                context_section += f"### {filename}\n```\n{display_content}\n```\n\n"
            base = base + context_section
        
        if language == 'undecided' or not language:
            return f"{base}\n\n{UNDECIDED_CONTEXT}"
        
        lang_context = LANGUAGE_CONTEXT.get(language, LANGUAGE_CONTEXT["p5js"])
        return f"{base}\n\n{lang_context}"
    
    def _load_project_files(self, project_id: int) -> Dict[str, str]:
        """Load all project files for context."""
        try:
            with get_db() as db:
                db.execute('''
                    SELECT filename, content FROM project_files
                    WHERE project_id = ?
                    ORDER BY filename
                ''', (project_id,))
                
                return {row['filename']: row['content'] for row in db.fetchall()}
        except Exception as e:
            print(f"Error loading project files: {e}")
            return {}
    
    def generate_code(
        self,
        message: str,
        conversation_history: Optional[List[Dict]],
        current_code: str,
        language: str = "undecided",
        model: str = "kimi-k2.5",
        project_id: int = None,
        enable_tools: bool = True
    ) -> Dict:
        """
        Generate code from a user's natural language request.
        
        Args:
            message: The user's request
            conversation_history: Previous messages for context
            current_code: The current code in the project
            language: Which language mode ('p5js', 'html', 'python', or 'undecided')
            model: Which AI model to use (default: kimi-k2.5)
            project_id: The project ID for file operations
            enable_tools: Whether to enable tool use
            
        Returns:
            Dict with success, code, explanation, suggestions, full_response, tool_calls, created_files
        """
        try:
            # Load project files for context
            project_files = {}
            if project_id:
                project_files = self._load_project_files(project_id)
            
            # Build messages for the API
            messages_data = self._build_messages(
                message, conversation_history, current_code, 
                language, project_files, enable_tools, project_id
            )
            
            # Call Kimi API
            response = self._call_kimi(messages_data, enable_tools and project_id is not None)
            
            if not response.get("success"):
                return {
                    "success": False,
                    "error": response.get("error", "Unknown error")
                }
            
            # Process tool use if present
            tool_calls = []
            tool_created_files = []
            final_content = response.get("content", "")
            
            if response.get("tool_calls") and project_id:
                file_tools = FileTools(project_id)
                
                for tool_call in response["tool_calls"]:
                    tool_name = tool_call.get("name")
                    tool_input = tool_call.get("input", {})
                    
                    # Execute the tool
                    tool_result = file_tools.execute_tool(tool_name, tool_input)
                    tool_calls.append({
                        "tool": tool_name,
                        "input": tool_input,
                        "result": tool_result
                    })
                    
                    # Track files created by write_file or append_file
                    if tool_name in ["write_file", "append_file"] and tool_result.get("success"):
                        tool_created_files.append({
                            "filename": tool_input.get("filename", "unknown"),
                            "action": tool_result.get("action", "created")
                        })
                
                # Make a second call to get the AI's response after tool use
                final_content = self._continue_after_tools(
                    message, conversation_history, current_code, 
                    language, project_files, tool_calls, project_id
                )
            
            # Extract code, explanation, suggestions, and file declarations from response
            parsed = self._parse_response(final_content, language, project_id)
            
            # Combine files from tool calls and parsed text declarations
            all_created_files = tool_created_files + parsed.get("created_files", [])
            
            return {
                "success": True,
                "code": parsed["code"],
                "explanation": parsed["explanation"],
                "suggestions": parsed["suggestions"],
                "full_response": final_content,
                "tokens_used": response.get("tokens_used", 0),
                "model": "kimi-k2.5",
                "tool_calls": tool_calls,
                "created_files": all_created_files
            }
            
        except Exception as e:
            print(f"Error in generate_code: {e}")
            import traceback
            traceback.print_exc()
            return {
                "success": False,
                "error": str(e)
            }
    
    def _build_messages(
        self,
        message: str,
        conversation_history: Optional[List[Dict]],
        current_code: str,
        language: str = "undecided",
        project_files: Dict[str, str] = None,
        enable_tools: bool = True,
        project_id: int = None
    ):
        """Build the message list for the Kimi API (Anthropic Messages format)."""
        # Get the full system prompt for this language
        system_content = self._get_system_prompt(language, project_files)
        
        # Map language to code block language identifier
        code_lang_map = {
            "p5js": "javascript",
            "html": "html",
            "python": "python"
        }
        code_lang = code_lang_map.get(language, "")
        
        messages = []
        
        # Add context about current code if it exists
        if current_code and current_code.strip():
            messages.append({
                "role": "user",
                "content": f"Here is my current code:\n```{code_lang}\n{current_code}\n```"
            })
        
        # Add conversation history
        if conversation_history:
            for msg in conversation_history[-10:]:  # Keep last 10 messages for context
                role = msg.get("role", "user")
                content = msg.get("content", "")
                if role in ["user", "assistant"]:
                    messages.append({"role": role, "content": content})
        
        # Add the current message
        messages.append({"role": "user", "content": message})
        
        # Build tools if enabled
        tools = None
        if enable_tools and project_id:
            file_tools = FileTools(project_id)
            tools = file_tools.get_tool_definitions()
        
        return messages, system_content, tools
    
    def _continue_after_tools(
        self,
        message: str,
        conversation_history: Optional[List[Dict]],
        current_code: str,
        language: str,
        project_files: Dict[str, str],
        tool_calls: List[Dict],
        project_id: int
    ) -> str:
        """Make a follow-up call after tool execution to get final response."""
        try:
            import requests
            
            code_lang_map = {"p5js": "javascript", "html": "html", "python": "python"}
            code_lang = code_lang_map.get(language, "")
            
            messages = []
            
            if current_code and current_code.strip():
                messages.append({
                    "role": "user",
                    "content": f"Here is my current code:\n```{code_lang}\n{current_code}\n```"
                })
            
            if conversation_history:
                for msg in conversation_history[-10:]:
                    role = msg.get("role", "user")
                    content = msg.get("content", "")
                    if role in ["user", "assistant"]:
                        messages.append({"role": role, "content": content})
            
            # Build tool results message
            tool_results_text = "I executed the following tools:\n\n"
            for tc in tool_calls:
                tool_results_text += f"Tool: {tc['tool']}\n"
                tool_results_text += f"Input: {json.dumps(tc['input'])}\n"
                tool_results_text += f"Result: {json.dumps(tc['result'])}\n\n"
            
            messages.append({"role": "user", "content": message})
            messages.append({"role": "assistant", "content": tool_results_text})
            
            system_content = self._get_system_prompt(language, project_files)
            
            data = {
                "model": self.model,
                "messages": messages,
                "system": system_content,
                "max_tokens": 4096,
                "temperature": 0.7
            }
            
            headers = {
                "x-api-key": self.api_key,
                "anthropic-version": "2023-06-01",
                "Content-Type": "application/json"
            }
            
            response = requests.post(
                f"{self.base_url}/v1/messages",
                headers=headers,
                json=data,
                timeout=120
            )
            
            if response.status_code == 200:
                result = response.json()
                return result.get("content", [{}])[0].get("text", "")
            else:
                return ""
                
        except Exception as e:
            print(f"Error in continue_after_tools: {e}")
            return ""
    
    def _call_kimi(self, messages_data, enable_tools: bool = False) -> Dict:
        """Call Kimi K2.5 API directly using Anthropic Messages format."""
        try:
            import requests
            
            messages, system_content, tools = messages_data
            
            # Anthropic Messages API format
            data = {
                "model": self.model,
                "messages": messages,
                "system": system_content,
                "max_tokens": 4096,
                "temperature": 0.7
            }
            
            # Add tools if enabled
            if enable_tools and tools:
                data["tools"] = tools
            
            headers = {
                "x-api-key": self.api_key,
                "anthropic-version": "2023-06-01",  # Required for Anthropic format
                "Content-Type": "application/json"
            }
            
            print(f"Calling Kimi API at {self.base_url}/v1/messages")
            print(f"Messages count: {len(messages)}")
            if enable_tools:
                print(f"Tools enabled: {len(tools)} tools")
            
            response = requests.post(
                f"{self.base_url}/v1/messages",
                headers=headers,
                json=data,
                timeout=120
            )
            
            print(f"Response status: {response.status_code}")
            
            if response.status_code == 200:
                result = response.json()
                content_blocks = result.get("content", [])
                usage = result.get("usage", {})
                
                # Extract text content and tool calls
                text_content = ""
                tool_calls = []
                
                for block in content_blocks:
                    if block.get("type") == "text":
                        text_content += block.get("text", "")
                    elif block.get("type") == "tool_use":
                        tool_calls.append({
                            "id": block.get("id"),
                            "name": block.get("name"),
                            "input": block.get("input", {})
                        })
                
                return {
                    "success": True,
                    "content": text_content,
                    "tool_calls": tool_calls if tool_calls else None,
                    "tokens_used": usage.get("input_tokens", 0) + usage.get("output_tokens", 0)
                }
            else:
                error_text = response.text
                print(f"API Error: {response.status_code} - {error_text}")
                return {
                    "success": False,
                    "error": f"API Error {response.status_code}: {error_text}"
                }
                
        except requests.exceptions.Timeout:
            return {
                "success": False,
                "error": "Request timed out. The AI is taking too long to respond."
            }
        except Exception as e:
            print(f"Exception in _call_kimi: {e}")
            import traceback
            traceback.print_exc()
            return {
                "success": False,
                "error": str(e)
            }
    
    def _parse_response(self, content: str, language: str = "undecided", project_id: int = None) -> Dict:
        """
        Parse AI response to extract code, explanation, suggestions, and file declarations.
        
        Args:
            content: The raw AI response text
            language: 'p5js', 'html', 'python', or 'undecided' - affects which code blocks to look for
            project_id: Project ID for saving extracted files
            
        Returns:
            Dict with code, explanation, suggestions, created_files
        """
        result = {
            "code": "",
            "explanation": "",
            "suggestions": [],
            "created_files": []
        }
        
        print(f"_parse_response: content length {len(content)}, project_id={project_id}")
        
        # STEP 1: Extract file declarations from code blocks
        # Pattern: ```language filename or ```language [filename]
        # Examples: ```html index.html, ```css style.css, ```js main.js
        file_pattern = r'```(html|css|js|javascript|python|py)\s*\[?([^\]\n]+)\]?\s*\n(.*?)```'
        file_matches = re.findall(file_pattern, content, re.DOTALL)
        
        # Also look for "File: filename" pattern before code blocks
        file_prefix_pattern = r'(?:File|file):\s*([\w.\-/]+)\s*\n```(html|css|js|javascript|python|py)?\s*\n(.*?)```'
        prefix_matches = re.findall(file_prefix_pattern, content, re.DOTALL)
        
        all_files = []
        
        # Process filename-in-codeblock pattern
        for lang, filename, file_content in file_matches:
            filename = filename.strip()
            if filename and file_content:
                all_files.append({
                    'filename': filename,
                    'content': file_content.strip(),
                    'language': lang
                })
        
        # Process "File: filename" pattern
        for filename, lang, file_content in prefix_matches:
            filename = filename.strip()
            if filename and file_content:
                all_files.append({
                    'filename': filename,
                    'content': file_content.strip(),
                    'language': lang or 'text'
                })
        
        print(f"_parse_response: found {len(all_files)} file declarations")
        
        # Save files to database if project_id is provided
        if project_id and all_files:
            file_tools = FileTools(project_id)
            for file_info in all_files:
                try:
                    tool_result = file_tools.write_file(file_info['filename'], file_info['content'])
                    if tool_result.get('success'):
                        result['created_files'].append({
                            'filename': file_info['filename'],
                            'action': tool_result.get('action', 'created')
                        })
                        print(f"_parse_response: saved file {file_info['filename']}")
                except Exception as e:
                    print(f"_parse_response: error saving file {file_info['filename']}: {e}")
        
        # STEP 2: Extract main code block for backward compatibility
        # Map language to possible code block identifiers
        lang_identifiers = {
            "p5js": ["javascript", "js", ""],
            "html": ["html", ""],
            "python": ["python", "py", ""],
            "undecided": ["javascript", "js", "html", "python", "py", ""]
        }
        identifiers = lang_identifiers.get(language, [""])
        
        # Build regex patterns for each identifier (without filename)
        code_patterns = []
        for ident in identifiers:
            if ident:
                # Pattern without filename - just language tag
                code_patterns.append(rf'```{ident}\s*\n(?!.*index\.html|.*style\.css|.*main\.js|.*dice\.js)(.*?)\n```')
            else:
                code_patterns.append(r'```\s*\n(.*?)(?:\n)?```')
        
        code_matches = []
        for pattern in code_patterns:
            matches = re.findall(pattern, content, re.DOTALL)
            if matches:
                code_matches = matches
                break
        
        print(f"_parse_response: found {len(code_matches)} code blocks for main code")
        
        if code_matches:
            result["code"] = code_matches[0].strip()
            print(f"_parse_response: extracted code length {len(result['code'])}")
        
        # STEP 3: Get explanation - text before first code block
        parts = re.split(r'```(?:\w+)?(?:\s*\[?[^\]]*\]?)?\s*\n?', content, maxsplit=1, flags=re.DOTALL)
        if parts:
            result["explanation"] = parts[0].strip()
            print(f"_parse_response: explanation length {len(result['explanation'])}")
        
        # STEP 4: Extract suggestions from text after code blocks
        if len(parts) > 1:
            after_code_parts = content.split('```')
            if len(after_code_parts) >= 3:
                after_code = ''.join(after_code_parts[2:])
                
                # Look for suggestions - various patterns
                suggestion_patterns = [
                    r'(?:What you could add|Suggestions|Next steps|Try adding|Ideas to try)[\s:]*\n((?:[-*•\d.]\s*.*?\n?)+)',
                    r'(?:\*\*)?(?:What you could add|Suggestions)[\s:]*(?:\*\*)?\n((?:[-*•\d.]\s*.*?\n?)+)',
                    r'\n((?:[-*•]\s*.*?\n)+)',  # Any bullet list
                ]
                for pattern in suggestion_patterns:
                    match = re.search(pattern, after_code, re.IGNORECASE | re.DOTALL)
                    if match:
                        suggestions_text = match.group(1)
                        suggestions = re.findall(r'[-*•\d.]\s*(.*?)(?=\n[-*•\d.]|\Z)', suggestions_text, re.DOTALL)
                        result["suggestions"] = [s.strip() for s in suggestions if s.strip()]
                        break
        
        return result


# Singleton instance
_ai_client = None

def get_ai_client() -> AIClient:
    """Get or create the singleton AI client."""
    global _ai_client
    if _ai_client is None:
        _ai_client = AIClient()
    return _ai_client
