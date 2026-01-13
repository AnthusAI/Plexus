import logging
import re
from abc import ABC, abstractmethod
from typing import Optional


class InputSource(ABC):
    """
    Base class for input sources that extract text from various sources.
    Input sources run BEFORE processors in the pipeline.
    """

    def __init__(self, pattern: str = None, **options):
        """
        Args:
            pattern: Regex pattern to match attachments (used by file-based sources)
            **options: Additional source-specific options
        """
        self.pattern = re.compile(pattern) if pattern else None
        self.options = options
        self.logger = logging.getLogger(self.__class__.__name__)

    @abstractmethod
    def extract(self, item, default_text: str) -> str:
        """
        Extract text from the specified source.

        Args:
            item: Item object (may have attachedFiles)
            default_text: Fallback text from item.text

        Returns:
            Extracted text string
        """
        pass

    def find_matching_attachment(self, item) -> Optional[str]:
        """
        Find first attachment matching the regex pattern.

        Args:
            item: Item object with attachedFiles list

        Returns:
            S3 key path of matching attachment, or None
        """
        if not self.pattern:
            raise ValueError(f"{self.__class__.__name__} requires a pattern")

        if not item or not hasattr(item, "attachedFiles") or not item.attachedFiles:
            return None

        for file_key in item.attachedFiles:
            filename = file_key.split("/")[-1]  # Extract filename from S3 path
            if self.pattern.match(filename):
                self.logger.info(f"Matched attachment: {file_key}")
                return file_key

        return None
