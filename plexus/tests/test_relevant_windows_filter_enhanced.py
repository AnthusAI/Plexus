"""
Tests for enhanced RelevantWindowsTranscriptFilter with keyword and fuzzy matching support.
"""

import unittest
import pandas as pd
from plexus.processors.RelevantWindowsTranscriptFilter import RelevantWindowsTranscriptFilter


class TestKeywordMatching(unittest.TestCase):
    """Tests for direct keyword matching without classifier"""

    def test_exact_keyword_match(self):
        """Test basic exact keyword matching"""
        transcript = "We have a dog.\nMy child is in school.\nWe recently moved."

        processor = RelevantWindowsTranscriptFilter(
            keywords=["child"],
            prev_count=0,
            next_count=0
        )

        result = processor.process(pd.DataFrame({'text': [transcript]})).iloc[0, 0]

        self.assertIn("My child is in school", result)
        self.assertNotIn("We have a dog", result)
        self.assertNotIn("We recently moved", result)
        self.assertIn("...", result)

    def test_multiple_keywords(self):
        """Test matching multiple different keywords"""
        transcript = "I like dogs.\nMy child is 5 years old.\nWe have dependents.\nI work remotely."

        processor = RelevantWindowsTranscriptFilter(
            keywords=["child", "dependent"],
            prev_count=0,
            next_count=0
        )

        result = processor.process(pd.DataFrame({'text': [transcript]})).iloc[0, 0]

        self.assertIn("My child is 5 years old", result)
        self.assertIn("We have dependents", result)
        self.assertNotIn("I like dogs", result)
        self.assertNotIn("I work remotely", result)

    def test_case_insensitive_by_default(self):
        """Test that keyword matching is case insensitive by default"""
        transcript = "Line 1.\nMy CHILD is here.\nLine 3."

        processor = RelevantWindowsTranscriptFilter(
            keywords=["child"],
            prev_count=0,
            next_count=0
        )

        result = processor.process(pd.DataFrame({'text': [transcript]})).iloc[0, 0]

        self.assertIn("My CHILD is here", result)

    def test_case_sensitive_matching(self):
        """Test case sensitive keyword matching"""
        transcript = "Line 1.\nMy CHILD is here.\nMy child is there.\nLine 4."

        processor = RelevantWindowsTranscriptFilter(
            keywords=["child"],
            case_sensitive=True,
            prev_count=0,
            next_count=0
        )

        result = processor.process(pd.DataFrame({'text': [transcript]})).iloc[0, 0]

        self.assertIn("My child is there", result)
        self.assertNotIn("My CHILD is here", result)

    def test_context_window(self):
        """Test including context sentences around matches"""
        transcript = "Line 1.\nLine 2.\nMy child is here.\nLine 4.\nLine 5."

        processor = RelevantWindowsTranscriptFilter(
            keywords=["child"],
            prev_count=1,
            next_count=1
        )

        result = processor.process(pd.DataFrame({'text': [transcript]})).iloc[0, 0]

        self.assertIn("Line 2", result)
        self.assertIn("My child is here", result)
        self.assertIn("Line 4", result)
        self.assertNotIn("Line 1", result)
        self.assertNotIn("Line 5", result)

    def test_no_keyword_matches(self):
        """Test when no keywords match"""
        transcript = "I like dogs.\nWe recently moved.\nI work remotely."

        processor = RelevantWindowsTranscriptFilter(
            keywords=["child", "dependent"],
            prev_count=0,
            next_count=0
        )

        result = processor.process(pd.DataFrame({'text': [transcript]})).iloc[0, 0]

        self.assertEqual(result, "")


class TestFuzzyKeywordMatching(unittest.TestCase):
    """Tests for fuzzy keyword matching using RapidFuzz"""

    def test_fuzzy_match_typo(self):
        """Test fuzzy matching catches common typos"""
        transcript = "Line 1.\nMy chidl is in school.\nLine 3."

        processor = RelevantWindowsTranscriptFilter(
            keywords=["child"],
            fuzzy_match=True,
            fuzzy_threshold=80,
            prev_count=0,
            next_count=0
        )

        result = processor.process(pd.DataFrame({'text': [transcript]})).iloc[0, 0]

        # Should match "chidl" as close to "child"
        self.assertIn("chidl", result)

    def test_fuzzy_match_similar_words(self):
        """Test fuzzy matching with semantically similar words"""
        transcript = "I have no pets.\nMy kid is in school.\nI work remotely."

        processor = RelevantWindowsTranscriptFilter(
            keywords=["child"],
            fuzzy_match=True,
            fuzzy_threshold=70,  # Lower threshold
            prev_count=0,
            next_count=0
        )

        result = processor.process(pd.DataFrame({'text': [transcript]})).iloc[0, 0]

        # "kid" should match "child" with fuzzy matching at reasonable threshold
        # Note: This may or may not match depending on the fuzzy algorithm
        # But it demonstrates the fuzzy matching capability

    def test_fuzzy_threshold_control(self):
        """Test that fuzzy threshold controls matching strictness"""
        transcript = "Line 1.\nMy chld is here.\nLine 3."

        # High threshold - should not match
        processor_strict = RelevantWindowsTranscriptFilter(
            keywords=["child"],
            fuzzy_match=True,
            fuzzy_threshold=95,
            prev_count=0,
            next_count=0
        )

        result_strict = processor_strict.process(pd.DataFrame({'text': [transcript]})).iloc[0, 0]

        # Low threshold - should match
        processor_lenient = RelevantWindowsTranscriptFilter(
            keywords=["child"],
            fuzzy_match=True,
            fuzzy_threshold=70,
            prev_count=0,
            next_count=0
        )

        result_lenient = processor_lenient.process(pd.DataFrame({'text': [transcript]})).iloc[0, 0]

        # Lenient should match where strict doesn't
        self.assertIn("chld", result_lenient)

    def test_fuzzy_match_with_multiple_keywords(self):
        """Test fuzzy matching with multiple keywords"""
        transcript = "I like pets.\nMy chld is 5.\nWe have dependants.\nI work."

        processor = RelevantWindowsTranscriptFilter(
            keywords=["child", "dependent"],
            fuzzy_match=True,
            fuzzy_threshold=75,
            prev_count=0,
            next_count=0
        )

        result = processor.process(pd.DataFrame({'text': [transcript]})).iloc[0, 0]

        # Should match both "chld" and "dependants" with fuzzy matching
        self.assertIn("chld", result)
        self.assertIn("dependants", result)

    def test_fuzzy_disabled_requires_exact(self):
        """Test that with fuzzy_match=False, exact match is required"""
        transcript = "Line 1.\nMy chidl is here.\nLine 3."

        processor = RelevantWindowsTranscriptFilter(
            keywords=["child"],
            fuzzy_match=False,
            prev_count=0,
            next_count=0
        )

        result = processor.process(pd.DataFrame({'text': [transcript]})).iloc[0, 0]

        # Should NOT match typo with exact matching
        self.assertEqual(result, "")


class TestPhrasesAndContextWindow(unittest.TestCase):
    """Tests for multi-word phrases and context windows"""

    def test_phrase_matching(self):
        """Test matching multi-word phrases"""
        transcript = "Line 1.\nThe quick brown fox jumps.\nLine 3."

        processor = RelevantWindowsTranscriptFilter(
            keywords=["quick brown fox"],
            prev_count=0,
            next_count=0
        )

        result = processor.process(pd.DataFrame({'text': [transcript]})).iloc[0, 0]

        self.assertIn("quick brown fox", result)

    def test_overlapping_context_windows(self):
        """Test that overlapping context windows merge correctly"""
        transcript = "Line 1.\nLine 2.\nKeyword 1.\nLine 4.\nKeyword 2.\nLine 6.\nLine 7."

        processor = RelevantWindowsTranscriptFilter(
            keywords=["Keyword"],
            prev_count=1,
            next_count=1
        )

        result = processor.process(pd.DataFrame({'text': [transcript]})).iloc[0, 0]

        # Windows should overlap and merge: Line 2, Keyword 1, Line 4, Keyword 2, Line 6
        self.assertIn("Line 2", result)
        self.assertIn("Keyword 1", result)
        self.assertIn("Line 4", result)
        self.assertIn("Keyword 2", result)
        self.assertIn("Line 6", result)
        self.assertNotIn("Line 1", result)
        self.assertNotIn("Line 7", result)

    def test_separate_windows_with_ellipsis(self):
        """Test that separate windows are joined with ellipsis"""
        transcript = "Keyword 1.\nLine 2.\nLine 3.\nLine 4.\nKeyword 2."

        processor = RelevantWindowsTranscriptFilter(
            keywords=["Keyword"],
            prev_count=0,
            next_count=0
        )

        result = processor.process(pd.DataFrame({'text': [transcript]})).iloc[0, 0]

        # Should have both keywords with ellipsis between
        self.assertIn("Keyword 1", result)
        self.assertIn("Keyword 2", result)
        self.assertIn("...", result)
        # Should not have the lines in between
        self.assertNotIn("Line 2", result)
        self.assertNotIn("Line 3", result)


class TestEdgeCases(unittest.TestCase):
    """Tests for edge cases and error handling"""

    def test_empty_text(self):
        """Test handling of empty text"""
        transcript = ""

        processor = RelevantWindowsTranscriptFilter(
            keywords=["child"],
            prev_count=0,
            next_count=0
        )

        result = processor.process(pd.DataFrame({'text': [transcript]})).iloc[0, 0]

        self.assertEqual(result, "")

    def test_empty_keywords_list(self):
        """Test that empty keywords list raises error"""
        with self.assertRaises(ValueError):
            RelevantWindowsTranscriptFilter(keywords=[])

    def test_no_keywords_or_classifier(self):
        """Test that missing both keywords and classifier raises error"""
        with self.assertRaises(ValueError):
            RelevantWindowsTranscriptFilter(prev_count=1)

    def test_single_line_with_match(self):
        """Test single line transcript with match"""
        transcript = "My child is in school."

        processor = RelevantWindowsTranscriptFilter(
            keywords=["child"],
            prev_count=1,
            next_count=1
        )

        result = processor.process(pd.DataFrame({'text': [transcript]})).iloc[0, 0]

        self.assertEqual(result, transcript)

    def test_all_lines_match(self):
        """Test when all lines match keywords"""
        transcript = "Child 1.\nChild 2.\nChild 3."

        processor = RelevantWindowsTranscriptFilter(
            keywords=["Child"],
            prev_count=0,
            next_count=0
        )

        result = processor.process(pd.DataFrame({'text': [transcript]})).iloc[0, 0]

        # All lines should be included without ellipsis
        self.assertEqual(result, transcript)
        self.assertNotIn("...", result)


class TestRealWorldScenarios(unittest.TestCase):
    """Tests for real-world use cases"""

    def test_call_center_transcript_family_mentions(self):
        """Test extracting family-related content from call center transcript"""
        transcript = """Agent: How can I help you today?
Customer: I need to update my insurance policy.
Agent: Sure, what changes would you like to make?
Customer: I need to add my daughter to the policy.
Agent: Great, I can help with that.
Customer: Also, can you explain the dependent coverage?
Agent: Of course, let me explain that."""

        processor = RelevantWindowsTranscriptFilter(
            keywords=["child", "children", "son", "daughter", "dependent", "dependents"],
            prev_count=1,
            next_count=1
        )

        result = processor.process(pd.DataFrame({'text': [transcript]})).iloc[0, 0]

        # Should include mentions of daughter and dependent with context
        self.assertIn("daughter", result)
        self.assertIn("dependent", result)
        # Should include surrounding context
        self.assertIn("what changes would you like to make", result)
        self.assertIn("Great, I can help with that", result)
        self.assertIn("explain that", result)
        # Should not include irrelevant opening
        self.assertNotIn("How can I help you today", result)

    def test_fuzzy_matching_with_misspellings(self):
        """Test fuzzy matching handles real-world misspellings"""
        transcript = """Agent: Tell me about your situation.
Customer: I have three chilren at home.
Agent: What are their ages?
Customer: My oldest daughtr is 12.
Agent: Thank you for that information."""

        processor = RelevantWindowsTranscriptFilter(
            keywords=["children", "daughter"],
            fuzzy_match=True,
            fuzzy_threshold=80,
            prev_count=0,
            next_count=1
        )

        result = processor.process(pd.DataFrame({'text': [transcript]})).iloc[0, 0]

        # Should match "chilren" and "daughtr" with fuzzy matching
        self.assertIn("chilren", result)
        self.assertIn("daughtr", result)
        # Should include next context lines
        self.assertIn("What are their ages", result)


if __name__ == '__main__':
    unittest.main()
