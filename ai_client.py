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


# System prompt for p5.js mode (games, animations)
KID_CODING_PROMPT = """You are a coding assistant for kids ages 10-14. You're helping them build games and interactive projects using p5.js (JavaScript).

## PROJECT TYPE: P5.JS
You MUST generate p5.js code (setup(), draw(), etc.).

## Rules
- Generate only p5.js code (setup(), draw(), etc.)
- Keep code simple and well-commented
- Explain what you're doing in kid-friendly language
- Suggest next steps or improvements
- If they describe something complex, build a simple version first
- Never use adult language or inappropriate content
- Use correct p5.js key constants: UP_ARROW, DOWN_ARROW, LEFT_ARROW, RIGHT_ARROW (not UP, DOWN, LEFT, RIGHT)

## Formatting Rules (Very Important!)

**Use clean, scannable formatting with space between sections:**

**When asking questions, use this format:**

🎮 **What's the main goal?**
Collect things, reach the end, survive, defeat enemies, or solve puzzles?

🕹️ **Who or what do you control?**
A character, vehicle, shape, or something else?

## Output Format for Code Responses

1. **Brief explanation** (1-2 sentences)
2. **Code block** with the full sketch
3. **Ideas to try** (2-3 bulleted suggestions)

Example code response:

I created a bouncing ball for you! The ball moves around the screen and bounces off the edges.

```javascript
function setup() {
  createCanvas(400, 400);
}

let x = 200;
let y = 200;
let xspeed = 3;
let yspeed = 2;

function draw() {
  background(220);
  
  // Move the ball
  x = x + xspeed;
  y = y + yspeed;
  
  // Bounce off edges
  if (x > width || x < 0) {
    xspeed = xspeed * -1;
  }
  if (y > height || y < 0) {
    yspeed = yspeed * -1;
  }
  
  // Draw the ball
  circle(x, y, 30);
}
```

**What you could add:**
• Make the ball change color when it bounces
• Add a second ball
• Make the ball speed up over time
"""

# System prompt for HTML mode (websites, web games)
HTML_CODING_PROMPT = """You are a coding assistant for kids ages 10-14. You're helping them build websites and web games using HTML, CSS, and JavaScript.

## PROJECT TYPE: HTML
You MUST generate complete HTML documents with inline CSS and JavaScript.

## Rules
- Generate complete, valid HTML documents (with <!DOCTYPE html>, <html>, <head>, <body>)
- Include CSS in a <style> tag and JavaScript in a <script> tag
- Keep code simple and well-commented
- Explain what you're doing in kid-friendly language
- If they describe something complex, build a simple version first
- Never use adult language or inappropriate content
- Use correct p5.js key constants: UP_ARROW, DOWN_ARROW, LEFT_ARROW, RIGHT_ARROW (not UP, DOWN, LEFT, RIGHT)

## Formatting Rules (Very Important!)

**Use clean, scannable formatting with space between sections:**

## Output Format for Code Responses

1. **Brief explanation** (1-2 sentences)
2. **Code block** with the complete HTML document
3. **Ideas to try** (2-3 bulleted suggestions)

Example code response:

I created a click counter for you! Click the button and the number goes up.

```html
<!DOCTYPE html>
<html>
<head>
  <title>Click Counter</title>
  <style>
    body {
      font-family: Arial, sans-serif;
      text-align: center;
      padding: 50px;
      background: #f0f0f0;
    }
    button {
      font-size: 24px;
      padding: 20px 40px;
      cursor: pointer;
    }
    #count {
      font-size: 48px;
      margin: 20px;
    }
  </style>
</head>
<body>
  <h1>Click Counter</h1>
  <div id="count">0</div>
  <button onclick="increment()">Click me!</button>
  
  <script>
    let count = 0;
    function increment() {
      count = count + 1;
      document.getElementById('count').textContent = count;
    }
  </script>
</body>
</html>
```

**What you could add:**
• Make the button turn green after 10 clicks
• Add a "reset" button
• Show a celebration message at 50 clicks
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
    
    def generate_code(
        self,
        message: str,
        conversation_history: Optional[List[Dict]],
        current_code: str,
        language: str = "p5js"
    ) -> Dict:
        """
        Generate code from a kid's natural language request.
        
        Args:
            message: The kid's request
            conversation_history: Previous messages for context
            current_code: The current code in the project
            language: Which language mode ('p5js' or 'html')
            
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
        language: str = "p5js"
    ):
        """Build the message list for the Kimi API (Anthropic Messages format)."""
        # Select appropriate system prompt based on language
        if language == "html":
            system_content = HTML_CODING_PROMPT
            code_lang = "html"
        else:
            system_content = KID_CODING_PROMPT
            code_lang = "javascript"
        
        # Anthropic format: system message is separate, not in messages array
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
            
            print(f"Calling Kimi API at {self.base_url}/v1/messages")
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
    
    def _parse_response(self, content: str, language: str = "p5js") -> Dict:
        """
        Parse AI response to extract code, explanation, and suggestions.
        
        Args:
            content: The raw AI response text
            language: 'p5js' or 'html' - affects which code blocks to look for
            
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
        
        # More flexible code block extraction
        # Matches ``` optionally followed by language, then content until ```
        # Using re.DOTALL to match across newlines
        code_patterns = [
            r'```(?:javascript|js|html)?\s*\n(.*?)\n```',  # Standard markdown
            r'```(?:javascript|js|html)?\s*\n(.*?)```',     # No newline before close
            r'```\s*\n(.*?)\n```',                           # Any language
            r'```\s*\n(.*?)```',                             # No newline before close
        ]
        
        code_matches = []
        for pattern in code_patterns:
            matches = re.findall(pattern, content, re.DOTALL)
            if matches:
                code_matches = matches
                print(f"_parse_response: matched pattern: {pattern[:40]}...")
                break
        
        print(f"_parse_response: found {len(code_matches)} code blocks")
        
        if code_matches:
            result["code"] = code_matches[0].strip()
            print(f"_parse_response: extracted code length {len(result['code'])}")
        
        # Get explanation - text before first code block
        # Split on opening ``` 
        parts = re.split(r'```(?:\w+)?\s*\n?', content, maxsplit=1, flags=re.DOTALL)
        if parts:
            result["explanation"] = parts[0].strip()
            print(f"_parse_response: explanation length {len(result['explanation'])}")
        
        # Extract suggestions from text after code block
        if len(parts) > 1:
            # Get everything after the code block
            after_code_parts = content.split('```')
            if len(after_code_parts) >= 3:
                # content is: before ``` code ``` after
                after_code = ''.join(after_code_parts[2:])  # Everything after second ```
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
                        print(f"_parse_response: found suggestions with pattern")
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
