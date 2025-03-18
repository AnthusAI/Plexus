"""
Implementation of the file editing tool protocol for Plexus's self-improving AI agents.

This module implements the file editing tool protocol as defined in:
https://docs.anthropic.com/en/docs/build-with-claude/tool-use/text-editor-tool

The file editing capabilities are a critical component of Plexus's agent-based data processing system,
enabling AI agents to modify and improve their own code. This is part of Plexus's self-improving AI
architecture described at: https://plexus.anth.us/solutions/platform

The FileEditor class provides the following operations:
- Viewing file contents
- Replacing text
- Inserting text
- Creating new files
- Undoing changes

Each operation includes automatic backup creation and error handling to ensure safe file modifications
by AI agents.
"""

from typing import Optional, Dict
import os
from pathlib import Path
import shutil
import time

class FileEditor:
    """A class to handle file editing operations for LLM tool calls."""
    
    def __init__(self, debug: bool = False):
        """Initialize the FileEditor.
        
        Args:
            debug: Whether to enable debug mode with more verbose output
        """
        self.debug = debug
        self._last_edit: Dict[str, str] = {}  # Maps file paths to their last backup path
    
    def _create_backup(self, file_path: str) -> str:
        """Create a backup of a file before editing.
        
        Args:
            file_path: Path to the file to backup
            
        Returns:
            Path to the backup file
        """
        if not os.path.exists(file_path):
            return None
            
        # Create backup in same directory as original file
        timestamp = int(time.time() * 1000)  # Millisecond timestamp
        backup_name = f"{os.path.basename(file_path)}.{timestamp}.bak"
        backup_path = os.path.join(os.path.dirname(file_path), backup_name)
        
        shutil.copy2(file_path, backup_path)
        return backup_path
    
    def view(self, file_path: str) -> str:
        """View the contents of a file.
        
        Args:
            file_path: Path to the file to view
            
        Returns:
            The contents of the file as a string
            
        Raises:
            FileNotFoundError: If the file does not exist
        """
        if not os.path.exists(file_path):
            raise FileNotFoundError(f"File not found: {file_path}")
            
        with open(file_path, 'r') as f:
            return f.read()
    
    def str_replace(self, file_path: str, old_str: str, new_str: str) -> str:
        """Replace text in a file.
        
        Args:
            file_path: Path to the file to edit
            old_str: Text to replace
            new_str: Text to replace with
            
        Returns:
            A status message indicating success or failure
            
        Raises:
            FileNotFoundError: If the file does not exist
        """
        if not os.path.exists(file_path):
            return "Error: Missing parameters or file not found (file not found)"
            
        if not old_str:
            return "Error: Missing parameters or file not found (old_str missing)"
            
        if not new_str:
            try:
                # Get additional context about the failure for debugging
                old_str_len = len(old_str) if old_str else 0
                return f"Error: Missing parameters or file not found (new_str missing, old_str length: {old_str_len})"
            except Exception as e:
                return f"Error: Missing parameters or file not found (new_str missing, error counting old_str: {str(e)})"
        
        try:
            # Create backup before making changes
            backup_path = self._create_backup(file_path)
            if backup_path:
                self._last_edit[file_path] = backup_path
            
            with open(file_path, 'r') as f:
                content = f.read()
            
            match_count = content.count(old_str)
            
            if match_count == 0:
                return "Error: No match found for replacement text"
            
            updated_content = content.replace(old_str, new_str)
            
            # Check if content actually changed
            if updated_content == content:
                if self.debug:
                    print("Warning: Content unchanged after replacement")
            
            with open(file_path, 'w') as f:
                f.write(updated_content)
            
            return f"Successfully replaced text ({match_count} occurrences)"
        except Exception as e:
            # Provide more detailed error information
            return f"Error during replacement: {str(e)}"
    
    def undo_edit(self, file_path: str) -> str:
        """Undo the last edit made to a file.
        
        Args:
            file_path: Path to the file to undo changes for
            
        Returns:
            A status message indicating success or failure
        """
        if file_path not in self._last_edit:
            return "Error: No previous edit found to undo"
            
        backup_path = self._last_edit[file_path]
        if not os.path.exists(backup_path):
            return "Error: Backup file not found"
            
        try:
            shutil.copy2(backup_path, file_path)
            del self._last_edit[file_path]
            return "Successfully restored previous version"
        except Exception as e:
            return f"Error restoring previous version: {str(e)}"
    
    def insert(self, file_path: str, insert_line: int, new_str: str) -> str:
        """Insert text at a specific line in a file.
        
        Args:
            file_path: Path to the file to edit
            insert_line: Line number to insert at (0-based)
            new_str: Text to insert
            
        Returns:
            A status message indicating success or failure
        """
        if not os.path.exists(file_path):
            return "Error: Missing parameters or file not found (file not found)"
            
        if not new_str:
            return "Error: Missing parameters or file not found (new_str missing)"
        
        # Create backup before making changes
        backup_path = self._create_backup(file_path)
        if backup_path:
            self._last_edit[file_path] = backup_path
        
        with open(file_path, 'r') as f:
            lines = f.readlines()
        
        # Handle negative line numbers and beyond-end line numbers
        if insert_line < 0:
            insert_line = 0
        elif insert_line > len(lines):
            insert_line = len(lines)
        
        # Ensure new_str ends with a newline
        if not new_str.endswith('\n'):
            new_str += '\n'
        
        # Insert the new line
        lines.insert(insert_line, new_str)
        
        with open(file_path, 'w') as f:
            f.writelines(lines)
        
        return f"Successfully inserted text at line {insert_line}"
    
    def create(self, file_path: str, content: str = "") -> str:
        """Create a new file with the specified content.
        
        Args:
            file_path: Path to the file to create
            content: Content to write to the file (default: empty string)
            
        Returns:
            str: Success or error message
        """
        if not file_path:
            return "Error: Missing parameters or file not found (file_path missing)"
            
        if os.path.exists(file_path):
            return "Error: File already exists"
            
        try:
            # Ensure content ends with newline
            if content and not content.endswith('\n'):
                content += '\n'
                
            # Create the file with content
            with open(file_path, 'w') as f:
                f.write(content)
                
            return "Successfully created new file"
            
        except Exception as e:
            return f"Error: Failed to create file: {str(e)}" 