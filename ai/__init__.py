# ai/__init__.py - AI Package Initialization
"""
AI Client Package for CK Coding Lab

Provides modular AI client functionality:
- client: AIClient class for API interactions
- tools: FileTools class for database file operations
- parser: Response parsing functions
- prompts: System prompt management
- config: API configuration and constants

Usage:
    from ai import get_ai_client
    
    ai = get_ai_client()
    result = ai.generate_code(...)
"""

from ai.client import AIClient, get_ai_client
from ai.tools import FileTools
from ai.parser import parse_response
from ai.config import (
    KIMI_BASE_URL,
    KIMI_MODEL,
    LANGUAGE_CONTEXT,
    UNDECIDED_CONTEXT
)

__all__ = [
    'AIClient',
    'get_ai_client',
    'FileTools',
    'parse_response',
    'KIMI_BASE_URL',
    'KIMI_MODEL',
    'LANGUAGE_CONTEXT',
    'UNDECIDED_CONTEXT',
]
