"""
auth.py - Authentication Module
Club Kinawa Coding Lab - Authentication System

Provides PIN hashing, user management, session creation and validation.
Designed for kids ages 10-14 with simple 4-digit PIN authentication.
"""

import re
import bcrypt
import secrets
from datetime import datetime, timedelta, timezone
from typing import Optional, Dict
from functools import wraps
from flask import request, jsonify, g
from database import get_db, row_to_dict

# Security configuration
BCRYPT_COST_FACTOR = 12  # bcrypt work factor (higher = more secure but slower)
SESSION_DURATION_HOURS = 24  # Session token validity period
PIN_PATTERN = re.compile(r'^\d{4}$')  # Exactly 4 digits


class AuthError(Exception):
    """Custom exception for authentication errors."""
    pass


class InvalidPINError(AuthError):
    """Raised when PIN doesn't meet requirements."""
    pass


class UserExistsError(AuthError):
    """Raised when trying to create a user that already exists."""
    pass


class InvalidCredentialsError(AuthError):
    """Raised when login credentials are invalid."""
    pass


class AdminRequiredError(AuthError):
    """Raised when admin access is required but user is not admin."""
    pass


def hash_pin(pin: str) -> str:
    """
    Hash a 4-digit PIN using bcrypt.
    
    Args:
        pin: 4-digit PIN string
    
    Returns:
        str: bcrypt hash of the PIN
    
    Raises:
        InvalidPINError: If PIN is not exactly 4 digits
    """
    if not PIN_PATTERN.match(pin):
        raise InvalidPINError("PIN must be exactly 4 digits (0000-9999)")
    
    # bcrypt requires bytes, encode the PIN
    pin_bytes = pin.encode('utf-8')
    # Generate salt with configured cost factor and hash
    hashed = bcrypt.hashpw(pin_bytes, bcrypt.gensalt(rounds=BCRYPT_COST_FACTOR))
    # Return as string for database storage
    return hashed.decode('utf-8')


def verify_pin(pin: str, hashed: str) -> bool:
    """
    Verify a PIN against its bcrypt hash.
    
    Args:
        pin: 4-digit PIN to verify
        hashed: bcrypt hash string from database
    
    Returns:
        bool: True if PIN matches hash, False otherwise
    """
    pin_bytes = pin.encode('utf-8')
    hashed_bytes = hashed.encode('utf-8')
    return bcrypt.checkpw(pin_bytes, hashed_bytes)


def validate_username(username: str) -> None:
    """
    Validate username format.
    
    Args:
        username: Username to validate
    
    Raises:
        AuthError: If username is invalid
    """
    if not username or len(username) < 3:
        raise AuthError("Username must be at least 3 characters")
    if len(username) > 30:
        raise AuthError("Username must be 30 characters or less")
    # Allow letters, numbers, underscores, and hyphens
    if not re.match(r'^[a-zA-Z0-9_-]+$', username):
        raise AuthError("Username can only contain letters, numbers, underscores, and hyphens")


def validate_role(role: str) -> None:
    """
    Validate role value.
    
    Args:
        role: Role to validate ('admin' or 'kid')
    
    Raises:
        AuthError: If role is invalid
    """
    if role not in ('admin', 'kid'):
        raise AuthError("Role must be 'admin' or 'kid'")


def create_user(username: str, pin: str, role: str = 'kid') -> dict:
    """
    Create a new user account with a 4-digit PIN.
    
    Args:
        username: Unique username for the kid
        pin: 4-digit PIN (will be hashed before storage)
        role: User role ('admin' or 'kid', default 'kid')
    
    Returns:
        dict: User data excluding sensitive fields (pin_hash removed)
    
    Raises:
        InvalidPINError: If PIN format is invalid
        UserExistsError: If username already exists
        AuthError: If username format or role is invalid
    """
    # Validate inputs
    validate_username(username)
    validate_role(role)
    pin_hash = hash_pin(pin)
    
    with get_db() as db:
        try:
            db.execute(
                "INSERT INTO users (username, pin_hash, role) VALUES (?, ?, ?)",
                (username, pin_hash, role)
            )
            # Get the created user
            db.execute(
                "SELECT id, username, role, created_at, is_active, last_login FROM users WHERE username = ?",
                (username,)
            )
            user = db.fetchone()
            return row_to_dict(user)
        except Exception as e:
            # Check for unique constraint violation
            if "UNIQUE constraint failed" in str(e) or "unique constraint" in str(e).lower():
                raise UserExistsError(f"Username '{username}' is already taken")
            raise


def authenticate(username: str, pin: str) -> Optional[dict]:
    """
    Authenticate a user with username and PIN.
    Only allows active users to login.
    
    Args:
        username: Username to authenticate
        pin: 4-digit PIN to verify
    
    Returns:
        dict: User data if authentication successful, None otherwise
    """
    with get_db() as db:
        db.execute(
            "SELECT id, username, pin_hash, role, created_at, is_active, last_login FROM users WHERE username = ? AND is_active = 1",
            (username,)
        )
        user = db.fetchone()
        
        if user is None:
            return None
        
        # Verify PIN against stored hash
        if not verify_pin(pin, user['pin_hash']):
            return None
        
        # Update last_login timestamp
        db.execute(
            "UPDATE users SET last_login = CURRENT_TIMESTAMP WHERE id = ?",
            (user['id'],)
        )
        
        # Return user data without the hash
        return {
            'id': user['id'],
            'username': user['username'],
            'role': user['role'],
            'created_at': user['created_at'],
            'is_active': user['is_active'],
            'last_login': user['last_login']
        }


def create_session(user_id: int) -> str:
    """
    Create a new session token for an authenticated user.
    
    Args:
        user_id: ID of the authenticated user
    
    Returns:
        str: 32-byte random hex session token
    """
    # Generate cryptographically secure random token (32 bytes = 64 hex chars)
    token = secrets.token_hex(32)
    # Use timezone-aware UTC datetime, stored in SQLite-compatible format
    expires_at = datetime.now(timezone.utc) + timedelta(hours=SESSION_DURATION_HOURS)
    
    with get_db() as db:
        db.execute(
            "INSERT INTO sessions (user_id, token, expires_at) VALUES (?, ?, datetime(?))",
            (user_id, token, expires_at.strftime('%Y-%m-%dT%H:%M:%S'))
        )
    
    return token


def validate_session(token: str) -> Optional[dict]:
    """
    Validate a session token and return associated user.
    Only returns active users.
    
    Args:
        token: Session token to validate
    
    Returns:
        dict: User data if token is valid and not expired, None otherwise
    """
    if not token:
        return None
    
    with get_db() as db:
        db.execute('''
            SELECT u.id, u.username, u.role, u.created_at, u.is_active, u.last_login,
                   s.expires_at, s.created_at as session_created_at
            FROM sessions s
            JOIN users u ON s.user_id = u.id
            WHERE s.token = ? AND datetime(s.expires_at) > datetime('now')
            AND u.is_active = 1
        ''', (token,))
        
        result = db.fetchone()
        if result:
            return row_to_dict(result)
        return None


def invalidate_session(token: str) -> bool:
    """
    Logout by deleting a session token.
    
    Args:
        token: Session token to invalidate
    
    Returns:
        bool: True if session was found and deleted, False otherwise
    """
    with get_db() as db:
        db.execute("DELETE FROM sessions WHERE token = ?", (token,))
        return db.rowcount > 0


def cleanup_expired_sessions() -> int:
    """
    Delete all expired sessions from the database.
    Should be called periodically (e.g., before each request or via cron).
    
    Returns:
        int: Number of expired sessions deleted
    """
    with get_db() as db:
        db.execute("DELETE FROM sessions WHERE datetime(expires_at) < datetime('now')")
        return db.rowcount


def get_user_by_id(user_id: int) -> Optional[dict]:
    """
    Get user data by ID.
    
    Args:
        user_id: User ID to look up
    
    Returns:
        dict: User data without pin_hash, or None if not found
    """
    with get_db() as db:
        db.execute(
            "SELECT id, username, role, created_at, is_active, last_login FROM users WHERE id = ?",
            (user_id,)
        )
        user = db.fetchone()
        return row_to_dict(user)


def get_all_users() -> list:
    """
    Get all users (for admin use).
    
    Returns:
        list: List of user dictionaries without pin_hash
    """
    with get_db() as db:
        db.execute(
            "SELECT id, username, role, created_at, is_active, last_login FROM users ORDER BY created_at DESC"
        )
        return [row_to_dict(row) for row in db.fetchall()]


def update_user(user_id: int, **kwargs) -> Optional[dict]:
    """
    Update user fields.
    
    Args:
        user_id: User ID to update
        **kwargs: Fields to update (pin, role, is_active)
    
    Returns:
        dict: Updated user data, or None if not found
    """
    allowed_fields = {'pin_hash', 'role', 'is_active'}
    updates = {}
    
    if 'pin' in kwargs:
        updates['pin_hash'] = hash_pin(kwargs['pin'])
    if 'role' in kwargs:
        validate_role(kwargs['role'])
        updates['role'] = kwargs['role']
    if 'is_active' in kwargs:
        updates['is_active'] = 1 if kwargs['is_active'] else 0
    
    if not updates:
        return get_user_by_id(user_id)
    
    with get_db() as db:
        # Build update query
        fields = ', '.join(f"{k} = ?" for k in updates.keys())
        values = list(updates.values()) + [user_id]
        
        db.execute(f"UPDATE users SET {fields} WHERE id = ?", values)
        
        if db.rowcount > 0:
            return get_user_by_id(user_id)
        return None


def delete_user(user_id: int) -> bool:
    """
    Soft delete a user by setting is_active to 0.
    
    Args:
        user_id: User ID to delete
    
    Returns:
        bool: True if user was found and deactivated
    """
    with get_db() as db:
        db.execute("UPDATE users SET is_active = 0 WHERE id = ?", (user_id,))
        return db.rowcount > 0


# ============== DECORATORS ==============

def require_auth(f):
    """Decorator to require valid session token."""
    @wraps(f)
    def decorated(*args, **kwargs):
        auth_header = request.headers.get('Authorization', '')
        if not auth_header.startswith('Bearer '):
            return jsonify({"success": False, "error": "Missing or invalid authorization header"}), 401
        
        token = auth_header[7:]  # Remove "Bearer "
        user = validate_session(token)
        
        if not user:
            return jsonify({"success": False, "error": "Invalid or expired session"}), 401
        
        # Store user in flask g for route access
        g.current_user = user
        g.current_token = token
        
        return f(*args, **kwargs)
    return decorated


def require_admin(f):
    """
    Decorator to require admin role.
    Must be used after @require_auth decorator.
    """
    @wraps(f)
    def decorated(*args, **kwargs):
        auth_header = request.headers.get('Authorization', '')
        if not auth_header.startswith('Bearer '):
            return jsonify({"success": False, "error": "Missing or invalid authorization header"}), 401
        
        token = auth_header[7:]  # Remove "Bearer "
        user = validate_session(token)
        
        if not user:
            return jsonify({"success": False, "error": "Invalid or expired session"}), 401
        
        # Check admin role
        if user.get('role') != 'admin':
            return jsonify({"success": False, "error": "Admin access required"}), 403
        
        # Store user in flask g for route access
        g.current_user = user
        g.current_token = token
        
        return f(*args, **kwargs)
    return decorated
