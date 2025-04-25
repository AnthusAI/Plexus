from abc import ABC, abstractmethod
from typing import Any, Dict, Optional


class BaseReportBlock(ABC):
    """
    Abstract base class for all report blocks.

    Each subclass is responsible for generating a specific section or data
    point within a report.
    """

    @abstractmethod
    def generate(
        self, config: Dict[str, Any], params: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Generates the data for this report block.

        Args:
            config: Configuration specific to this block instance, taken from
                    the ReportConfiguration.
            params: Optional runtime parameters passed during report generation.

        Returns:
            A dictionary containing the generated data for the block, which
            must be JSON-serializable.
        """
        pass 