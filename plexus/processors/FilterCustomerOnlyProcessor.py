import re
import pandas as pd
from plexus.processors.DataframeProcessor import DataframeProcessor

class FilterCustomerOnlyProcessor(DataframeProcessor):
    """
    Processor that filters transcript text to include only customer utterances.
    
    This processor extracts only the portions of a transcript where the customer
    is speaking, removing all agent/representative utterances. It handles various
    speaker label formats (Customer:, Contact:, etc.).
    
    Note: This processor does NOT remove the speaker identifiers themselves.
    To remove speaker labels like "Customer:", chain this with 
    RemoveSpeakerIdentifiersTranscriptFilter.
    
    Example usage in YAML:
        data:
          processors:
            - class: FilterCustomerOnlyProcessor
            - class: RemoveSpeakerIdentifiersTranscriptFilter
    """

    def process(self, dataframe: pd.DataFrame) -> pd.DataFrame:
        """
        Process the dataframe by filtering text to customer utterances only.
        
        Args:
            dataframe: DataFrame with 'text' column containing transcripts
            
        Returns:
            DataFrame with 'text' column filtered to customer speech only
        """
        # Sample a random row for before/after comparison
        if len(dataframe) > 0:
            random_row_index = dataframe.sample(n=1).index[0]
            original_transcript = dataframe.at[random_row_index, 'text']
            # Handle NaN/None values
            if pd.isna(original_transcript) or original_transcript is None:
                truncated_original_transcript = ""
            else:
                truncated_original_transcript = (original_transcript[:512] + '...') if len(original_transcript) > 512 else original_transcript
        else:
            truncated_original_transcript = ""

        # Apply customer-only filter to all rows
        dataframe['text'] = dataframe['text'].apply(self._extract_customer_only)

        # Get modified transcript for comparison
        if len(dataframe) > 0:
            modified_transcript = dataframe.at[random_row_index, 'text']
            # Handle NaN/None values
            if pd.isna(modified_transcript) or modified_transcript is None:
                truncated_modified_transcript = ""
            else:
                truncated_modified_transcript = (modified_transcript[:512] + '...') if len(modified_transcript) > 512 else modified_transcript
        else:
            truncated_modified_transcript = ""

        self.before_summary = truncated_original_transcript
        self.after_summary = truncated_modified_transcript

        self.display_summary()
        return dataframe

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
        if pd.isna(text) or not text:
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

