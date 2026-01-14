import re
from plexus.processors.DataframeProcessor import Processor


class FilterCustomerOnlyProcessor(Processor):
    """
    Processor that filters transcript text to include only customer utterances.

    This processor extracts only the portions of a transcript where the customer
    is speaking, removing all agent/representative utterances. It handles various
    speaker label formats (Customer:, Contact:, etc.).

    Note: This processor does NOT remove the speaker identifiers themselves.
    To remove speaker labels like "Customer:", chain this with
    RemoveSpeakerIdentifiersTranscriptFilter.

    Example usage in YAML:
        item:
          processors:
            - class: FilterCustomerOnlyProcessor
            - class: RemoveSpeakerIdentifiersTranscriptFilter
    """

    def process(self, score_input: 'Score.Input') -> 'Score.Input':
        """
        Process the Score.Input by filtering text to customer utterances only.

        Args:
            score_input: Score.Input with text containing transcripts

        Returns:
            Score.Input with text filtered to customer speech only
        """
        from plexus.scores.Score import Score

        # Extract customer-only text
        filtered_text = self._extract_customer_only(score_input.text)

        # Return new Score.Input with filtered text
        return Score.Input(
            text=filtered_text,
            metadata=score_input.metadata,
            results=score_input.results
        )

    def _extract_customer_only(self, text: str) -> str:
        """
        Extract only the customer utterances from transcript text.

        This method handles various speaker label formats and extracts only
        the portions where the customer is speaking.

        If no speaker labels are found, returns the original text (assumes it's all customer speech).

        Args:
            text: Raw transcript text with speaker labels

        Returns:
            String containing only customer utterances concatenated together,
            or the original text if no speaker labels are found
        """
        if not text:
            return ""

        # Check if text contains any speaker labels
        has_labels = bool(re.search(r'(Agent:|Customer:|Contact:|Representative:|Rep:)', text))

        # If no labels found, return original text (assume it's all customer speech)
        if not has_labels:
            return text

        # Add spaces around "Agent:" and "Customer:" (and variants) for consistent splitting
        text = re.sub(r'(?<![\s])(Agent:|Customer:|Contact:|Representative:|Rep:)', r' \1', text)
        text = re.sub(r'(Agent:|Customer:|Contact:|Representative:|Rep:)(?![\s])', r'\1 ', text)

        # Split on Agent/Customer markers
        parts = re.split(r'\s+(Agent:|Customer:|Contact:|Representative:|Rep:)\s+', text)

        # First part might be empty or contain text before any marker
        if parts and not any(marker in parts[0] for marker in ['Agent:', 'Customer:', 'Contact:', 'Representative:', 'Rep:']):
            parts = parts[1:]

        # Process in pairs (marker + text)
        customer_parts = []
        for i in range(0, len(parts), 2):
            if i+1 < len(parts):
                marker = parts[i]
                content = parts[i+1]
                # Check if this is a customer marker (Customer, Contact, etc.)
                if marker in ['Customer:', 'Contact:']:
                    customer_parts.append(content.strip())

        # Join customer parts with a space
        return " ".join(customer_parts)
