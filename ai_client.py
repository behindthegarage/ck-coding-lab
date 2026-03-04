# ai_client.py - AI Model Integration for Club Kinawa Coding Lab

"""
ai_client.py - AI Model Integration for Club Kinawa Coding Lab

CRITICAL: This file calls Kimi K2.5 API DIRECTLY.
    Do NOT route through OpenClaw gateway — it's not an API proxy.
    
    OpenClaw gateway = Control plane for assistants (localhost:18789)
    Kimi API = ai_client.py calls https://api.kimi.com/coding/v1/messages
    
    If you see 405 Method Not Allowed or connection refused to localhost:18789,
    someone reverted this file to use the wrong endpoint. Fix it.

Uses Anthropic Messages API format.
"""

import os
import json
import re
from typing import List, Dict, Optional
from datetime import datetime


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


class AIClient:
    """
    Client for Kimi K2.5 API (direct API calls, not through OpenClaw).
    Uses Anthropic Messages API format.
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
    
    def _get_system_prompt(self, language: str) -> str:
        """Build the full system prompt for a given language."""
        base = self.base_system_prompt
        if language == 'undecided' or not language:
            return f"{base}\n\n{UNDECIDED_CONTEXT}"
        print(f"DEBUG: Base prompt starts with: {base[:100]!r}")
        lang_context = LANGUAGE_CONTEXT.get(language, LANGUAGE_CONTEXT["p5js"])
        return f"{base}\n\n{lang_context}"
        print(f"DEBUG: Base prompt starts with: {base[:100]!r}")
    
    def generate_code(
        self,
        message: str,
        conversation_history: Optional[List[Dict]],
        current_code: str,
        language: str = "undecided",
        model: str = "kimi-k2.5"
    ) -> Dict:
        """
        Generate code from a user's natural language request.
        
        Args:
            message: The user's request
            conversation_history: Previous messages for context
            current_code: The current code in the project
            language: Which language mode ('p5js', 'html', 'python', or 'undecided')
            model: Which AI model to use (default: kimi-k2.5)
            
        Returns:
            Dict with success, code, explanation, suggestions, full_response
        """
        try:
            # Build messages for the API
            messages_data = self._build_messages(message, conversation_history, current_code, language)
            
            # Call Kimi API
            response = self._call_kimi(messages_data)
            
            if not response.get("success"):
                return {
                    "success": False,
                    "error": response.get("error", "Unknown error")
                }
            
            # Extract code and explanation from response
            parsed = self._parse_response(response["content"], language)
            
            return {
                "success": True,
                "code": parsed["code"],
                "explanation": parsed["explanation"],
                "suggestions": parsed["suggestions"],
                "full_response": response["content"],
                "tokens_used": response.get("tokens_used", 0),
                "model": "kimi-k2.5"
            }
            
        except Exception as e:
            print(f"Error in generate_code: {e}")
            return {
                "success": False,
                "error": str(e)
            }
    
    def _build_messages(
        self,
        message: str,
        conversation_history: Optional[List[Dict]],
        current_code: str,
        language: str = "undecided"
    ):
        """Build the message list for the Kimi API (Anthropic Messages format)."""
        # Get the full system prompt for this language
        system_content = self._get_system_prompt(language)
        
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
        
        return messages, system_content
    
    def _call_kimi(self, messages_data) -> Dict:
        """Call Kimi K2.5 API directly using Anthropic Messages format."""
        try:
            import requests
            
            messages, system_content = messages_data
            
            # Anthropic Messages API format
            data = {
                "model": self.model,
                "messages": messages,
                "system": system_content,
                "max_tokens": 4096,
                "temperature": 0.7
            }
            
            headers = {
                "x-api-key": self.api_key,
                "anthropic-version": "2023-06-01",  # Required for Anthropic format
                "Content-Type": "application/json"
            }
            
            print(f"DEBUG: System prompt length: {len(system_content)} chars"); print(f"Calling Kimi API at {self.base_url}/v1/messages")
            print(f"Messages count: {len(messages)}")
            
            response = requests.post(
                f"{self.base_url}/v1/messages",
                headers=headers,
                json=data,
                timeout=120
            )
            
            print(f"Response status: {response.status_code}")
            
            if response.status_code == 200:
                result = response.json()
                content = result.get("content", [{}])[0].get("text", "")
                usage = result.get("usage", {})
                
                return {
                    "success": True,
                    "content": content,
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
            return {
                "success": False,
                "error": str(e)
            }
    
    def _parse_response(self, content: str, language: str = "undecided") -> Dict:
        """
        Parse AI response to extract code, explanation, and suggestions.
        
        Args:
            content: The raw AI response text
            language: 'p5js', 'html', 'python', or 'undecided' - affects which code blocks to look for
            
        Returns:
            Dict with code, explanation, suggestions
        """
        result = {
            "code": "",
            "explanation": "",
            "suggestions": []
        }
        
        print(f"_parse_response: content length {len(content)}")
        print(f"_parse_response: first 200 chars: {content[:200]!r}")
        
        # Map language to possible code block identifiers
        lang_identifiers = {
            "p5js": ["javascript", "js", ""],
            "html": ["html", ""],
            "python": ["python", "py", ""],
            "undecided": ["javascript", "js", "html", "python", "py", ""]
        }
        identifiers = lang_identifiers.get(language, [""])
        
        # Build regex patterns for each identifier
        code_patterns = []
        for ident in identifiers:
            if ident:
                code_patterns.append(rf'```{ident}\s*\n(.*?)\n```')  # With newline before close
                code_patterns.append(rf'```{ident}\s*\n(.*?)```')   # No newline before close
            else:
                code_patterns.append(r'```\s*\n(.*?)\n```')  # Any language
                code_patterns.append(r'```\s*\n(.*?)```')    # No newline before close
        
        code_matches = []
        for pattern in code_patterns:
            matches = re.findall(pattern, content, re.DOTALL)
            if matches:
                code_matches = matches
                print(f"_parse_response: matched pattern")
                break
        
        print(f"_parse_response: found {len(code_matches)} code blocks")
        
        if code_matches:
            result["code"] = code_matches[0].strip()
            print(f"_parse_response: extracted code length {len(result['code'])}")
        
        # Get explanation - text before first code block
        parts = re.split(r'```(?:\w+)?\s*\n?', content, maxsplit=1, flags=re.DOTALL)
        if parts:
            result["explanation"] = parts[0].strip()
            print(f"_parse_response: explanation length {len(result['explanation'])}")
        
        # Extract suggestions from text after code block
        if len(parts) > 1:
            after_code_parts = content.split('```')
            if len(after_code_parts) >= 3:
                after_code = ''.join(after_code_parts[2:])
                print(f"_parse_response: after_code length {len(after_code)}")
                
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
                        print(f"_parse_response: found suggestions")
                        suggestions = re.findall(r'[-*•\d.]\s*(.*?)(?=\n[-*•\d.]|\Z)', suggestions_text, re.DOTALL)
                        result["suggestions"] = [s.strip() for s in suggestions if s.strip()]
                        break
        
        print(f"_parse_response: returning code={len(result['code'])}, explanation={len(result['explanation'])}, suggestions={len(result['suggestions'])}")
        return result


# Singleton instance
_ai_client = None

def get_ai_client() -> AIClient:
    """Get or create the singleton AI client."""
    global _ai_client
    if _ai_client is None:
        _ai_client = AIClient()
    return _ai_client
