"""
Standard command output handling for the Plexus task dispatch system.

Provides a clean interface for commands to write structured output files
that can be uploaded as task attachments.
"""

import os
import json
import logging
from typing import Any, Optional, Dict
from pathlib import Path
import tempfile


class CommandOutputManager:
    """
    Manages output files for commands in the task dispatch system.
    
    Commands can use this to write structured output that gets automatically
    uploaded as task attachments.
    """
    
    def __init__(self, task_id: Optional[str] = None, format_type: Optional[str] = None):
        """
        Initialize the output manager.
        
        Args:
            task_id: The task ID for file naming
            format_type: The output format (e.g., 'json', 'yaml', 'csv')
        """
        self.task_id = task_id
        self.format_type = format_type
        self.temp_dir = None
        self.output_files = {}
        
        # Create temp directory for output files
        if task_id:
            self.temp_dir = tempfile.mkdtemp(prefix=f"plexus_task_{task_id}_")
            logging.info(f"Created temp output directory: {self.temp_dir}")
    
    def get_output_file_path(self, filename: str) -> str:
        """
        Get the path for an output file.
        
        Args:
            filename: The name of the output file
            
        Returns:
            str: Full path to the output file
        """
        if not self.temp_dir:
            # Fallback to current directory if no temp dir
            return filename
        
        return os.path.join(self.temp_dir, filename)
    
    def write_json_output(self, data: Any, filename: str = "output.json") -> str:
        """
        Write JSON output to a file.
        
        Args:
            data: The data to write as JSON
            filename: The output filename
            
        Returns:
            str: Path to the created file
        """
        file_path = self.get_output_file_path(filename)
        
        try:
            with open(file_path, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=2, ensure_ascii=False, default=str)
            
            self.output_files[filename] = file_path
            logging.info(f"Written JSON output to: {file_path}")
            return file_path
        except Exception as e:
            logging.error(f"Failed to write JSON output to {file_path}: {e}")
            raise
    
    def write_text_output(self, content: str, filename: str) -> str:
        """
        Write text output to a file.
        
        Args:
            content: The text content to write
            filename: The output filename
            
        Returns:
            str: Path to the created file
        """
        file_path = self.get_output_file_path(filename)
        
        try:
            with open(file_path, 'w', encoding='utf-8') as f:
                f.write(content)
            
            self.output_files[filename] = file_path
            logging.info(f"Written text output to: {file_path}")
            return file_path
        except Exception as e:
            logging.error(f"Failed to write text output to {file_path}: {e}")
            raise
    
    def get_created_files(self) -> Dict[str, str]:
        """
        Get all files created by this output manager.
        
        Returns:
            Dict[str, str]: Mapping of filename to full path
        """
        return self.output_files.copy()
    
    def cleanup(self):
        """Clean up temporary files and directories."""
        if self.temp_dir and os.path.exists(self.temp_dir):
            try:
                import shutil
                shutil.rmtree(self.temp_dir)
                logging.info(f"Cleaned up temp directory: {self.temp_dir}")
            except Exception as e:
                logging.warning(f"Failed to clean up temp directory {self.temp_dir}: {e}")


# Global instance that commands can use
_output_manager: Optional[CommandOutputManager] = None


def get_output_manager() -> Optional[CommandOutputManager]:
    """Get the global output manager instance."""
    return _output_manager


def set_output_manager(manager: CommandOutputManager):
    """Set the global output manager instance."""
    global _output_manager
    _output_manager = manager


def write_json_output(data: Any, filename: str = "output.json") -> Optional[str]:
    """
    Convenience function to write JSON output using the global manager.
    
    Args:
        data: The data to write as JSON
        filename: The output filename
        
    Returns:
        Optional[str]: Path to created file, or None if no manager
    """
    manager = get_output_manager()
    if manager:
        return manager.write_json_output(data, filename)
    return None


def write_text_output(content: str, filename: str) -> Optional[str]:
    """
    Convenience function to write text output using the global manager.
    
    Args:
        content: The text content to write
        filename: The output filename
        
    Returns:
        Optional[str]: Path to created file, or None if no manager
    """
    manager = get_output_manager()
    if manager:
        return manager.write_text_output(content, filename)
    return None


def should_write_json_output() -> bool:
    """
    Check if commands should write JSON output files.
    
    Returns:
        bool: True if JSON output should be written
    """
    manager = get_output_manager()
    return manager is not None and manager.format_type == 'json'


def get_format_type() -> Optional[str]:
    """
    Get the current output format type.
    
    Returns:
        Optional[str]: The format type, or None if not set
    """
    manager = get_output_manager()
    return manager.format_type if manager else None