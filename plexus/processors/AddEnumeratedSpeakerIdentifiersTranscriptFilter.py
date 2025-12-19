import re
import pandas as pd
from plexus.processors.DataframeProcessor import DataframeProcessor

class AddEnumeratedSpeakerIdentifiersTranscriptFilter(DataframeProcessor):
    """
    Replace speaker identifiers with enumerated labels (Speaker A, Speaker B, etc.).

    This processor does a two-pass operation:
    1. First pass: Identify all unique speaker identifiers in the order they appear
    2. Second pass: Replace each speaker identifier with Speaker A, Speaker B, etc.

    Example:
        Before: "Agent: Hello. Customer: Hi. Agent: How are you?"
        After: "Speaker A: Hello. Speaker B: Hi. Speaker A: How are you?"
    """

    def process(self, dataframe: pd.DataFrame) -> pd.DataFrame:
        random_row_index = dataframe.sample(n=1).index[0] if len(dataframe) > 0 else None

        if random_row_index is not None:
            original_transcript = dataframe.at[random_row_index, 'text']
            truncated_original_transcript = (original_transcript[:512] + '...') if len(original_transcript) > 512 else original_transcript
            self.before_summary = truncated_original_transcript

        dataframe['text'] = dataframe['text'].apply(
            lambda text: self.enumerate_speakers(text)
        )

        if random_row_index is not None:
            modified_transcript = dataframe.at[random_row_index, 'text']
            truncated_modified_transcript = (modified_transcript[:512] + '...') if len(modified_transcript) > 512 else modified_transcript
            self.after_summary = truncated_modified_transcript

        self.display_summary()
        return dataframe

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
