from abc import ABC, abstractmethod
from typing import Any, Dict, Optional, Tuple, List


class BaseReportBlock(ABC):
    """
    Abstract base class for all report blocks.

    Each subclass is responsible for generating a specific section or data
    point within a report.
    """

    def __init__(self, config: Dict[str, Any], params: Optional[Dict[str, Any]], api_client: 'PlexusDashboardClient'):
        self.config = config
        self.params = params if params is not None else {}
        self.api_client = api_client
        self.log_messages = []

    def _log(self, message: str):
        """Helper method to add log messages during generation."""
        self.log_messages.append(message)
        
    def attach_detail_file(self, report_block_id: str, file_name: str, content: str, content_type: Optional[str] = None) -> Dict[str, Any]:
        """
        Attach a detail file to this report block.
        
        This uploads the file to S3 and adds its reference to the ReportBlock's detailsFiles field.
        
        Args:
            report_block_id: ID of the report block to attach the file to
            file_name: Name of the file to create
            content: String content of the file
            content_type: Optional MIME type for the file
            
        Returns:
            The file info dict: {'name': file_name, 'path': s3_path}
        """
        from plexus.reports.s3_utils import add_file_to_report_block
        
        file_details = add_file_to_report_block(
            report_block_id=report_block_id,
            file_name=file_name,
            content=content,
            content_type=content_type,
            client=self.api_client
        )
        
        self._log(f"Attached detail file '{file_name}' to report block {report_block_id}")
        return file_details

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