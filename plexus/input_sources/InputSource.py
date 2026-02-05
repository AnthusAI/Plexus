import logging
import re
from abc import ABC, abstractmethod
from typing import Optional, TYPE_CHECKING

if TYPE_CHECKING:
    from plexus.scores.Score import Score


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
    def extract(self, item) -> 'Score.Input':
        """
        Extract Score.Input from the specified source.

        This method is the core of the input source pipeline. It takes an Item
        and produces a Score.Input with text and metadata populated.

        Args:
            item: Item object (may have attachedFiles, text, metadata)

        Returns:
            Score.Input with text field and metadata populated

        Example:
            class MyInputSource(InputSource):
                def extract(self, item):
                    # Extract text from source
                    text = self.get_text_from_source(item)

                    # Build metadata
                    metadata = item.metadata or {}
                    metadata['source'] = 'MyInputSource'

                    # Return Score.Input
                    from plexus.scores.Score import Score
                    return Score.Input(text=text, metadata=metadata)
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
