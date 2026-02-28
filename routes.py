"""
routes.py - Flask API Routes
Club Kinawa Coding Lab - Authentication System

Provides REST API endpoints for authentication:
- POST /api/auth/login - Authenticate and create session
- POST /api/auth/logout - Invalidate session
- POST /api/auth/register - Create new user (staff only)
- GET /api/auth/me - Get current user info

All endpoints return JSON with consistent structure:
    Success: {"success": true, ...data}
    Error: {"success": false, "error": "message"}
"""

import re
from functools import wraps
from flask import Blueprint, request, jsonify, g
from datetime import datetime
import auth
from auth import (
    create_user, authenticate, create_session, validate_session,
    invalidate_session, cleanup_expired_sessions, AuthError,
    InvalidPINError, UserExistsError
)

# Create Flask Blueprint
auth_bp = Blueprint('auth', __name__, url_prefix='/api/auth')

# Rate limiting storage (in-memory, per-process)
# For production with multiple workers, use Redis or similar
_rate_limit_store = {}
RATE_LIMIT_ATTEMPTS = 5  # Max attempts
RATE_LIMIT_WINDOW_SECONDS = 60  # Time window in seconds


def get_client_ip() -> str:
    """
    Get the client IP address from request headers.
    Handles proxies by checking X-Forwarded-For first.
    """
    if request.headers.get('X-Forwarded-For'):
        return request.headers.get('X-Forwarded-For').split(',')[0].strip()
    elif request.headers.get('X-Real-IP'):
        return request.headers.get('X-Real-IP')
    return request.remote_addr or 'unknown'


def check_rate_limit(ip: str) -> bool:
    """
    Check if IP has exceeded rate limit for login attempts.
    
    Args:
        ip: Client IP address
    
    Returns:
        bool: True if rate limited (too many attempts), False otherwise
    """
    now = datetime.utcnow()
    
    if ip not in _rate_limit_store:
        _rate_limit_store[ip] = []
    
    # Clean old entries outside the window
    _rate_limit_store[ip] = [
        timestamp for timestamp in _rate_limit_store[ip]
        if (now - timestamp).total_seconds() < RATE_LIMIT_WINDOW_SECONDS
    ]
    
    # Check if limit exceeded
    if len(_rate_limit_store[ip]) >= RATE_LIMIT_ATTEMPTS:
        return True
    
    return False


def record_attempt(ip: str) -> None:
    """Record a login attempt for rate limiting."""
    now = datetime.utcnow()
    if ip not in _rate_limit_store:
        _rate_limit_store[ip] = []
    _rate_limit_store[ip].append(now)


def get_auth_token() -> str:
    """
    Extract Bearer token from Authorization header.
    
    Returns:
        str: Token string or empty string if not present/invalid format
    """
    auth_header = request.headers.get('Authorization', '')
    if not auth_header:
        return ''
    
    # Expect "Bearer <token>" format
    parts = auth_header.split()
    if len(parts) == 2 and parts[0].lower() == 'bearer':
        return parts[1]
    
    return ''


def require_auth(f):
    """
    Decorator to require valid session token for protected routes.
    
    Adds `g.current_user` with user data if authentication succeeds.
    Returns 401 if authentication fails.
    """
    @wraps(f)
    def decorated_function(*args, **kwargs):
        token = get_auth_token()
        
        if not token:
            return jsonify({
                'success': False,
                'error': 'Authentication required. Provide token in Authorization header.'
            }), 401
        
        user = validate_session(token)
        if not user:
            return jsonify({
                'success': False,
                'error': 'Invalid or expired session token'
            }), 401
        
        # Store user in Flask's g object for use in route
        g.current_user = user
        g.auth_token = token
        
        return f(*args, **kwargs)
    
    return decorated_function


def require_staff(f):
    """
    Decorator to require staff/admin privileges.
    
    For Phase 2, this is a placeholder. In production, check user role/permissions.
    Currently requires authentication but doesn't check specific role.
    """
    @wraps(f)
    @require_auth
    def decorated_function(*args, **kwargs):
        # TODO: Check if user has staff/admin role when role system is added
        # For now, any authenticated user can register (for development)
        # In production, add role checking here
        return f(*args, **kwargs)
    
    return decorated_function


# API Routes

@auth_bp.route('/login', methods=['POST'])
def login():
    """
    POST /api/auth/login
    
    Authenticate user with username and PIN.
    
    Request Body (JSON):
        {
            "username": "string",
            "pin": "4-digit PIN"
        }
    
    Response:
        Success (200):
            {
                "success": true,
                "token": "session_token_here",
                "user": {
                    "id": 1,
                    "username": "kidname",
                    "created_at": "2024-01-01T00:00:00",
                    "is_active": 1,
                    "last_login": "2024-01-01T00:00:00"
                }
            }
        Error (400/401/429):
            {"success": false, "error": "error message"}
    """
    # Check rate limiting
    client_ip = get_client_ip()
    if check_rate_limit(client_ip):
        return jsonify({
            'success': False,
            'error': 'Too many login attempts. Please wait a minute and try again.'
        }), 429
    
    # Validate request body
    if not request.is_json:
        return jsonify({
            'success': False,
            'error': 'Request must be JSON'
        }), 400
    
    data = request.get_json()
    username = data.get('username', '').strip()
    pin = data.get('pin', '')
    
    if not username or not pin:
        return jsonify({
            'success': False,
            'error': 'Username and PIN are required'
        }), 400
    
    # Validate PIN format
    if not re.match(r'^\d{4}$', pin):
        record_attempt(client_ip)
        return jsonify({
            'success': False,
            'error': 'PIN must be exactly 4 digits'
        }), 400
    
    # Attempt authentication
    user = authenticate(username, pin)
    
    if not user:
        record_attempt(client_ip)
        return jsonify({
            'success': False,
            'error': 'Invalid username or PIN'
        }), 401
    
    # Create session token
    token = create_session(user['id'])
    
    response = jsonify({
        'success': True,
        'token': token,
        'user': user
    })
    response.set_cookie('auth_token', token, httponly=True, samesite='Lax', path='/', max_age=86400)
    return response, 200


@auth_bp.route('/logout', methods=['POST'])
@require_auth
def logout():
    """
    POST /api/auth/logout
    
    Invalidate the current session token.
    
    Headers:
        Authorization: Bearer <token>
    
    Response:
        Success (200): {"success": true}
        Error (401): {"success": false, "error": "..."}
    """
    token = g.auth_token
    invalidate_session(token)
    
    response = jsonify({
        'success': True
    })
    response.delete_cookie('auth_token', path='/')
    return response, 200


@auth_bp.route('/register', methods=['POST'])
def register():
    """
    POST /api/auth/register
    
    Create a new user account. 
    Note: Currently open for development. In production, add @require_staff decorator.
    
    Request Body (JSON):
        {
            "username": "string",
            "pin": "4-digit PIN"
        }
    
    Response:
        Success (201):
            {
                "success": true,
                "user": {
                    "id": 1,
                    "username": "kidname",
                    "created_at": "2024-01-01T00:00:00",
                    "is_active": 1,
                    "last_login": null
                }
            }
        Error (400/409):
            {"success": false, "error": "error message"}
    """
    # Validate request body
    if not request.is_json:
        return jsonify({
            'success': False,
            'error': 'Request must be JSON'
        }), 400
    
    data = request.get_json()
    username = data.get('username', '').strip()
    pin = data.get('pin', '')
    
    if not username or not pin:
        return jsonify({
            'success': False,
            'error': 'Username and PIN are required'
        }), 400
    
    # Validate PIN format
    if not re.match(r'^\d{4}$', pin):
        return jsonify({
            'success': False,
            'error': 'PIN must be exactly 4 digits (0000-9999)'
        }), 400
    
    try:
        user = create_user(username, pin)
        return jsonify({
            'success': True,
            'user': user
        }), 201
    
    except InvalidPINError as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 400
    
    except UserExistsError as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 409
    
    except AuthError as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 400


@auth_bp.route('/me', methods=['GET'])
@require_auth
def get_me():
    """
    GET /api/auth/me
    
    Get current authenticated user information.
    
    Headers:
        Authorization: Bearer <token>
    
    Response:
        Success (200):
            {
                "user": {
                    "id": 1,
                    "username": "kidname",
                    "created_at": "2024-01-01T00:00:00",
                    "is_active": 1,
                    "last_login": "2024-01-01T00:00:00"
                }
            }
        Error (401): {"success": false, "error": "..."}
    """
    return jsonify({
        'user': g.current_user
    }), 200


# Health check endpoint (no auth required)
@auth_bp.route('/health', methods=['GET'])
def health_check():
    """
    GET /api/auth/health
    
    Simple health check endpoint.
    """
    return jsonify({
        'status': 'ok',
        'service': 'ckcl-auth'
    }), 200
