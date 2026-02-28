"""
database.py - SQLite Database Schema and Connection Management
Club Kinawa Coding Lab - Authentication System

Provides database initialization and connection context manager.
All SQL uses parameterized queries for security.
"""

import sqlite3
from contextlib import contextmanager
from datetime import datetime
import os

# Default database path - can be overridden via environment variable
DATABASE_PATH = os.environ.get('CKCL_DB_PATH', 'ckcl.db')


def init_db(db_path: str = None) -> None:
    """
    Initialize the database with required tables.
    
    Creates the following tables:
    - users: Stores kid accounts with PIN hashes
    - sessions: Stores active authentication sessions
    
    Args:
        db_path: Optional path to database file. Uses DATABASE_PATH if not provided.
    """
    if db_path is None:
        db_path = DATABASE_PATH
    
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    # Create users table
    # Stores kid accounts with hashed 4-digit PINs
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            pin_hash TEXT NOT NULL,
            role TEXT DEFAULT 'kid' CHECK (role IN ('admin', 'kid')),
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            is_active BOOLEAN DEFAULT 1,
            last_login TIMESTAMP
        )
    ''')
    
    # Create sessions table
    # Stores active authentication sessions with expiration
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS sessions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            token TEXT UNIQUE NOT NULL,
            expires_at TIMESTAMP NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users (id) ON DELETE CASCADE
        )
    ''')
    
    # Create index on session tokens for faster lookup
    cursor.execute('''
        CREATE INDEX IF NOT EXISTS idx_sessions_token ON sessions (token)
    ''')
    
    # Create index on session expiration for cleanup queries
    cursor.execute('''
        CREATE INDEX IF NOT EXISTS idx_sessions_expires ON sessions (expires_at)
    ''')
    
    conn.commit()
    conn.close()


@contextmanager
def get_db(db_path: str = None):
    """
    Context manager for database connections.
    
    Usage:
        with get_db() as db:
            db.execute("SELECT * FROM users WHERE id = ?", (user_id,))
            result = db.fetchone()
    
    Args:
        db_path: Optional path to database file. Uses DATABASE_PATH if not provided.
    
    Yields:
        sqlite3.Cursor: Database cursor for executing queries.
    """
    if db_path is None:
        db_path = DATABASE_PATH
    
    conn = sqlite3.connect(db_path)
    # Enable foreign key support
    conn.execute("PRAGMA foreign_keys = ON")
    # Return rows as sqlite3.Row for dict-like access
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    
    try:
        yield cursor
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def row_to_dict(row: sqlite3.Row) -> dict:
    """
    Convert a sqlite3.Row to a regular dictionary.
    
    Args:
        row: sqlite3.Row object from query result
    
    Returns:
        dict: Dictionary representation of the row
    """
    if row is None:
        return None
    return {key: row[key] for key in row.keys()}


def migrate_v2_projects_and_conversations(db_path: str = None) -> None:
    """
    Migration: Add projects and conversations tables for chat/AI features.
    
    Creates:
    - projects: Stores kid coding projects
    - conversations: Stores chat history per project
    - code_versions: Stores saved versions of project code
    """
    if db_path is None:
        db_path = DATABASE_PATH
    
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    # Create projects table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS projects (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            name TEXT NOT NULL,
            description TEXT,
            current_code TEXT DEFAULT '',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            is_public BOOLEAN DEFAULT 0,
            share_token TEXT UNIQUE,
            FOREIGN KEY (user_id) REFERENCES users (id) ON DELETE CASCADE
        )
    ''')
    
    # Create index on user_id for fetching user's projects
    cursor.execute('''
        CREATE INDEX IF NOT EXISTS idx_projects_user ON projects (user_id)
    ''')
    
    # Create index on share_token for public sharing
    cursor.execute('''
        CREATE INDEX IF NOT EXISTS idx_projects_share ON projects (share_token)
    ''')
    
    # Create conversations table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS conversations (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            project_id INTEGER NOT NULL,
            role TEXT NOT NULL CHECK (role IN ('user', 'assistant', 'system')),
            content TEXT NOT NULL,
            model TEXT,
            tokens_used INTEGER,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (project_id) REFERENCES projects (id) ON DELETE CASCADE
        )
    ''')
    
    # Create index on project_id for fetching conversation history
    cursor.execute('''
        CREATE INDEX IF NOT EXISTS idx_conversations_project ON conversations (project_id)
    ''')
    
    # Create code_versions table for manual save points
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS code_versions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            project_id INTEGER NOT NULL,
            code TEXT NOT NULL,
            description TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (project_id) REFERENCES projects (id) ON DELETE CASCADE
        )
    ''')
    
    conn.commit()
    conn.close()


def migrate_v3_add_language(db_path: str = None) -> None:
    """
    Migration: Add language column to projects table.
    
    Default is 'p5js' for backwards compatibility.
    """
    if db_path is None:
        db_path = DATABASE_PATH
    
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    # Check if language column already exists
    cursor.execute("PRAGMA table_info(projects)")
    columns = [row[1] for row in cursor.fetchall()]
    
    if 'language' not in columns:
        print("Adding language column to projects table...")
        cursor.execute('''
            ALTER TABLE projects
            ADD COLUMN language TEXT DEFAULT 'p5js'
        ''')
        conn.commit()
        print("Language column added successfully.")
    else:
        print("Language column already exists.")
    
    conn.close()


def migrate_v4_admin_columns(db_path: str = None) -> None:
    """
    Migration: Add role column to users table for admin functionality.
    
    Adds:
    - role: TEXT 'admin' or 'kid' (default 'kid')
    - Ensures existing users have appropriate roles
    """
    if db_path is None:
        db_path = DATABASE_PATH
    
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    # Check if role column exists
    cursor.execute("PRAGMA table_info(users)")
    columns = [row[1] for row in cursor.fetchall()]
    
    if 'role' not in columns:
        print("Adding role column to users table...")
        cursor.execute('''
            ALTER TABLE users
            ADD COLUMN role TEXT DEFAULT 'kid' CHECK (role IN ('admin', 'kid'))
        ''')
        conn.commit()
        print("Role column added successfully.")
    else:
        print("Role column already exists.")
    
    # Set admin user role
    cursor.execute("UPDATE users SET role = 'admin' WHERE username = 'admin'")
    if cursor.rowcount > 0:
        print(f"Set {cursor.rowcount} admin user(s) to role 'admin'.")
    
    # Ensure all users without role are set to 'kid'
    cursor.execute("UPDATE users SET role = 'kid' WHERE role IS NULL")
    if cursor.rowcount > 0:
        print(f"Set {cursor.rowcount} users to default role 'kid'.")
    
    conn.commit()
    conn.close()


def init_db_full(db_path: str = None) -> None:
    """
    Initialize complete database including all migrations.
    
    Args:
        db_path: Optional path to database file.
    """
    init_db(db_path)
    migrate_v2_projects_and_conversations(db_path)
    migrate_v3_add_language(db_path)
    migrate_v4_admin_columns(db_path)
