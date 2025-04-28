from abc import ABC, abstractmethod
from typing import Any, Dict, Optional, Tuple


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

    @abstractmethod
    def generate(
        self
    ) -> Tuple[Optional[Dict[str, Any]], Optional[str]]:
        """
        Generates the data for this report block synchronously.

        Access block configuration via `self.config` and report parameters via `self.params`.
        Use `self.api_client` for data fetching.
        Use `self._log("message")` to record log information.

        Returns:
            A tuple containing:
                - A dictionary containing the generated data (JSON-serializable), or None on failure.
                - A string containing concatenated log messages, or None if no logs.
        """
        pass 