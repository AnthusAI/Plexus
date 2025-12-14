import pandas as pd
import nltk.data
import re
from rapidfuzz import fuzz

from .DataframeProcessor import DataframeProcessor
from plexus.scores.Score import Score
from plexus.CustomLogging import logging

class RelevantWindowsTranscriptFilter(DataframeProcessor):
    """
    Filter transcript to extract relevant windows based on keywords or a classifier.

    This processor can work in two modes:
    1. Keyword mode: Provide a list of keywords with optional fuzzy matching
    2. Classifier mode: Provide a Score classifier (legacy mode)

    Parameters:
        keywords (list): List of keywords/phrases to match (alternative to classifier)
        fuzzy_match (bool): Enable fuzzy matching for keywords (default: False)
        fuzzy_threshold (int): Minimum similarity score for fuzzy matching, 0-100 (default: 80)
        case_sensitive (bool): Whether keyword matching is case sensitive (default: False)
        classifier (Score): A Score classifier for determining relevance (legacy)
        prev_count (int): Number of sentences to include before matched sentence (default: 1)
        next_count (int): Number of sentences to include after matched sentence (default: 1)
        window_unit (str): Unit for window size - 'sentences', 'words', or 'characters' (default: 'sentences')
    """
    def __init__(self, **parameters):
        super().__init__(**parameters)

        # Keyword-based matching parameters
        self.keywords = parameters.get("keywords", [])
        self.fuzzy_match = parameters.get("fuzzy_match", False)
        self.fuzzy_threshold = parameters.get("fuzzy_threshold", 80)
        self.case_sensitive = parameters.get("case_sensitive", False)

        # Legacy classifier-based matching
        self.classifier = parameters.get("classifier")

        # Window configuration
        self.prev_count = parameters.get("prev_count", 1)
        self.next_count = parameters.get("next_count", 1)
        self.window_unit = parameters.get("window_unit", "sentences")

        # Validate configuration
        if not self.keywords and not self.classifier:
            raise ValueError("RelevantWindowsTranscriptFilter requires either 'keywords' or 'classifier' parameter")

        if self.keywords and self.classifier:
            logging.warning("Both 'keywords' and 'classifier' provided. Using keywords.")

        if self.window_unit not in ['sentences', 'words', 'characters']:
            raise ValueError(f"window_unit must be 'sentences', 'words', or 'characters', got: {self.window_unit}")

    def is_sentence_relevant(self, sentence: str) -> bool:
        """
        Check if a sentence is relevant based on keywords or classifier.

        Args:
            sentence: The sentence to check

        Returns:
            True if sentence matches keywords or classifier returns True
        """
        if self.keywords:
            return self._matches_keywords(sentence)
        elif self.classifier:
            return self.classifier.predict(model_input=Score.Input(text=sentence)).value
        return False

    def _matches_keywords(self, text: str) -> bool:
        """
        Check if text matches any of the configured keywords.

        Args:
            text: The text to check

        Returns:
            True if any keyword matches
        """
        compare_text = text if self.case_sensitive else text.lower()

        for keyword in self.keywords:
            compare_keyword = keyword if self.case_sensitive else keyword.lower()

            if self.fuzzy_match:
                # Use fuzzy matching with RapidFuzz
                similarity = fuzz.partial_ratio(compare_keyword, compare_text)
                if similarity >= self.fuzzy_threshold:
                    logging.debug(f"Fuzzy match found: '{keyword}' in '{text[:50]}...' (score: {similarity})")
                    return True
            else:
                # Exact substring matching
                if compare_keyword in compare_text:
                    logging.debug(f"Exact match found: '{keyword}' in '{text[:50]}...'")
                    return True

        return False

    def process(self, dataframe: pd.DataFrame) -> pd.DataFrame:
        # Get a sample for before/after display
        random_row_index = dataframe.sample(n=1).index[0] if len(dataframe) > 0 else None
        if random_row_index is not None:
            original_text = dataframe.at[random_row_index, 'text']
            truncated_original = (original_text[:512] + '...') if len(original_text) > 512 else original_text
            self.before_summary = truncated_original

        def filter_text(text):
            sentences = text.split('\n')
            relevance_flags = [self.is_sentence_relevant(sentence) for sentence in sentences]
            include_flags = self.compute_inclusion_flags(relevance_flags)

            filtered_text = []
            for i in range(len(sentences)):
                if include_flags[i]:
                    filtered_text.append(sentences[i])
                elif self.should_insert_ellipsis(i, include_flags, sentences):
                    filtered_text.append("...")

            combined_text = self.combine_consecutive_ellipses(filtered_text)
            result = '\n'.join(combined_text).strip()

            if result == "...":
                return ""

            logging.debug(f"Filtered text: {result}")
            return result

        dataframe['text'] = dataframe['text'].apply(filter_text)

        # Get sample for after display
        if random_row_index is not None:
            modified_text = dataframe.at[random_row_index, 'text']
            truncated_modified = (modified_text[:512] + '...') if len(modified_text) > 512 else modified_text
            self.after_summary = truncated_modified

        self.display_summary()
        return dataframe

    def compute_inclusion_flags(self, relevance_flags):
        include_flags = [False] * len(relevance_flags)
        for i, is_relevant in enumerate(relevance_flags):
            if is_relevant:
                start_index = max(i - self.prev_count, 0)
                end_index = min(i + self.next_count + 1, len(relevance_flags))
                for j in range(start_index, end_index):
                    include_flags[j] = True
        return include_flags

    def should_insert_ellipsis(self, index, include_flags, sentences):
        # Insert ellipsis if the current sentence is not included,
        # and either the previous or the next sentence is included.
        prev_included = index > 0 and include_flags[index - 1]
        next_included = index < len(include_flags) - 1 and include_flags[index + 1]
        return not include_flags[index] and (prev_included or next_included)

    def combine_consecutive_ellipses(self, filtered_text):
        combined_text = []
        for sentence in filtered_text:
            if sentence == "..." and combined_text and combined_text[-1] == "...":
                continue
            combined_text.append(sentence)
        return combined_text