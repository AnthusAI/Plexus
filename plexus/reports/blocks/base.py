from abc import ABC, abstractmethod
from typing import Any, Dict, Optional, Tuple, List
from plexus.dashboard.api.client import PlexusDashboardClient
from .report_block_orm import ReportBlockORM


class BaseReportBlock(ABC):
    """
    Abstract base class for all report blocks.

    Each subclass is responsible for generating a specific section or data
    point within a report.
    """
    
    # Class-level defaults that subclasses can override
    DEFAULT_NAME: Optional[str] = None
    DEFAULT_DESCRIPTION: Optional[str] = None

    def __init__(self, config: Dict[str, Any], params: Optional[Dict[str, Any]], api_client: 'PlexusDashboardClient'):
        self.config = config
        self.params = params if params is not None else {}
        self.api_client = api_client
        self.report_block_id = None  # This will be set by the report service if available
        
        # Initialize ORM-style logging and file management
        self._orm = ReportBlockORM(api_client, self.report_block_id, config)
        
        # Backward compatibility - maintain old interface
        self.log_messages = self._orm.log_messages

    def _log(self, message: str, level: str = "INFO", console_only: bool = False):
        """
        Unified logging method that sends to both console and attached log by default.
        
        Args:
            message: Log message to record
            level: Log level (DEBUG, INFO, WARNING, ERROR) 
            console_only: If True, only log to console, not to attached log
        """
        if self.report_block_id and not self._orm.report_block_id:
            self._orm.set_report_block_id(self.report_block_id)
            
        self._orm.log(message, level, console_only)
        
    def attach_detail_file(self, report_block_id: str, file_name: str, content: bytes, content_type: Optional[str] = None) -> str:
        """
        Attach a detail file to this report block.
        
        This uploads the file to S3 and adds its path to the ReportBlock's attachedFiles field.
        The Amplify Gen2 storage expects paths to be stored, not complex objects.
        
        Args:
            report_block_id: ID of the report block to attach the file to
            file_name: Name of the file to create
            content: Bytes content of the file (changed from str to bytes)
            content_type: Optional MIME type for the file
            
        Returns:
            The S3 path to the file
        """
        # Ensure ORM has the report block ID
        if not self._orm.report_block_id:
            self._orm.set_report_block_id(report_block_id)
            
        return self._orm.attach_file(file_name, content, content_type)
    
    def _get_log_string(self) -> str:
        """Get the complete log string for this report block."""
        return self._orm.get_log_string()

    @abstractmethod
    async def generate(
        self
    ) -> Tuple[Optional[Dict[str, Any]], Optional[str]]:
        """
        Generates the data for this report block asynchronously.

        Access block configuration via `self.config` and report parameters via `self.params`.
        Use `self.api_client` for data fetching.
        Use `self._log("message")` to record log information.

        Returns:
            A tuple containing:
                - A dictionary containing the generated data (JSON-serializable), or None on failure.
                - A string containing concatenated log messages, or None if no logs.
        """
        pass 