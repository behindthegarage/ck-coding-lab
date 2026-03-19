# ai/client.py - AI Client for Kimi K2.5 API
"""
Client for Kimi K2.5 API (direct API calls, not through OpenClaw).
Uses Anthropic Messages API format with tool use support.
"""

import json
import os
from typing import List, Dict, Optional

import requests

from database import get_db
from ai.config import (
    KIMI_BASE_URL,
    KIMI_MODEL,
    DEFAULT_MAX_TOKENS,
    DEFAULT_TEMPERATURE,
    get_api_key,
    CODE_LANG_MAP
)
from ai.prompts import load_agent_prompt, build_system_prompt
from ai.tools import FileTools
from ai.parser import parse_response
from ai.workflow import analyze_workflow_context


class AIClient:
    """
    Client for Kimi K2.5 API (direct API calls, not through OpenClaw).
    Uses Anthropic Messages API format with tool use support.
    """
    
    def __init__(self):
        # Kimi API configuration
        self.provider = "kimi"
        self.api_key = os.environ.get("KIMI_API_KEY")
        if not self.api_key:
            raise ValueError("KIMI_API_KEY environment variable is required")
        self.base_url = KIMI_BASE_URL
        self.model = KIMI_MODEL
        
        # Load agent.md system prompt
        self.base_system_prompt = load_agent_prompt()
    
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
            
            workflow_context = analyze_workflow_context(
                message=message,
                conversation_history=conversation_history,
                project_files=project_files,
                language=language,
                current_code=current_code,
            )

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
                        latest_change = file_tools.get_change_log()[-1] if file_tools.get_change_log() else {}
                        tool_created_files.append({
                            "filename": tool_input.get("filename", "unknown"),
                            "action": tool_result.get("action", "created"),
                            "before_content": latest_change.get("before_content", ""),
                            "after_content": latest_change.get("after_content", tool_input.get("content", ""))
                        })
                
                # Make a second call to get the AI's response after tool use
                final_content = self._continue_after_tools(
                    messages_data, response["tool_calls"], tool_calls, project_id
                )
            
            # Extract code, explanation, suggestions, and file declarations from response
            parsed = parse_response(final_content, language, project_id)
            
            # Combine files from tool calls and parsed text declarations
            all_created_files = tool_created_files + parsed.get("created_files", [])
            
            return {
                "success": True,
                "code": parsed["code"],
                "explanation": parsed["explanation"],
                "decision_notes": parsed.get("decision_notes", []),
                "assumptions": parsed.get("assumptions", []),
                "follow_up_questions": parsed.get("follow_up_questions", []),
                "suggestions": parsed["suggestions"],
                "full_response": final_content,
                "tokens_used": response.get("tokens_used", 0),
                "model": "kimi-k2.5",
                "tool_calls": tool_calls,
                "created_files": all_created_files,
                "workflow": workflow_context,
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
        workflow_context = analyze_workflow_context(
            message=message,
            conversation_history=conversation_history,
            project_files=project_files,
            language=language,
            current_code=current_code,
        )

        # Get the full system prompt for this language
        system_content = build_system_prompt(
            self.base_system_prompt,
            language,
            project_files,
            tools_enabled=bool(enable_tools and project_id),
            workflow_context=workflow_context,
        )
        
        # Map language to code block language identifier
        code_lang = CODE_LANG_MAP.get(language, "")
        
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
        messages_data: tuple,
        original_tool_calls: List[Dict],
        tool_results: List[Dict],
        project_id: int
    ) -> str:
        """Make a follow-up call after tool execution to get final response."""
        try:
            messages, system_content, tools = messages_data
            
            # Build tool_use content blocks for assistant message
            assistant_content = []
            for tool_call in original_tool_calls:
                assistant_content.append({
                    "type": "tool_use",
                    "id": tool_call.get("id", ""),
                    "name": tool_call.get("name", ""),
                    "input": tool_call.get("input", {})
                })
            
            # Append assistant message that requested the tools
            messages.append({
                "role": "assistant", 
                "content": assistant_content
            })
            
            # Build tool_result content blocks for user message
            user_content = []
            for i_tc, tc in enumerate(tool_results):
                tool_use_id = original_tool_calls[i_tc].get("id", "") if i_tc < len(original_tool_calls) else ""
                user_content.append({
                    "type": "tool_result",
                    "tool_use_id": tool_use_id,
                    "content": json.dumps(tc['result'])
                })
            
            # Append user message with tool results
            messages.append({
                "role": "user",
                "content": user_content
            })
            
            data = {
                "model": self.model,
                "messages": messages,
                "system": system_content,
                "max_tokens": DEFAULT_MAX_TOKENS,
                "temperature": DEFAULT_TEMPERATURE
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
                timeout=600
            )
            
            if response.status_code == 200:
                result = response.json()
                content_blocks = result.get("content", [])
                text_content = ""
                for block in content_blocks:
                    if block.get("type") == "text":
                        text_content += block.get("text", "")
                return text_content
            else:
                print(f"API error in continue_after_tools: {response.status_code}")
                return ""
                
        except Exception as e:
            print(f"Error in continue_after_tools: {e}")
            import traceback
            traceback.print_exc()
            return ""
    
    def _call_kimi(self, messages_data, enable_tools: bool = False) -> Dict:
        """Call Kimi K2.5 API directly using Anthropic Messages format."""
        try:
            messages, system_content, tools = messages_data
            
            # Anthropic Messages API format
            data = {
                "model": self.model,
                "messages": messages,
                "system": system_content,
                "max_tokens": DEFAULT_MAX_TOKENS,
                "temperature": DEFAULT_TEMPERATURE
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
                print(f"Tools enabled: {len(tools) if tools else 0} tools")
            
            response = requests.post(
                f"{self.base_url}/v1/messages",
                headers=headers,
                json=data,
                timeout=600
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


# Singleton instance
_ai_client = None


def get_ai_client() -> AIClient:
    """Get or create the singleton AI client."""
    global _ai_client
    if _ai_client is None:
        _ai_client = AIClient()
    return _ai_client
