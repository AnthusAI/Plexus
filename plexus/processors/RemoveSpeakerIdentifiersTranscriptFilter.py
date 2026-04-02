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

    SPEAKER_LABEL_PATTERN = re.compile(
        r'(?:(?<=^)|(?<=\s))'
        r'(?:'
        r'speaker(?:\s*[A-Za-z0-9_-]+)?|'
        r'unknown\s+speaker|'
        r'agent|customer|contact|representative|rep'
        r')\s*:\s*',
        flags=re.IGNORECASE | re.MULTILINE,
    )
    GENERIC_SPEAKER_LABEL_PATTERN = re.compile(
        r'(?:(?<=^)|(?<=\n)|(?<=\.\s))'
        r'[A-Za-z][A-Za-z0-9_-]{1,31}\s*:\s*',
        flags=re.MULTILINE,
    )

    def process(self, score_input: 'Score.Input') -> 'Score.Input':
        """
        Process the Score.Input by removing speaker identifiers.

        Args:
            score_input: Score.Input with text containing speaker labels

        Returns:
            Score.Input with speaker labels removed
        """
        from plexus.scores.Score import Score

        # Remove speaker identifiers, including multi-token forms like "Speaker 0:"
        filtered_text = self.SPEAKER_LABEL_PATTERN.sub('', str(score_input.text))
        filtered_text = self.GENERIC_SPEAKER_LABEL_PATTERN.sub('', filtered_text)

        # Normalize spacing left behind by label removal.
        filtered_text = re.sub(r'[ \t]{2,}', ' ', filtered_text)
        filtered_text = re.sub(r'[ \t]*\n[ \t]*', '\n', filtered_text)
        filtered_text = filtered_text.strip()

        # Return new Score.Input with filtered text
        return Score.Input(
            text=filtered_text,
            metadata=score_input.metadata,
            results=score_input.results
        )
