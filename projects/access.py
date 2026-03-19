"""
projects/access.py - Shared project access helpers
Club Kinawa Coding Lab
"""


def is_admin_user(user):
    """Return True when the current session belongs to an admin."""
    return bool(user and user.get('role') == 'admin')



def can_access_project_owner(user, owner_id):
    """Admins can access all projects; everyone else is limited to their own."""
    if not user:
        return False
    return user.get('id') == owner_id or is_admin_user(user)
