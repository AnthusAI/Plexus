import nltk.data

from plexus.CustomLogging import logging

class TranscriptFilter:
    def __init__(self, classifier):
        self.classifier = classifier

    def compute_relevant_windows(self, transcript, prev_count=1, next_count=1):
        sentences = transcript.split('\n')
        relevance_flags = [self.classifier.is_relevant(sentence) for sentence in sentences]
        include_flags = self.compute_inclusion_flags(relevance_flags, prev_count, next_count)

        # Create the filtered transcript with ellipses, preserving newline characters
        filtered_transcript = []
        for i in range(len(sentences)):
            if include_flags[i]:
                filtered_transcript.append(sentences[i])
            elif self.should_insert_ellipsis(i, include_flags, sentences):
                filtered_transcript.append("...")

        # Combine consecutive ellipses into one
        combined_transcript = self.combine_consecutive_ellipses(filtered_transcript)

        # Join sentences with newlines
        result = '\n'.join(combined_transcript).strip()

        # Special case: if the result is only ellipses, return an empty string
        if result == "...":
            return ""

        logging.debug(f"Filtered transcript: {result}")

        return result

    def compute_inclusion_flags(self, relevance_flags, prev_count, next_count):
        include_flags = [False] * len(relevance_flags)
        for i, is_relevant in enumerate(relevance_flags):
            if is_relevant:
                start_index = max(i - prev_count, 0)
                end_index = min(i + next_count + 1, len(relevance_flags))
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