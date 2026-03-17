"""
routes.py - Flask API Routes
Club Kinawa Coding Lab - Authentication System

Provides REST API endpoints for authentication:
- POST /api/auth/login - Authenticate and create session
- POST /api/auth/logout - Invalidate session
- POST /api/auth/register - Create new user (admin-only unless self-registration is explicitly enabled)
- GET /api/auth/me - Get current user info

All endpoints return JSON with consistent structure:
    Success: {"success": true, ...data}
    Error: {"success": false, "error": "message"}
"""

import re
import sqlite3
from flask import Blueprint, request, jsonify, g, current_app
from datetime import datetime, timedelta
from auth import (
    create_user, authenticate, create_session, validate_session, invalidate_session,
    cleanup_expired_sessions, require_auth, AuthError, InvalidPINError, UserExistsError
)
from database import get_database_path

# Create Flask Blueprint
auth_bp = Blueprint('auth', __name__, url_prefix='/api/auth')

# Rate limiting configuration
RATE_LIMIT_ATTEMPTS = 5  # Max attempts
RATE_LIMIT_WINDOW_SECONDS = 60  # Time window in seconds
LOGIN_RATE_LIMIT_ERROR = 'Too many login attempts. Please wait a minute and try again.'


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


def _login_rate_limit_connection() -> sqlite3.Connection:
    """Open a dedicated connection for login rate limit checks."""
    conn = sqlite3.connect(get_database_path())
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def _current_login_attempt_count(cursor: sqlite3.Cursor, ip: str, now: datetime) -> int:
    """Prune expired attempts and return the current count for an IP."""
    window_start = now - timedelta(seconds=RATE_LIMIT_WINDOW_SECONDS)
    timestamp = window_start.strftime('%Y-%m-%dT%H:%M:%S')

    cursor.execute(
        '''
        DELETE FROM login_rate_limit_attempts
        WHERE client_ip = ? AND attempted_at < datetime(?)
        ''',
        (ip, timestamp),
    )
    cursor.execute(
        '''
        SELECT COUNT(*) AS count FROM login_rate_limit_attempts
        WHERE client_ip = ? AND attempted_at >= datetime(?)
        ''',
        (ip, timestamp),
    )
    result = cursor.fetchone()
    return result['count'] if result else 0


def check_rate_limit(ip: str) -> bool:
    """
    Check if IP has exceeded rate limit for login attempts.

    Uses database-backed storage so the limit is shared across workers.
    """
    now = datetime.utcnow()
    conn = _login_rate_limit_connection()

    try:
        conn.execute('BEGIN IMMEDIATE')
        cursor = conn.cursor()
        current_count = _current_login_attempt_count(cursor, ip, now)
        conn.commit()
        return current_count >= RATE_LIMIT_ATTEMPTS
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def record_attempt(ip: str) -> bool:
    """Record a failed login attempt for an IP.

    Returns:
        bool: True if the failure was recorded, False if the IP was already rate limited.
    """
    now = datetime.utcnow()
    conn = _login_rate_limit_connection()

    try:
        conn.execute('BEGIN IMMEDIATE')
        cursor = conn.cursor()
        current_count = _current_login_attempt_count(cursor, ip, now)
        if current_count >= RATE_LIMIT_ATTEMPTS:
            conn.commit()
            return False

        cursor.execute(
            '''
            INSERT INTO login_rate_limit_attempts (client_ip, attempted_at)
            VALUES (?, datetime(?))
            ''',
            (ip, now.strftime('%Y-%m-%dT%H:%M:%S')),
        )
        conn.commit()
        return True
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def require_admin_for_registration():
    """
    Enforce admin auth when self-registration is disabled.

    Returns:
        tuple[dict | None, Response | None]: (admin_user, error_response)
    """
    if current_app.config.get('ALLOW_SELF_REGISTRATION', False):
        return None, None

    auth_header = request.headers.get('Authorization', '')
    if not auth_header.startswith('Bearer '):
        return None, (
            jsonify({
                'success': False,
                'error': 'Self-registration is disabled. Admin access required.'
            }),
            403,
        )

    token = auth_header[7:]
    user = validate_session(token)
    if not user:
        return None, (
            jsonify({
                'success': False,
                'error': 'Invalid or expired session'
            }),
            401,
        )

    if user.get('role') != 'admin':
        return None, (
            jsonify({
                'success': False,
                'error': 'Admin access required'
            }),
            403,
        )

    g.current_user = user
    g.current_token = token
    return user, None


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
            'error': LOGIN_RATE_LIMIT_ERROR
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
        if not record_attempt(client_ip):
            return jsonify({
                'success': False,
                'error': LOGIN_RATE_LIMIT_ERROR
            }), 429
        return jsonify({
            'success': False,
            'error': 'PIN must be exactly 4 digits'
        }), 400
    
    # Attempt authentication
    user = authenticate(username, pin)
    
    if not user:
        if not record_attempt(client_ip):
            return jsonify({
                'success': False,
                'error': LOGIN_RATE_LIMIT_ERROR
            }), 429
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
    token = g.current_token
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

    Security model:
    - Self-registration is disabled by default.
    - When disabled, only authenticated admins may create accounts.
    - When explicitly enabled via config, requests may create kid accounts only.
    
    Request Body (JSON):
        {
            "username": "string",
            "pin": "4-digit PIN",
            "role": "kid|admin"   # admin-only when self-registration is disabled
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
        Error (400/401/403/409):
            {"success": false, "error": "error message"}
    """
    admin_user, error_response = require_admin_for_registration()
    if error_response:
        return error_response

    # Validate request body
    if not request.is_json:
        return jsonify({
            'success': False,
            'error': 'Request must be JSON'
        }), 400
    
    data = request.get_json()
    username = data.get('username', '').strip()
    pin = data.get('pin', '')
    role = data.get('role', 'kid')
    
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

    # Self-registration may only create kid accounts.
    if admin_user is None:
        role = 'kid'
    
    try:
        user = create_user(username, pin, role)
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
