"""
ai_client.py - AI Model Integration for Club Kinawa Coding Lab

⚠️  CRITICAL: This file calls Kimi K2.5 API DIRECTLY.
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

## Rules
- Generate only p5.js code (setup(), draw(), etc.)
- Keep code simple and well-commented
- Explain what you're doing in kid-friendly language
- Suggest next steps or improvements
- If they describe something complex, build a simple version first
- Never use adult language or inappropriate content

## Formatting Rules (Very Important!)

**Use clean, scannable formatting with space between sections:**

✅ **GOOD formatting:**
```
I created a bouncing ball for you!

**What it does:**
The ball moves around and bounces off the edges.

**Try saying:**
• "Make the ball red"
• "Add a second ball"
• "Make it bounce faster"
```

❌ **BAD formatting (don't do this):**
```
• "The Basics:" 1. "What's the main goal?" (collect things, reach the end...) 2. "Who do you control?" (a character, a vehicle...)
```

**When asking questions, use this format:**

🎮 **What's the main goal?**
Collect things, reach the end, survive, defeat enemies, or solve puzzles?

🕹️ **Who or what do you control?**
A character, vehicle, shape, or something else?

**Key formatting tips:**
- Use emoji headers (🎮 🕹️ 🎯 🎨) to make sections pop
- Put each question on its own line with space after it
- Keep examples in parentheses short
- Use bullet points (•) not cramming into one line
- Bold the question, regular text for explanation

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

**What you could add next:**
• Change the ball color when it bounces
• Make the ball bigger or smaller
• Add a second ball"""

# System prompt for HTML mode (websites, web games)
HTML_CODING_PROMPT = """You are a coding assistant for kids ages 10-14. You're helping them build websites and web games using HTML, CSS, and JavaScript.

## Rules
- Generate complete, valid HTML documents
- Include inline CSS for styling and JavaScript for interactivity
- Keep code simple and well-commented
- Explain what you're doing in kid-friendly language
- Suggest next steps or improvements
- If they describe something complex, build a simple version first
- Never use adult language or inappropriate content

## Formatting Rules (Very Important!)

**Use clean, scannable formatting with space between sections:**

✅ **GOOD formatting:**
```
I created a simple website for you!

**What it does:**
Shows a button that changes color when you click it.

**Try saying:**
• "Make the button bigger"
• "Add a second button"
• "Change the background color"
```

❌ **BAD formatting (don't do this):**
```
• "The Basics:" 1. "What's the main goal?" ... 2. "Who do you control?" ...
```

**When asking questions, use this format:**

🎮 **What's the main goal?**
Collect things, reach the end, survive, defeat enemies, or solve puzzles?

🕹️ **Who or what do you control?**
A character, vehicle, or something else?

🎨 **What style is it?**
Colorful, space theme, underwater, pixel art?

**Key formatting tips:**
- Use emoji headers (🎮 🕹️ 🎯 🎨) to make sections pop
- Put each question on its own line with space after it
- Keep examples short
- Use bullet points (•) not cramming into one line
- Bold the question, regular text for explanation

## Output Format for Code Responses

1. **Brief explanation** (1-2 sentences)
2. **Code block** with the full HTML document
3. **Ideas to try** (2-3 bulleted suggestions)

Example code response:

I created a click counter for you! Click the button to see the count go up.

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
    }
    button {
      font-size: 20px;
      padding: 10px 20px;
      cursor: pointer;
    }
  </style>
</head>
<body>
  <h1>Click Counter</h1>
  <p>Clicks: <span id="count">0</span></p>
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

**What you could add next:**
• Make the button turn red after 10 clicks
• Add a "reset" button
• Change the font to something fun"""


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
            print("Warning: KIMI_API_KEY not set. AI features will fail.")
    
    def generate_code(
        self,
        message: str,
        conversation_history: Optional[List[Dict]] = None,
        current_code: str = "",
        model: str = "kimi-k2.5",
        language: str = "p5js"
    ) -> Dict:
        """
        Generate code from a kid's natural language request.
        
        Args:
            message: The kid's request (e.g., "make a bouncing ball")
            conversation_history: Previous messages for context
            current_code: Current project code (if any)
            model: Which model to use (ignored, always uses Kimi K2.5)
            language: Which language mode ('p5js' or 'html')
        
        Returns:
            Dict with:
            - success: bool
            - code: str (extracted code)
            - explanation: str (kid-friendly explanation)
            - suggestions: List[str] (next steps)
            - full_response: str (raw AI response)
            - tokens_used: int
            - model: str
        """
        # Build the conversation
        messages = self._build_messages(message, conversation_history, current_code, language)
        
        # Call Kimi API directly
        response = self._call_kimi(messages)
        
        if not response["success"]:
            return response
        
        # Extract code and explanation from response
        parsed = self._parse_response(response["content"])
        
        return {
            "success": True,
            "code": parsed["code"],
            "explanation": parsed["explanation"],
            "suggestions": parsed["suggestions"],
            "full_response": response["content"],
            "tokens_used": response.get("tokens_used", 0),
            "model": "kimi-k2.5"
        }
    
    def _build_messages(
        self,
        message: str,
        conversation_history: Optional[List[Dict]],
        current_code: str,
        language: str = "p5js"
    ) -> List[Dict]:
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
                "anthropic-version": "2023-06-01",
                "content-type": "application/json"
            }
            
            response = requests.post(
                f"{self.base_url}/v1/messages",
                json=data,
                headers=headers,
                timeout=120
            )
            
            if response.status_code != 200:
                return {
                    "success": False,
                    "error": f"Kimi API error: {response.status_code} - {response.text}"
                }
            
            result = response.json()
            content = result["content"][0]["text"] if result.get("content") else ""
            tokens_used = result.get("usage", {}).get("input_tokens", 0) + result.get("usage", {}).get("output_tokens", 0)
            
            return {
                "success": True,
                "content": content,
                "tokens_used": tokens_used
            }
            
        except Exception as e:
            return {
                "success": False,
                "error": f"Failed to call Kimi API: {str(e)}"
            }
    
    def _parse_response(self, content: str) -> Dict:
        """
        Parse AI response to extract code, explanation, and suggestions.
        
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
        
        # Extract code from markdown code block - more flexible pattern
        # Matches ``` followed by optional language, newline, content, newline, ```
        code_pattern = r'```(?:\w+)?\s*\n(.*?)\n```'
        code_matches = re.findall(code_pattern, content, re.DOTALL)
        print(f"_parse_response: found {len(code_matches)} code blocks")
        
        if code_matches:
            result["code"] = code_matches[0].strip()
            print(f"_parse_response: extracted code length {len(result['code'])}")
        
        # Get explanation - text before first code block
        parts = re.split(r'```(?:\w+)?\s*\n', content, maxsplit=1, flags=re.DOTALL)
        if parts:
            result["explanation"] = parts[0].strip()
            print(f"_parse_response: explanation length {len(result['explanation'])}")
        
        # Extract suggestions from text after code block
        if len(parts) > 1:
            # Get the part after the code block (the rest after splitting)
            after_code_match = re.search(r'```\s*(.*?)$', content, re.DOTALL)
            if after_code_match:
                after_code = after_code_match.group(1)
                print(f"_parse_response: after_code length {len(after_code)}")
                
                # Look for suggestions - bullet points, numbered lists, or "ideas" section
                suggestion_patterns = [
                    r'(?:What you could add|Suggestions|Next steps|Try adding|Ideas to try)[\s:]*\n((?:[-*•\d.]\s*.*?\n?)+)',
                    r'(?:\*\*)?(?:What you could add|Suggestions)[\s:]*(?:\*\*)?\n((?:[-*•\d.]\s*.*?\n?)+)',
                    r'\n((?:[-*•]\s*.*?\n)+)'  # Any bullet list
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
