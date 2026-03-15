"""
projects/__init__.py - Project module blueprint registration
Club Kinawa Coding Lab
"""

from flask import Blueprint

# Create blueprint
project_bp = Blueprint('projects', __name__, url_prefix='/api')

# Import routes after blueprint creation to avoid circular imports
from projects import routes

__all__ = ['project_bp']
