"""
chat/__init__.py - Chat module blueprint registration
Club Kinawa Coding Lab
"""

from flask import Blueprint

# Create blueprint
chat_bp = Blueprint('chat', __name__, url_prefix='/api')

# Import routes after blueprint creation to avoid circular imports
from chat import routes

__all__ = ['chat_bp']
