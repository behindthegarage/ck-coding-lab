# ai/tools.py - File Tools for AI Interactions
"""
Tools for AI to interact with project files in the database.
Provides read, write, append, and list operations.
"""

from typing import List, Dict

from database import get_db


class FileTools:
    """Tools for AI to interact with project files."""
    
    def __init__(self, project_id: int):
        self.project_id = project_id
    
    def read_file(self, filename: str) -> Dict:
        """Read a file from the project."""
        try:
            with get_db() as db:
                db.execute('''
                    SELECT content FROM project_files
                    WHERE project_id = ? AND filename = ?
                ''', (self.project_id, filename))
                
                row = db.fetchone()
                if row:
                    return {
                        "success": True,
                        "filename": filename,
                        "content": row['content'],
                        "exists": True
                    }
                else:
                    return {
                        "success": True,
                        "filename": filename,
                        "content": "",
                        "exists": False
                    }
        except Exception as e:
            return {
                "success": False,
                "error": str(e),
                "filename": filename
            }
    
    def write_file(self, filename: str, content: str) -> Dict:
        """Write or overwrite a file in the project."""
        try:
            with get_db() as db:
                # Check if file exists
                db.execute('''
                    SELECT id FROM project_files
                    WHERE project_id = ? AND filename = ?
                ''', (self.project_id, filename))
                
                existing = db.fetchone()
                
                if existing:
                    # Update
                    db.execute('''
                        UPDATE project_files
                        SET content = ?, updated_at = CURRENT_TIMESTAMP
                        WHERE id = ?
                    ''', (content, existing['id']))
                    action = "updated"
                else:
                    # Create
                    db.execute('''
                        INSERT INTO project_files (project_id, filename, content)
                        VALUES (?, ?, ?)
                    ''', (self.project_id, filename, content))
                    action = "created"
                
                return {
                    "success": True,
                    "filename": filename,
                    "action": action,
                    "content_length": len(content)
                }
        except Exception as e:
            return {
                "success": False,
                "error": str(e),
                "filename": filename
            }
    
    def append_file(self, filename: str, content: str) -> Dict:
        """Append content to a file (creates if doesn't exist)."""
        try:
            with get_db() as db:
                # Check if file exists
                db.execute('''
                    SELECT id, content FROM project_files
                    WHERE project_id = ? AND filename = ?
                ''', (self.project_id, filename))
                
                existing = db.fetchone()
                
                if existing:
                    # Append
                    new_content = existing['content'] + content
                    db.execute('''
                        UPDATE project_files
                        SET content = ?, updated_at = CURRENT_TIMESTAMP
                        WHERE id = ?
                    ''', (new_content, existing['id']))
                    action = "appended"
                else:
                    # Create new
                    db.execute('''
                        INSERT INTO project_files (project_id, filename, content)
                        VALUES (?, ?, ?)
                    ''', (self.project_id, filename, content))
                    action = "created"
                
                return {
                    "success": True,
                    "filename": filename,
                    "action": action,
                    "appended_length": len(content)
                }
        except Exception as e:
            return {
                "success": False,
                "error": str(e),
                "filename": filename
            }
    
    def list_files(self) -> Dict:
        """List all files in the project."""
        try:
            with get_db() as db:
                db.execute('''
                    SELECT filename, updated_at
                    FROM project_files
                    WHERE project_id = ?
                    ORDER BY filename
                ''', (self.project_id,))
                
                files = [{"filename": row['filename'], "updated_at": row['updated_at']} 
                        for row in db.fetchall()]
                
                return {
                    "success": True,
                    "files": files,
                    "count": len(files)
                }
        except Exception as e:
            return {
                "success": False,
                "error": str(e)
            }
    
    def get_tool_definitions(self) -> List[Dict]:
        """Get tool definitions for the AI."""
        return [
            {
                "name": "read_file",
                "description": "Read the content of a project file. Use this to check current state before making changes.",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "filename": {
                            "type": "string",
                            "description": "The name of the file to read (e.g., 'design.md', 'todo.md', 'main.js')"
                        }
                    },
                    "required": ["filename"]
                }
            },
            {
                "name": "write_file",
                "description": "Write or overwrite a project file. Use this to save designs, architecture, todo lists, or code.",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "filename": {
                            "type": "string",
                            "description": "The name of the file to write (e.g., 'design.md', 'main.js')"
                        },
                        "content": {
                            "type": "string",
                            "description": "The content to write to the file"
                        }
                    },
                    "required": ["filename", "content"]
                }
            },
            {
                "name": "append_file",
                "description": "Append content to the end of a project file. Useful for adding to session logs or notes.",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "filename": {
                            "type": "string",
                            "description": "The name of the file to append to (e.g., 'notes.md', 'session.log')"
                        },
                        "content": {
                            "type": "string",
                            "description": "The content to append to the file"
                        }
                    },
                    "required": ["filename", "content"]
                }
            },
            {
                "name": "list_files",
                "description": "List all files in the project to see what exists.",
                "input_schema": {
                    "type": "object",
                    "properties": {}
                }
            }
        ]
    
    def execute_tool(self, tool_name: str, tool_input: Dict) -> Dict:
        """Execute a tool by name."""
        if tool_name == "read_file":
            return self.read_file(tool_input.get("filename"))
        elif tool_name == "write_file":
            return self.write_file(tool_input.get("filename"), tool_input.get("content", ""))
        elif tool_name == "append_file":
            return self.append_file(tool_input.get("filename"), tool_input.get("content", ""))
        elif tool_name == "list_files":
            return self.list_files()
        else:
            return {"success": False, "error": f"Unknown tool: {tool_name}"}
