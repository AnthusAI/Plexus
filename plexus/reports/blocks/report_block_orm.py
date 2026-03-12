"""
ORM-style ReportBlock class for programmatic API interaction.

This provides a unified interface for working with ReportBlock records,
including standardized logging, file attachment, and real-time updates.
"""

import logging
import pandas as pd
from typing import Any, Dict, Optional, List
from plexus.dashboard.api.client import PlexusDashboardClient


class ReportBlockORM:
    """
    ORM-style class for programmatic ReportBlock API interaction.
    
    Provides unified logging, file management, and eventual real-time updates.
    """
    
    def __init__(self, 
                 api_client: PlexusDashboardClient,
                 report_block_id: Optional[str] = None,
                 config: Optional[Dict[str, Any]] = None):
        """
        Initialize ReportBlock ORM instance.
        
        Args:
            api_client: Dashboard API client for operations
            report_block_id: Existing report block ID (None for new blocks)
            config: Block configuration dictionary
        """
        self.api_client = api_client
        self.report_block_id = report_block_id
        self.config = config or {}
        self.log_messages: List[str] = []
        self.attached_files: List[str] = []
        
        # Set up logging
        self.logger = logging.getLogger(self.__class__.__module__)
        
    def log(self, message: str, level: str = "INFO", console_only: bool = False):
        """
        Unified logging method that sends to both console and attached log by default.
        
        Args:
            message: Log message to record
            level: Log level (DEBUG, INFO, WARNING, ERROR)
            console_only: If True, only log to console, not to attached log
        """
        # Always log to console via standard logging
        log_method = getattr(self.logger, level.lower(), self.logger.info)
        
        # Add block context if we have a block ID
        block_context = f"[ReportBlock {self.report_block_id}]" if self.report_block_id else "[ReportBlock]"
        log_method(f"{block_context} {message}")
        
        # Also store in attached log unless console_only is True
        if not console_only:
            # Don't store DEBUG logs in attached log to reduce noise
            if level.upper() != "DEBUG":
                timestamp = pd.Timestamp.now(tz='UTC').isoformat()
                self.log_messages.append(f"{timestamp} [{level.upper()}] {message}")
    
    def log_debug(self, message: str, console_only: bool = False):
        """Convenience method for DEBUG level logging."""
        self.log(message, "DEBUG", console_only)
        
    def log_info(self, message: str, console_only: bool = False):
        """Convenience method for INFO level logging."""
        self.log(message, "INFO", console_only)
        
    def log_warning(self, message: str, console_only: bool = False):
        """Convenience method for WARNING level logging."""
        self.log(message, "WARNING", console_only)
        
    def log_error(self, message: str, console_only: bool = False):
        """Convenience method for ERROR level logging."""
        self.log(message, "ERROR", console_only)
    
    def attach_file(self, file_name: str, content: bytes, content_type: Optional[str] = None) -> str:
        """
        Attach a file to this report block.
        
        Args:
            file_name: Name of the file to create
            content: Bytes content of the file
            content_type: Optional MIME type for the file
            
        Returns:
            The S3 path to the file
            
        Raises:
            ValueError: If no report_block_id is set
        """
        if not self.report_block_id:
            raise ValueError("Cannot attach files: report_block_id not set")
            
        from plexus.reports.s3_utils import add_file_to_report_block
        
        file_path = add_file_to_report_block(
            report_block_id=self.report_block_id,
            file_name=file_name,
            content=content,
            content_type=content_type,
            client=self.api_client
        )
        
        self.attached_files.append(file_path)
        self.log_info(f"Attached file '{file_name}' to report block")
        return file_path
    
    def get_log_string(self) -> str:
        """
        Get the complete log string for this report block.
        
        Returns:
            Concatenated log messages as a single string
        """
        return "\n".join(self.log_messages)
    
    def get_attached_files(self) -> List[str]:
        """
        Get list of files attached to this report block.
        
        Returns:
            List of S3 file paths
        """
        return self.attached_files.copy()
    
    def set_report_block_id(self, report_block_id: str):
        """
        Set the report block ID (used when creating new blocks).
        
        Args:
            report_block_id: The report block ID from the database
        """
        self.report_block_id = report_block_id
        self.log_debug(f"Set report block ID: {report_block_id}")
    
    # Future methods for real-time updates (out of scope for now):
    # def update_output(self, output_data: Dict[str, Any]):
    # def update_log(self):  
    # def update_attached_files(self):
    # def save(self):