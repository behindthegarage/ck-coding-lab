"""
admin_routes.py - Admin Area Routes
Club Kinawa Coding Lab

Provides admin panel functionality for managing users and viewing stats.
All routes require admin authentication.
"""

from functools import wraps
from flask import Blueprint, request, jsonify, g, render_template, redirect, url_for, flash, make_response
from datetime import datetime, timedelta

from database import get_db, row_to_dict
from auth import (
    require_auth, require_admin, validate_session,
    create_user, update_user, delete_user, get_all_users,
    validate_username, validate_role, AuthError, UserExistsError, InvalidPINError
)



# Web route admin auth - checks for token in cookie
def admin_web_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        token = request.cookies.get('auth_token')
        if not token:
            return redirect('/lab/login')
        user = validate_session(token)
        if not user:
            return redirect('/lab/login')
        if user.get('role') != 'admin':
            return 'Admin access required', 403
        g.current_user = user
        return f(*args, **kwargs)
    return decorated

# Create blueprint
admin_bp = Blueprint('admin', __name__, url_prefix='/admin')
api_admin_bp = Blueprint('api_admin', __name__, url_prefix='/api/admin')


# ============== WEB ROUTES ==============

@admin_bp.route('/')
@admin_web_required
def admin_index():
    """Redirect to dashboard."""
    return redirect(url_for('admin.admin_dashboard'))


@admin_bp.route('/dashboard')
@admin_web_required
def admin_dashboard():
    """Admin dashboard with stats overview."""
    # Get stats
    stats = get_admin_stats()
    return render_template('admin/dashboard.html', stats=stats)


@admin_bp.route('/users')
@admin_web_required
def admin_users():
    """List all users with project counts."""
    users = get_users_with_project_counts()
    return render_template('admin/users/list.html', users=users)


@admin_bp.route('/users/add', methods=['GET'])
@admin_web_required
def admin_add_user_form():
    """Form to add a new user."""
    return render_template('admin/users/add.html')


@admin_bp.route('/users', methods=['POST'])
@admin_web_required
def admin_create_user():
    """Create a new user."""
    username = request.form.get('username', '').strip()
    pin = request.form.get('pin', '').strip()
    role = request.form.get('role', 'kid')
    
    # Validation
    errors = []
    if not username:
        errors.append('Username is required.')
    if not pin:
        errors.append('PIN is required.')
    if len(pin) != 4 or not pin.isdigit():
        errors.append('PIN must be exactly 4 digits.')
    if role not in ('admin', 'kid'):
        errors.append('Invalid role.')
    
    if errors:
        for error in errors:
            flash(error, 'error')
        return render_template('admin/users/add.html', username=username, role=role)
    
    try:
        user = create_user(username, pin, role)
        flash(f"User '{username}' created successfully!", 'success')
        return redirect(url_for('admin.admin_users'))
    except UserExistsError:
        flash(f"Username '{username}' is already taken.", 'error')
        return render_template('admin/users/add.html', username=username, role=role)
    except (AuthError, InvalidPINError) as e:
        flash(str(e), 'error')
        return render_template('admin/users/add.html', username=username, role=role)


@admin_bp.route('/users/<int:user_id>/edit', methods=['GET'])
@admin_web_required
def admin_edit_user_form(user_id):
    """Form to edit a user."""
    user = get_user_with_project_count(user_id)
    if not user:
        flash('User not found.', 'error')
        return redirect(url_for('admin.admin_users'))
    return render_template('admin/users/edit.html', user=user)


@admin_bp.route('/users/<int:user_id>', methods=['POST'])
@admin_web_required
def admin_update_user(user_id):
    """Update a user."""
    pin = request.form.get('pin', '').strip()
    role = request.form.get('role')
    is_active = request.form.get('is_active') == 'on'
    
    # Get current user to check if they're trying to deactivate themselves
    current_admin = g.current_user
    if current_admin['id'] == user_id and not is_active:
        flash('You cannot deactivate your own account.', 'error')
        return redirect(url_for('admin.admin_edit_user_form', user_id=user_id))
    
    updates = {'is_active': is_active}
    
    if pin:
        if len(pin) != 4 or not pin.isdigit():
            flash('PIN must be exactly 4 digits.', 'error')
            return redirect(url_for('admin.admin_edit_user_form', user_id=user_id))
        updates['pin'] = pin
    
    if role:
        updates['role'] = role
    
    # Prevent removing the last admin
    if role == 'kid':
        if is_last_admin(user_id):
            flash('Cannot change role: at least one admin must exist.', 'error')
            return redirect(url_for('admin.admin_edit_user_form', user_id=user_id))
    
    try:
        user = update_user(user_id, **updates)
        if user:
            flash(f"User '{user['username']}' updated successfully!", 'success')
        else:
            flash('User not found.', 'error')
    except AuthError as e:
        flash(str(e), 'error')
    
    return redirect(url_for('admin.admin_users'))


@admin_bp.route('/users/<int:user_id>/delete', methods=['POST'])
def admin_delete_user(user_id):
    """Soft delete (deactivate) a user."""
    current_admin = g.current_user
    if current_admin['id'] == user_id:
        flash('You cannot delete your own account.', 'error')
        return redirect(url_for('admin.admin_users'))
    
    # Prevent deleting the last admin
    if is_last_admin(user_id):
        flash('Cannot delete: at least one admin must exist.', 'error')
        return redirect(url_for('admin.admin_users'))
    
    user = get_user_by_id_safe(user_id)
    if user:
        delete_user(user_id)
        flash(f"User '{user['username']}' has been deactivated.", 'success')
    else:
        flash('User not found.', 'error')
    
    return redirect(url_for('admin.admin_users'))


# ============== API ROUTES ==============

@api_admin_bp.route('/stats')
@require_admin
def api_admin_stats():
    """Get admin stats as JSON."""
    stats = get_admin_stats()
    return jsonify({"success": True, "stats": stats})


@api_admin_bp.route('/users')
@require_admin
def api_admin_users():
    """Get all users with project counts as JSON."""
    users = get_users_with_project_counts()
    return jsonify({"success": True, "users": users})


# ============== HELPER FUNCTIONS ==============

def get_admin_stats():
    """Get admin dashboard statistics."""
    with get_db() as db:
        # Total users
        db.execute("SELECT COUNT(*) FROM users WHERE is_active = 1")
        total_users = db.fetchone()[0]
        
        # Total projects
        db.execute("SELECT COUNT(*) FROM projects")
        total_projects = db.fetchone()[0]
        
        # Total conversations
        db.execute("SELECT COUNT(*) FROM conversations")
        total_conversations = db.fetchone()[0]
        
        # Active today (users who logged in today)
        today = datetime.now().strftime('%Y-%m-%d')
        db.execute('''
            SELECT COUNT(DISTINCT user_id) FROM sessions 
            WHERE DATE(created_at) = DATE('now')
        ''')
        active_today = db.fetchone()[0]
        
        # Additional stats
        db.execute("SELECT COUNT(*) FROM users WHERE role = 'admin' AND is_active = 1")
        admin_count = db.fetchone()[0]
        
        db.execute("SELECT COUNT(*) FROM users WHERE role = 'kid' AND is_active = 1")
        kid_count = db.fetchone()[0]
        
        return {
            'total_users': total_users,
            'total_projects': total_projects,
            'total_conversations': total_conversations,
            'active_today': active_today,
            'admin_count': admin_count,
            'kid_count': kid_count
        }


def get_users_with_project_counts():
    """Get all users with their project counts."""
    with get_db() as db:
        db.execute('''
            SELECT 
                u.id, u.username, u.role, u.created_at, u.is_active, u.last_login,
                COUNT(p.id) as project_count
            FROM users u
            LEFT JOIN projects p ON u.id = p.user_id
            GROUP BY u.id
            ORDER BY u.created_at DESC
        ''')
        return [row_to_dict(row) for row in db.fetchall()]


def get_user_with_project_count(user_id):
    """Get a single user with project count."""
    with get_db() as db:
        db.execute('''
            SELECT 
                u.id, u.username, u.role, u.created_at, u.is_active, u.last_login,
                COUNT(p.id) as project_count
            FROM users u
            LEFT JOIN projects p ON u.id = p.user_id
            WHERE u.id = ?
            GROUP BY u.id
        ''', (user_id,))
        return row_to_dict(db.fetchone())


def get_user_by_id_safe(user_id):
    """Get user by ID (safe version without auth dependency)."""
    with get_db() as db:
        db.execute(
            "SELECT id, username, role, created_at, is_active, last_login FROM users WHERE id = ?",
            (user_id,)
        )
        return row_to_dict(db.fetchone())


def is_last_admin(user_id):
    """Check if this user is the last active admin."""
    with get_db() as db:
        db.execute('''
            SELECT COUNT(*) FROM users 
            WHERE role = 'admin' AND is_active = 1
        ''')
        total_admins = db.fetchone()[0]
        
        if total_admins > 1:
            return False
        
        # Check if this user is the admin we're checking
        db.execute('''
            SELECT role FROM users WHERE id = ? AND is_active = 1
        ''', (user_id,))
        result = db.fetchone()
        return result and result[0] == 'admin'


# ============== REQUEST HOOKS ==============

@admin_bp.before_request
def check_admin_access():
    """Verify admin access before each admin route."""
    # Check for session cookie
    session_token = request.cookies.get("auth_token")
    if not session_token:
        return redirect('/lab/login')
    
    user = validate_session(session_token)
    if not user:
        return redirect('/lab/login')
    
    if user.get('role') != 'admin':
        return "Access Denied: Admin privileges required", 403
    
    # Store user in g for route access
    g.current_user = user
    g.current_token = session_token


@api_admin_bp.before_request
def check_api_admin_access():
    """Verify admin access before each API admin route."""
    auth_header = request.headers.get('Authorization', '')
    if not auth_header.startswith('Bearer '):
        return jsonify({"success": False, "error": "Missing authorization"}), 401
    
    token = auth_header[7:]
    user = validate_session(token)
    
    if not user:
        return jsonify({"success": False, "error": "Invalid or expired session"}), 401
    
    if user.get('role') != 'admin':
        return jsonify({"success": False, "error": "Admin access required"}), 403
    
    g.current_user = user
    g.current_token = token
