"""
app.py - Flask Application Factory
Club Kinawa Coding Lab

Provides the create_app() factory function following Flask 2.x patterns.
Handles database initialization, blueprint registration, and session cleanup.
"""

import os
from flask import Flask, g, request, send_from_directory
from database import init_db_full
from auth import cleanup_expired_sessions
from routes import auth_bp
from project_routes import project_bp


def create_app(test_config: dict = None) -> Flask:
    """
    Application factory for Club Kinawa Coding Lab.
    
    Creates and configures the Flask application with:
    - Database initialization on startup
    - Authentication blueprint registration
    - Session cleanup before each request
    - Error handlers for common HTTP errors
    
    Args:
        test_config: Optional dictionary of configuration overrides for testing
    
    Returns:
        Flask: Configured Flask application instance
    """
    # Create Flask app
    app = Flask(__name__, static_folder='static', template_folder='templates')
    
    # Load configuration
    app.secret_key = os.environ.get('SECRET_KEY', 'dev-secret-key-change-in-production')
    app.config['DATABASE'] = os.environ.get('CKCL_DB_PATH', 'ckcl.db')
    
    # Apply test configuration if provided
    if test_config:
        app.config.update(test_config)
    
    # Initialize database on startup (includes all migrations)
    try:
        init_db_full(app.config['DATABASE'])
        app.logger.info(f"Database initialized: {app.config['DATABASE']}")
    except Exception as e:
        app.logger.error(f"Failed to initialize database: {e}")
        raise
    
    # Register blueprints
    app.register_blueprint(auth_bp)
    app.register_blueprint(project_bp)
    
    # Request hooks
    @app.before_request
    def before_request():
        """Clean up expired sessions before each request."""
        try:
            deleted = cleanup_expired_sessions()
            if deleted > 0:
                app.logger.debug(f"Cleaned up {deleted} expired sessions")
        except Exception as e:
            app.logger.warning(f"Session cleanup failed: {e}")
    
    @app.after_request
    def after_request(response):
        """Add security headers after each request."""
        response.headers['X-Content-Type-Options'] = 'nosniff'
        response.headers['X-Frame-Options'] = 'DENY'
        response.headers['X-XSS-Protection'] = '1; mode=block'
        return response
    
    # Error handlers
    @app.errorhandler(404)
    def not_found(error):
        if request.path.startswith('/api/'):
            return {'success': False, 'error': 'Endpoint not found'}, 404
        return 'Not Found', 404
    
    @app.errorhandler(500)
    def internal_error(error):
        app.logger.error(f"Internal error: {error}")
        if request.path.startswith('/api/'):
            return {'success': False, 'error': 'Internal server error'}, 500
        return 'Internal Server Error', 500
    
    @app.errorhandler(405)
    def method_not_allowed(error):
        if request.path.startswith('/api/'):
            return {'success': False, 'error': 'Method not allowed'}, 405
        return 'Method Not Allowed', 405
    
    # Handle SCRIPT_NAME for subpath deployment
    @app.before_request
    def handle_script_name():
        script_name = request.headers.get('X-Script-Name')
        if script_name:
            request.environ['SCRIPT_NAME'] = script_name
    
    # API root endpoint
    @app.route('/')
    def index():
        return {
            'service': 'Club Kinawa Coding Lab API',
            'version': '1.0.0',
            'status': 'running',
            'endpoints': {
                'auth': '/api/auth',
                'projects': '/api/projects',
                'health': '/api/auth/health'
            }
        }
    
    # Frontend routes - serve the lab interface
    @app.route('/lab')
    def lab_index():
        """Main lab interface - redirect to login."""
        return send_from_directory('templates', 'login.html')
    
    @app.route('/lab/login')
    def lab_login():
        """Login page."""
        return send_from_directory('templates', 'login.html')
    
    @app.route('/lab/projects')
    def lab_projects():
        """Project gallery page."""
        return send_from_directory('templates', 'projects.html')
    
    @app.route('/lab/project/<int:project_id>')
    def lab_project(project_id):
        """Individual project workspace."""
        return send_from_directory('templates', 'workspace.html')
    
    # Static files - serve from both /static and /lab/static for flexibility
    @app.route('/static/<path:filename>')
    def serve_static(filename):
        return send_from_directory('static', filename)
    
    @app.route('/lab/static/<path:filename>')
    def serve_static_lab(filename):
        """Serve static files under /lab path."""
        return send_from_directory('static', filename)
    
    app.logger.info("Club Kinawa Coding Lab API initialized")
    return app


# For running directly (development)
if __name__ == '__main__':
    app = create_app()
    app.run(debug=True, host='0.0.0.0', port=5000)