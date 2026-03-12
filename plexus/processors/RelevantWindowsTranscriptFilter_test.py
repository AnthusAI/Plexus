import re
import pandas as pd
import unittest

from plexus.processors.RelevantWindowsTranscriptFilter import RelevantWindowsTranscriptFilter
from plexus.scores.Score import Score
from plexus.scores.KeywordClassifier import KeywordClassifier


def _process_text(processor, text):
    """
    Helper function to process text through a processor.

    Args:
        processor: The processor instance
        text: The text to process

    Returns:
        The processed text string
    """
    score_input = Score.Input(text=text, metadata={})
    result = processor.process(score_input)
    return result.text

# Mock classifier for testing purposes
class MockClassifier(Score):
    def predict_validation(self):
        pass
    def register_model(self):
        pass
    def save_model(self):
        pass
    def load_context(self, context):
        pass
    def predict(self, model_input: Score.Input):
        score_value = bool(re.search(r'\brelevant\b', model_input.text, re.IGNORECASE))
        return Score.Result(
            score_name="Test score",
            score=score_value,
            parameters=Score.Parameters(
                scorecard_name="Test scorecard",
                name="Test score"
            ),
            value=score_value
        )

class TestTranscriptFilter(unittest.TestCase):

    def setUp(self):
        self.classifier = MockClassifier(
            scorecard_name="Test scorecard",
            score_name="Test score"
        )

    def test_single_relevant_sentence(self):
        transcript = "Agent: This is an irrelevant sentence.\nCustomer: This is a relevant sentence.\nAgent: This is another irrelevant one."
        transcript_filter = RelevantWindowsTranscriptFilter(classifier=self.classifier,
            prev_count=0,
            next_count=0
        )
        result = _process_text(transcript_filter, transcript)
        self.assertEqual(result, "...\nCustomer: This is a relevant sentence.\n...")

    def test_multiple_relevant_sentences(self):
        transcript = "Agent: Irrelevant.\nCustomer: Relevant sentence one.\nAgent: Still relevant.\nCustomer: Irrelevant again.\nAgent: Relevant sentence two.\nCustomer: The end."
        transcript_filter = RelevantWindowsTranscriptFilter(classifier=self.classifier,
            prev_count=0,
            next_count=0
        )
        result = _process_text(transcript_filter, transcript)
        expected_output = "...\nCustomer: Relevant sentence one.\nAgent: Still relevant.\n...\nAgent: Relevant sentence two.\n..."
        self.assertEqual(result, expected_output)

    def test_context_inclusion(self):
        transcript = "Agent: Start.\nCustomer: Irrelevant.\nAgent: Relevant sentence.\nCustomer: Irrelevant.\nAgent: Irrelevant.\nCustomer: End."
        transcript_filter = RelevantWindowsTranscriptFilter(classifier=self.classifier,
            prev_count=1,
            next_count=1
        )
        result = _process_text(transcript_filter, transcript)
        expected_output = "...\nCustomer: Irrelevant.\nAgent: Relevant sentence.\nCustomer: Irrelevant.\n..."
        self.assertEqual(result, expected_output)

    def test_no_relevant_sentences(self):
        transcript = "Agent: Just an irrelevant sentence.\nCustomer: Another one.\nAgent: And yet another one."
        transcript_filter = RelevantWindowsTranscriptFilter(classifier=self.classifier,
            prev_count=0,
            next_count=0
        )
        result = _process_text(transcript_filter, transcript)
        expected_output = ""
        self.assertEqual(result, expected_output)

    def test_full_transcript_relevant(self):
        transcript = "Agent: Relevant sentence one.\nCustomer: Relevant sentence two.\nAgent: Relevant sentence three."
        transcript_filter = RelevantWindowsTranscriptFilter(classifier=self.classifier,
            prev_count=0,
            next_count=0
        )
        result = _process_text(transcript_filter, transcript)
        expected_output = transcript
        self.assertEqual(result, expected_output)

    def test_gap_insertion(self):
        transcript = "Agent: Relevant.\nCustomer: Irrelevant.\nAgent: Irrelevant.\nCustomer: Relevant.\nAgent: Irrelevant.\nCustomer: Relevant."
        transcript_filter = RelevantWindowsTranscriptFilter(classifier=self.classifier,
            prev_count=0,
            next_count=0
        )
        result = _process_text(transcript_filter, transcript)
        expected_output = "Agent: Relevant.\n...\nCustomer: Relevant.\n...\nCustomer: Relevant."
        self.assertEqual(result, expected_output)

    def test_overlapping_windows(self):
        transcript = "Agent: Start.\nCustomer: Irrelevant.\n3: Relevant sentence one.\nAgent: Irrelevant.\nCustomer: Relevant sentence two.\n3: Irrelevant.\nAgent: End."
        transcript_filter = RelevantWindowsTranscriptFilter(classifier=self.classifier,
            prev_count=1,
            next_count=1
        )
        result = _process_text(transcript_filter, transcript)
        expected_output = "...\nCustomer: Irrelevant.\n3: Relevant sentence one.\nAgent: Irrelevant.\nCustomer: Relevant sentence two.\n3: Irrelevant.\n..."
        self.assertEqual(result, expected_output)

    def test_separate_windows(self):
        transcript =\
"""Agent: Relevant start.
Customer: Irrelevant.
Agent: Irrelevant.
Customer: Irrelevant.
Agent: Relevant middle.
Customer: Irrelevant.
Agent: Irrelevant.
Customer: Irrelevant.
Customer: Relevant end."""
        transcript_filter = RelevantWindowsTranscriptFilter(classifier=self.classifier,
            prev_count=1,
            next_count=1
        )
        result = _process_text(transcript_filter, transcript)
        expected_output =\
"""Agent: Relevant start.
Customer: Irrelevant.
...
Customer: Irrelevant.
Agent: Relevant middle.
Customer: Irrelevant.
...
Customer: Irrelevant.
Customer: Relevant end."""
        self.assertEqual(result, expected_output)

class TestKeywordTranscriptFilter(unittest.TestCase):

    def setUp(self):
        keywords = ["child", "children", "kid", "kids", "dependent", 
                    "dependents", "son", "daughter"]
        parameters = Score.Parameters(
            scorecard_name="Test scorecard",
            name="Test score"
        )
        self.classifier = KeywordClassifier(
            keywords=keywords,
            scorecard_name="Test scorecard",
            score_name="Test score",
            parameters=parameters
        )
        self.transcript_filter = RelevantWindowsTranscriptFilter(
            classifier=self.classifier
        )

    def test_single_keyword_sentence(self):
        transcript = "I have no pets.\nMy child is in school.\nI am self-employed."
        transcript_filter = RelevantWindowsTranscriptFilter(classifier=self.classifier)
        result = _process_text(transcript_filter, transcript)
        expected_output = "I have no pets.\nMy child is in school.\nI am self-employed."
        self.assertEqual(result, expected_output)

    def test_multiple_keywords(self):
        transcript = "My kids play football.\nI work from home.\nMy children are grown up."
        transcript_filter = RelevantWindowsTranscriptFilter(classifier=self.classifier)
        result = _process_text(transcript_filter, transcript)
        expected_output = "My kids play football.\nI work from home.\nMy children are grown up."
        self.assertEqual(result, expected_output)

    def test_no_keywords(self):
        transcript = "I enjoy gardening.\nI work as a designer.\nI like to travel."
        transcript_filter = RelevantWindowsTranscriptFilter(classifier=self.classifier,
            prev_count=0,
            next_count=0
        )
        result = _process_text(transcript_filter, transcript)
        expected_output = ""
        self.assertEqual(result, expected_output)

    def test_keywords_with_context(self):
        transcript = "We have a dog.\nMy kid is a teenager.\nWe recently moved."
        transcript_filter = RelevantWindowsTranscriptFilter(classifier=self.classifier,
            prev_count=1,
            next_count=1
        )
        result = _process_text(transcript_filter, transcript)
        expected_output = "We have a dog.\nMy kid is a teenager.\nWe recently moved."
        self.assertEqual(result, expected_output)

    def test_keywords_with_context_with_narrow_window(self):
        transcript = "We have a dog.\nMy kid is a teenager.\nWe recently moved."
        transcript_filter = RelevantWindowsTranscriptFilter(classifier=self.classifier,
            prev_count=0,
            next_count=0
        )
        result = _process_text(transcript_filter, transcript)
        expected_output = "...\nMy kid is a teenager.\n..."
        self.assertEqual(result, expected_output)

    def test_separated_keywords(self):
        transcript = "My daughter is at college.\nI am a teacher.\nMy son is in high school."
        transcript_filter = RelevantWindowsTranscriptFilter(classifier=self.classifier)
        result = _process_text(transcript_filter, transcript)
        expected_output = "My daughter is at college.\nI am a teacher.\nMy son is in high school."
        self.assertEqual(result, expected_output)

    def test_newlines(self):
        transcript = "Agent: Tell me about your kids?\nCustomer: My daughter is at college. I am a teacher. My son is in high school."
        transcript_filter = RelevantWindowsTranscriptFilter(classifier=self.classifier,
            prev_count=0,
            next_count=0
        )
        result = _process_text(transcript_filter, transcript)
        expected_output = "Agent: Tell me about your kids?\nCustomer: My daughter is at college. I am a teacher. My son is in high school."
        self.assertEqual(result, expected_output)

    def test_missing_newlines(self):
        transcript = "Agent: Tell me about your kids?\nCustomer: Nope, none."
        transcript_filter = RelevantWindowsTranscriptFilter(classifier=self.classifier,
            prev_count=0,
            next_count=0
        )
        result = _process_text(transcript_filter, transcript)
        expected_output = "Agent: Tell me about your kids?\n..."
        self.assertEqual(result, expected_output)

# Run the tests
if __name__ == '__main__':
    unittest.main()