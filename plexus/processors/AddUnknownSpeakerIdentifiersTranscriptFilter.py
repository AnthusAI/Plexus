import re
from typing import TYPE_CHECKING
from plexus.processors.DataframeProcessor import Processor

if TYPE_CHECKING:
    from plexus.scores.Score import Score


class AddUnknownSpeakerIdentifiersTranscriptFilter(Processor):
    """
    Processor that replaces all speaker identifiers with 'Unknown Speaker:'.
    """

    def process(self, score_input: 'Score.Input') -> 'Score.Input':
        """
        Process the Score.Input by replacing speaker identifiers.

        Args:
            score_input: Score.Input with text

        Returns:
            Score.Input with speaker identifiers replaced
        """
        from plexus.scores.Score import Score

        # Replace all speaker identifiers with 'Unknown Speaker:'
        modified_text = re.sub(
            r'(?:^|\b)\w+:\s*',
            'Unknown Speaker: ',
            str(score_input.text),
            flags=re.MULTILINE
        )

        # Return new Score.Input with modified text
        return Score.Input(
            text=modified_text,
            metadata=score_input.metadata,
            results=score_input.results
        )

