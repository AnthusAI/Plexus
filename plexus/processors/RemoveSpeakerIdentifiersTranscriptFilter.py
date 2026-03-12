import re
from typing import TYPE_CHECKING
from plexus.processors.DataframeProcessor import Processor

if TYPE_CHECKING:
    from plexus.scores.Score import Score


class RemoveSpeakerIdentifiersTranscriptFilter(Processor):
    """
    Processor that removes speaker identifiers from transcript text.

    Removes patterns like "Agent:", "Customer:", etc. from the beginning of lines.
    """

    def process(self, score_input: 'Score.Input') -> 'Score.Input':
        """
        Process the Score.Input by removing speaker identifiers.

        Args:
            score_input: Score.Input with text containing speaker labels

        Returns:
            Score.Input with speaker labels removed
        """
        from plexus.scores.Score import Score

        # Remove speaker identifiers
        filtered_text = re.sub(
            r'(?:^|\b)\w+:\s*',
            '',
            str(score_input.text),
            flags=re.MULTILINE
        )

        # Return new Score.Input with filtered text
        return Score.Input(
            text=filtered_text,
            metadata=score_input.metadata,
            results=score_input.results
        )
