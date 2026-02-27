"""
sandbox.py - Secure Code Execution Environment

Provides server-side code validation and sandbox management.
"""

import re
import ast
import json
from typing import Dict, List, Tuple


class CodeValidator:
    """Validates JavaScript code for safety before execution."""
    
    # Dangerous patterns to block
    BLOCKED_PATTERNS = [
        r'eval\s*\(',
        r'Function\s*\(',
        r'setTimeout\s*\(\s*["\']',
        r'setInterval\s*\(\s*["\']',
        r'import\s*\(',
        r'new\s+Worker',
        r'XMLHttpRequest',
        r'fetch\s*\(',
        r'WebSocket',
        r'localStorage',
        r'sessionStorage',
        r'indexedDB',
        r'open\s*\(',
        r'location\.',
        r'document\.cookie',
        r'document\.write',
        r'parent\.',  # iframe escape
        r'top\.',     # iframe escape
    ]
    
    # Allowed p5.js functions whitelist (optional strict mode)
    ALLOWED_P5_FUNCTIONS = [
        'setup', 'draw', 'preload', 'windowResized',
        'createCanvas', 'resizeCanvas', 'background', 'clear',
        'fill', 'noFill', 'stroke', 'noStroke', 'strokeWeight',
        'color', 'red', 'green', 'blue', 'alpha', 'lerpColor',
        'point', 'line', 'triangle', 'quad', 'rect', 'square',
        'ellipse', 'circle', 'arc', 'beginShape', 'endShape',
        'vertex', 'bezierVertex', 'curveVertex',
        'text', 'textSize', 'textFont', 'textAlign', 'textLeading',
        'loadFont', 'loadImage', 'image', 'createImage',
        'push', 'pop', 'translate', 'rotate', 'scale',
        'random', 'randomSeed', 'noise', 'noiseSeed', 'map',
        'dist', 'lerp', 'constrain', 'min', 'max', 'abs', 'floor', 'ceil',
        'sin', 'cos', 'tan', 'atan2', 'degrees', 'radians',
        'createVector', 'p5.Vector',
        'mouseX', 'mouseY', 'pmouseX', 'pmouseY', 'mouseIsPressed',
        'key', 'keyCode', 'keyIsPressed', 'keyIsDown',
        'width', 'height', 'windowWidth', 'windowHeight',
        'frameCount', 'frameRate', 'deltaTime', 'millis',
        'loop', 'noLoop', 'redraw',
        'print', 'console.log'
    ]
    
    def validate(self, code: str) -> Tuple[bool, List[str]]:
        """
        Validate code for safety issues.
        
        Returns:
            (is_valid, list_of_violations)
        """
        violations = []
        
        # Check for blocked patterns
        for pattern in self.BLOCKED_PATTERNS:
            if re.search(pattern, code, re.IGNORECASE):
                violations.append(f"Blocked pattern detected: {pattern}")
        
        # Check for infinite loops (basic heuristic)
        if self._has_potential_infinite_loop(code):
            violations.append("Potential infinite loop detected")
        
        return len(violations) == 0, violations
    
    def _has_potential_infinite_loop(self, code: str) -> bool:
        """Basic check for potential infinite loops."""
        # Look for while(true) or for(;;) patterns
        patterns = [
            r'while\s*\(\s*true\s*\)',
            r'while\s*\(\s*1\s*\)',
            r'for\s*\(\s*;\s*;\s*\)',
        ]
        for pattern in patterns:
            if re.search(pattern, code, re.IGNORECASE):
                return True
        return False
    
    def sanitize(self, code: str) -> str:
        """
        Sanitize code before execution.
        Returns cleaned code or raises ValueError if unsafe.
        """
        is_valid, violations = self.validate(code)
        if not is_valid:
            raise ValueError(f"Code validation failed: {'; '.join(violations)}")
        return code


class SandboxConfig:
    """Configuration for sandbox execution."""
    
    def __init__(self):
        self.max_execution_time_ms = 5000  # 5 seconds
        self.max_iterations = 100000  # Frame limit
        self.max_memory_mb = 100
        self.allowed_domains = []  # No external domains allowed
        self.enable_network = False
        self.enable_storage = False
