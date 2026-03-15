"""
versions/__init__.py - Versions module blueprint registration
Club Kinawa Coding Lab
"""

from flask import Blueprint

# Create blueprint
versions_bp = Blueprint('versions', __name__, url_prefix='/api')

# Import routes after blueprint creation to avoid circular imports
from versions import routes

__all__ = ['versions_bp']
