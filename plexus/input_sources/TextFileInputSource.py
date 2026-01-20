from plexus.input_sources.InputSource import InputSource
from plexus.utils.score_result_s3_utils import download_score_result_log_file


class TextFileInputSource(InputSource):
    """
    Extracts raw text from a file attachment matching a pattern.
    """

    def extract(self, item) -> 'Score.Input':
        """
        Find and return Score.Input with text from matching attachment.

        Args:
            item: Item with attachedFiles

        Returns:
            Score.Input with text content from file

        Raises:
            ValueError: If no matching attachment found
            Exception: If file download or parsing fails
        """
        # Import from lightweight module to avoid psycopg dependencies
        from plexus.core.ScoreInput import ScoreInput

        # Find matching attachment
        attachment_key = self.find_matching_attachment(item)

        if not attachment_key:
            available = (
                item.attachedFiles
                if item and hasattr(item, "attachedFiles")
                else "None"
            )
            raise ValueError(
                f"No attachment matching pattern '{self.pattern.pattern}' found. "
                f"Available attachments: {available}"
            )

        # Download text file from S3 (exceptions propagate)
        text_content, _ = download_score_result_log_file(attachment_key)
        self.logger.info(f"Loaded {len(text_content)} characters from {attachment_key}")

        # Build metadata
        # Parse metadata if it's a JSON string (handle API items where metadata is a string)
        import json
        metadata = {}
        if item.metadata:
            if isinstance(item.metadata, str):
                try:
                    metadata = json.loads(item.metadata)
                except json.JSONDecodeError:
                    self.logger.warning(f"Failed to parse metadata JSON for item {getattr(item, 'id', 'unknown')}")
                    metadata = {}
            elif isinstance(item.metadata, dict):
                metadata = item.metadata.copy()

        metadata['input_source'] = 'TextFileInputSource'
        metadata['attachment_key'] = attachment_key

        # Return ScoreInput
        return ScoreInput(text=text_content, metadata=metadata)
