import re
from plexus.processors.DataframeProcessor import Processor


class AddEnumeratedSpeakerIdentifiersTranscriptFilter(Processor):
    """
    Replace speaker identifiers with enumerated labels (Speaker A, Speaker B, etc.).

    This processor does a two-pass operation:
    1. First pass: Identify all unique speaker identifiers in the order they appear
    2. Second pass: Replace each speaker identifier with Speaker A, Speaker B, etc.

    Example:
        Before: "Agent: Hello. Customer: Hi. Agent: How are you?"
        After: "Speaker A: Hello. Speaker B: Hi. Speaker A: How are you?"
    """

    def process(self, score_input: 'Score.Input') -> 'Score.Input':
        """
        Process the Score.Input by enumerating speaker identifiers.

        Args:
            score_input: Score.Input with text

        Returns:
            Score.Input with enumerated speaker identifiers
        """
        from plexus.scores.Score import Score

        enumerated_text = self.enumerate_speakers(score_input.text)

        # Return new Score.Input with enumerated text
        return Score.Input(
            text=enumerated_text,
            metadata=score_input.metadata,
            results=score_input.results
        )

    def enumerate_speakers(self, text: str) -> str:
        """
        Replace speaker identifiers with enumerated labels.

        Args:
            text: Input text with speaker identifiers

        Returns:
            Text with speakers replaced by Speaker A, Speaker B, etc.
        """
        if not text:
            return text

        # Pattern to match speaker identifiers: word followed by colon and space
        # Matches at start of string, after newline, or after period+space
        speaker_pattern = r'(?:^|(?<=\n)|(?<=\. ))(\w+):\s*'

        # First pass: Find all unique speakers in order of first appearance
        speakers_found = []
        for match in re.finditer(speaker_pattern, text):
            speaker = match.group(1)
            if speaker not in speakers_found:
                speakers_found.append(speaker)

        # Create mapping from original speakers to enumerated labels (A, B, C, etc.)
        speaker_mapping = {}
        for i, speaker in enumerate(speakers_found):
            # Use letters A, B, C, ... Z, then AA, AB, etc. if needed
            label = self._get_speaker_label(i)
            speaker_mapping[speaker] = label

        # Second pass: Replace speakers with enumerated labels
        def replace_speaker(match):
            speaker = match.group(1)
            enumerated_label = speaker_mapping.get(speaker, speaker)
            # Get the full match to check what preceded it
            full_match = match.group(0)
            # Preserve any newline or period+space that came before
            if full_match.startswith('\n'):
                return f"\nSpeaker {enumerated_label}: "
            elif full_match.startswith('. '):
                return f". Speaker {enumerated_label}: "
            else:
                return f"Speaker {enumerated_label}: "

        result = re.sub(speaker_pattern, replace_speaker, text)

        return result

    def _get_speaker_label(self, index: int) -> str:
        """
        Get speaker label for a given index (A, B, C, ..., Z, AA, AB, etc.)

        Args:
            index: Zero-based index of the speaker

        Returns:
            Letter label (A, B, C, etc.)
        """
        if index < 26:
            return chr(65 + index)  # A-Z
        else:
            # For indices >= 26, use AA, AB, AC, etc.
            first_letter = chr(65 + (index // 26) - 1)
            second_letter = chr(65 + (index % 26))
            return f"{first_letter}{second_letter}"
