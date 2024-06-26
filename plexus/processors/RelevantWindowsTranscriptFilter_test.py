import re
import unittest

from plexus.processors.RelevantWindowsTranscriptFilter import RelevantWindowsTranscriptFilter
from plexus.scores.Score import Score
from plexus.scores.KeywordClassifier import KeywordClassifier

# Mock classifier for testing purposes
class MockClassifier(Score):
    def is_relevant(self, text):
        # Use word boundaries to ensure 'relevant' is a whole word
        return bool(re.search(r'\brelevant\b', text, re.IGNORECASE))

class TestTranscriptFilter(unittest.TestCase):

    def setUp(self):
        self.classifier = MockClassifier()
        self.transcript_filter = RelevantWindowsTranscriptFilter(self.classifier)

    def test_single_relevant_sentence(self):
        transcript = "Agent: This is an irrelevant sentence.\nCustomer: This is a relevant sentence.\nAgent: This is another irrelevant one."
        expected_output = "...\nCustomer: This is a relevant sentence.\n..."
        result = self.transcript_filter.process(transcript=transcript, prev_count=0, next_count=0)
        self.assertEqual(result, expected_output)

    def test_multiple_relevant_sentences(self):
        transcript = "Agent: Irrelevant.\nCustomer: Relevant sentence one.\nAgent: Still relevant.\nCustomer: Irrelevant again.\nAgent: Relevant sentence two.\nCustomer: The end."
        expected_output = "...\nCustomer: Relevant sentence one.\nAgent: Still relevant.\n...\nAgent: Relevant sentence two.\n..."
        result = self.transcript_filter.process(transcript=transcript, prev_count=0, next_count=0)
        self.assertEqual(result, expected_output)

    def test_context_inclusion(self):
        transcript = "Agent: Start.\nCustomer: Irrelevant.\nAgent: Relevant sentence.\nCustomer: Irrelevant.\nAgent: Irrelevant.\nCustomer: End."
        expected_output = "...\nCustomer: Irrelevant.\nAgent: Relevant sentence.\nCustomer: Irrelevant.\n..."
        result = self.transcript_filter.process(transcript=transcript, prev_count=1, next_count=1)
        self.assertEqual(result, expected_output)

    def test_no_relevant_sentences(self):
        transcript = "Agent: Just an irrelevant sentence.\nCustomer: Another one.\nAgent: And yet another one."
        expected_output = ""
        result = self.transcript_filter.process(transcript=transcript)
        self.assertEqual(result, expected_output)

    def test_full_transcript_relevant(self):
        transcript = "Agent: Relevant sentence one.\nCustomer: Relevant sentence two.\nAgent: Relevant sentence three."
        expected_output = transcript
        result = self.transcript_filter.process(transcript=transcript)
        self.assertEqual(result, expected_output)

    def test_gap_insertion(self):
        transcript = "Agent: Relevant.\nCustomer: Irrelevant.\nAgent: Irrelevant.\nCustomer: Relevant.\nAgent: Irrelevant.\nCustomer: Relevant."
        expected_output = "Agent: Relevant.\n...\nCustomer: Relevant.\n...\nCustomer: Relevant."
        result = self.transcript_filter.process(transcript=transcript, prev_count=0, next_count=0)
        self.assertEqual(result, expected_output)

    def test_overlapping_windows(self):
        transcript = "Agent: Start.\nCustomer: Irrelevant.\n3: Relevant sentence one.\nAgent: Irrelevant.\nCustomer: Relevant sentence two.\n3: Irrelevant.\nAgent: End."
        expected_output = "...\nCustomer: Irrelevant.\n3: Relevant sentence one.\nAgent: Irrelevant.\nCustomer: Relevant sentence two.\n3: Irrelevant.\n..."
        result = self.transcript_filter.process(transcript=transcript, prev_count=1, next_count=1)
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
        result = self.transcript_filter.process(transcript=transcript, prev_count=1, next_count=1)
        self.assertEqual(result, expected_output)

class TestKeywordTranscriptFilter(unittest.TestCase):

    def setUp(self):
        keywords = ["child", "children", "kid", "kids", "dependent", "dependents", "son", "daughter"]
        self.classifier = KeywordClassifier(keywords)
        self.transcript_filter = RelevantWindowsTranscriptFilter(self.classifier)

    def test_single_keyword_sentence(self):
        transcript = "I have no pets.\nMy child is in school.\nI am self-employed."
        expected_output = "I have no pets.\nMy child is in school.\nI am self-employed."
        result = self.transcript_filter.process(transcript=transcript)
        self.assertEqual(result, expected_output)

    def test_multiple_keywords(self):
        transcript = "My kids play football.\nI work from home.\nMy children are grown up."
        expected_output = "My kids play football.\nI work from home.\nMy children are grown up."
        result = self.transcript_filter.process(transcript=transcript)
        self.assertEqual(result, expected_output)

    def test_no_keywords(self):
        transcript = "I enjoy gardening.\nI work as a designer.\nI like to travel."
        expected_output = ""
        result = self.transcript_filter.process(transcript=transcript)
        self.assertEqual(result, expected_output)

    def test_keywords_with_context(self):
        transcript = "We have a dog.\nMy kid is a teenager.\nWe recently moved."
        expected_output = "We have a dog.\nMy kid is a teenager.\nWe recently moved."
        result = self.transcript_filter.process(transcript=transcript, prev_count=1, next_count=1)
        self.assertEqual(result, expected_output)

    def test_keywords_with_context_with_narrow_window(self):
        transcript = "We have a dog.\nMy kid is a teenager.\nWe recently moved."
        expected_output = "...\nMy kid is a teenager.\n..."
        result = self.transcript_filter.process(transcript=transcript, prev_count=0, next_count=0)
        self.assertEqual(result, expected_output)

    def test_separated_keywords(self):
        transcript = "My daughter is at college.\nI am a teacher.\nMy son is in high school."
        expected_output = "My daughter is at college.\nI am a teacher.\nMy son is in high school."
        result = self.transcript_filter.process(transcript=transcript)
        self.assertEqual(result, expected_output)

    def test_newlines(self):
        transcript = "Agent: Tell me about your kids?\nCustomer: My daughter is at college. I am a teacher. My son is in high school."
        expected_output = "Agent: Tell me about your kids?\nCustomer: My daughter is at college. I am a teacher. My son is in high school."
        result = self.transcript_filter.process(transcript=transcript)
        self.assertEqual(result, expected_output)

    def test_missing_newlines(self):
        transcript = "Agent: Tell me about your kids?\nCustomer: Nope, none."
        expected_output = "Agent: Tell me about your kids?\n..."
        result = self.transcript_filter.process(transcript=transcript, prev_count=0, next_count=0)
        self.assertEqual(result, expected_output)

# Run the tests
if __name__ == '__main__':
    unittest.main()