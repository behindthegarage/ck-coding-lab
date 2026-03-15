"""
chat/rate_limit.py - DB-backed rate limiting for chat
Club Kinawa Coding Lab
"""

from datetime import datetime, timedelta
from database import get_db


# Rate limiting configuration
CHAT_RATE_LIMIT_REQUESTS = 10  # Max requests
CHAT_RATE_LIMIT_WINDOW = 60    # Window in seconds


def check_chat_rate_limit(user_id: int) -> tuple[bool, int, int]:
    """
    Check if user has exceeded chat rate limit.
    Uses database-backed storage for multi-process safety.
    
    Returns:
        tuple: (allowed: bool, remaining: int, reset_after: int)
    """
    now = datetime.utcnow()
    window_start = now - timedelta(seconds=CHAT_RATE_LIMIT_WINDOW)
    
    with get_db() as db:
        # Clean old entries for this user
        db.execute('''
            DELETE FROM rate_limit_buckets 
            WHERE user_id = ? AND window_start < datetime(?)
        ''', (user_id, window_start.strftime('%Y-%m-%dT%H:%M:%S')))
        
        # Count current requests in window
        db.execute('''
            SELECT COUNT(*) as count FROM rate_limit_buckets 
            WHERE user_id = ? AND window_start >= datetime(?)
        ''', (user_id, window_start.strftime('%Y-%m-%dT%H:%M:%S')))
        
        result = db.fetchone()
        current_count = result['count'] if result else 0
        
        if current_count >= CHAT_RATE_LIMIT_REQUESTS:
            # Rate limited - calculate reset time
            db.execute('''
                SELECT MIN(window_start) as oldest FROM rate_limit_buckets 
                WHERE user_id = ?
            ''', (user_id,))
            oldest = db.fetchone()
            if oldest and oldest['oldest']:
                oldest_dt = datetime.fromisoformat(oldest['oldest'])
                reset_after = int((oldest_dt + timedelta(seconds=CHAT_RATE_LIMIT_WINDOW) - now).total_seconds())
            else:
                reset_after = CHAT_RATE_LIMIT_WINDOW
            return False, 0, max(0, reset_after)
        
        # Record this request
        db.execute('''
            INSERT INTO rate_limit_buckets (user_id, window_start)
            VALUES (?, datetime(?))
        ''', (user_id, now.strftime('%Y-%m-%dT%H:%M:%S')))
        
        remaining = CHAT_RATE_LIMIT_REQUESTS - current_count - 1
        return True, remaining, 0
