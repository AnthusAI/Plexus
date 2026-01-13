from plexus.input_sources.InputSource import InputSource
from plexus.utils.score_result_s3_utils import download_score_result_log_file


class TextFileInputSource(InputSource):
    """
    Extracts raw text from a file attachment matching a pattern.
    """

    def extract(self, item, default_text: str) -> str:
        """
        Find and return text from matching attachment.

        Args:
            item: Item with attachedFiles
            default_text: Not used (kept for interface compatibility)

        Returns:
            Text content from file

        Raises:
            ValueError: If no matching attachment found
            Exception: If file download or parsing fails
        """
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
        return text_content
