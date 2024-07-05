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
        def filter_transcript(transcript):
            sentences = transcript.split('\n')
            relevance_flags = [
                self.classifier.predict(
                    model_input = Score.ModelInput(transcript=sentence)
                ).classification for sentence in sentences
            ]
            include_flags = self.compute_inclusion_flags(relevance_flags)

            filtered_transcript = []
            for i in range(len(sentences)):
                if include_flags[i]:
                    filtered_transcript.append(sentences[i])
                elif self.should_insert_ellipsis(i, include_flags, sentences):
                    filtered_transcript.append("...")

            combined_transcript = self.combine_consecutive_ellipses(filtered_transcript)
            result = '\n'.join(combined_transcript).strip()

            if result == "...":
                return ""

            logging.debug(f"Filtered transcript: {result}")
            return result

        dataframe["Transcription"] = dataframe["Transcription"].apply(filter_transcript)
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

    def combine_consecutive_ellipses(self, filtered_transcript):
        combined_transcript = []
        for sentence in filtered_transcript:
            if sentence == "..." and combined_transcript and combined_transcript[-1] == "...":
                continue
            combined_transcript.append(sentence)
        return combined_transcript