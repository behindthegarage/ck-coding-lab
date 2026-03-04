"""
database_migrations.py - Database migrations for agentic workflow
Club Kinawa Coding Lab

Adds project_files table for file-based project memory.
"""

import sqlite3
from datetime import datetime


def migrate_v5_project_files(db_path: str = None) -> None:
    """
    Migration: Add project_files table for agentic workflow.
    
    Creates:
    - project_files: Stores design.md, architecture.md, todo.md, notes.md, code files
    """
    if db_path is None:
        from database import DATABASE_PATH
        db_path = DATABASE_PATH
    
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    # Create project_files table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS project_files (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            project_id INTEGER NOT NULL,
            filename TEXT NOT NULL,
            content TEXT DEFAULT '',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (project_id) REFERENCES projects (id) ON DELETE CASCADE,
            UNIQUE(project_id, filename)
        )
    ''')
    
    # Create index for faster lookups
    cursor.execute('''
        CREATE INDEX IF NOT EXISTS idx_project_files_project ON project_files (project_id)
    ''')
    
    cursor.execute('''
        CREATE INDEX IF NOT EXISTS idx_project_files_filename ON project_files (project_id, filename)
    ''')
    
    conn.commit()
    conn.close()
    print("Migration v5: project_files table created successfully.")


def init_db_full_agentic(db_path: str = None) -> None:
    """Initialize complete database including all migrations for agentic workflow."""
    from database import init_db_full
    init_db_full(db_path)
    migrate_v5_project_files(db_path)


if __name__ == '__main__':
    init_db_full_agentic()
    print("All migrations completed.")
