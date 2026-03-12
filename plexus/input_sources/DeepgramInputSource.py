from typing import TYPE_CHECKING

from plexus.input_sources.TextFileInputSource import TextFileInputSource
from plexus.utils.score_result_s3_utils import download_score_result_trace_file

if TYPE_CHECKING:
    from plexus.scores.Score import Score


class DeepgramInputSource(TextFileInputSource):
    """
    Loader-only input source for Deepgram JSON attachments.

    Responsibilities:
    - find the Deepgram attachment
    - download/parse Deepgram JSON
    - return baseline transcript text plus raw deepgram metadata

    Formatting and slicing are intentionally handled by processors.
    """

    def extract(self, item) -> 'Score.Input':
        from plexus.core.ScoreInput import ScoreInput
        import json

        attachment_key = self.find_matching_attachment(item)

        if not attachment_key:
            available = (
                item.attachedFiles
                if item and hasattr(item, "attachedFiles")
                else "None"
            )
            raise ValueError(
                f"No Deepgram file matching pattern '{self.pattern.pattern}' "
                f"found. Available attachments: {available}"
            )

        deepgram_result, _ = download_score_result_trace_file(attachment_key)

        # Parse metadata if it's a JSON string (API items can return strings)
        metadata = {}
        if item.metadata:
            if isinstance(item.metadata, str):
                try:
                    metadata = json.loads(item.metadata)
                except json.JSONDecodeError:
                    self.logger.warning(
                        "Failed to parse metadata JSON for item %s",
                        getattr(item, 'id', 'unknown'),
                    )
                    metadata = {}
            elif isinstance(item.metadata, dict):
                metadata = item.metadata.copy()

        metadata['input_source'] = 'DeepgramInputSource'
        metadata['attachment_key'] = attachment_key
        metadata['deepgram'] = deepgram_result

        # Loader baseline text: raw channel-0 transcript.
        transcript = deepgram_result['results']['channels'][0]['alternatives'][0]['transcript']

        return ScoreInput(text=transcript, metadata=metadata)
