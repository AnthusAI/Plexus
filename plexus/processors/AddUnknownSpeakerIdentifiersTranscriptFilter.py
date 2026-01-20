import re
from plexus.processors.DataframeProcessor import Processor

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
        from plexus.core.ScoreInput import ScoreInput

        # Replace all speaker identifiers with 'Unknown Speaker:'
        modified_text = re.sub(
            r'(?:^|\b)\w+:\s*',
            'Unknown Speaker: ',
            str(score_input.text),
            flags=re.MULTILINE
        )

        # Return new Score.Input with modified text
        return ScoreInput(
            text=modified_text,
            metadata=score_input.metadata,
            results=score_input.results
        )

