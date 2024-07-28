import pandas as pd
import nltk.data

from .DataframeProcessor import DataframeProcessor
from plexus.scores.Score import Score
from plexus.CustomLogging import logging

class RelevantWindowsTranscriptFilter(DataframeProcessor):
    def __init__(self, **parameters):
        super().__init__(**parameters)
        self.classifier = parameters.get("classifier")
        self.prev_count = parameters.get("prev_count", 1)
        self.next_count = parameters.get("next_count", 1)

    def process(self, dataframe: pd.DataFrame) -> pd.DataFrame:
        def filter_text(text):
            sentences = text.split('\n')
            relevance_flags = [
                self.classifier.predict(
                    model_input = Score.Input(text=sentence)
                ).value for sentence in sentences
            ]
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