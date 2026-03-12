"""
Tests for AddEnumeratedSpeakerIdentifiersTranscriptFilter processor.
"""

import unittest
from plexus.scores.Score import Score


class TestEnumeratedSpeakerProcessor(unittest.TestCase):
    """Tests for AddEnumeratedSpeakerIdentifiersTranscriptFilter"""

    def test_enumerate_two_speakers(self):
        """Test basic enumeration with two speakers"""
        text = "Agent: Hello. Customer: Hi there. Agent: How can I help?"

        processors_config = [
            {'class': 'AddEnumeratedSpeakerIdentifiersTranscriptFilter'}
        ]

        result = Score.apply_processors_to_text(text, processors_config)

        # Should have Speaker A and Speaker B
        self.assertIn("Speaker A:", result)
        self.assertIn("Speaker B:", result)

        # Should not have original speaker names
        self.assertNotIn("Agent:", result)
        self.assertNotIn("Customer:", result)

        # Content should be preserved
        self.assertIn("Hello", result)
        self.assertIn("Hi there", result)
        self.assertIn("How can I help", result)

    def test_enumerate_three_speakers(self):
        """Test enumeration with three speakers"""
        text = "Agent: Hello. Customer: Hi. Supervisor: Good morning. Agent: Let me help."

        processors_config = [
            {'class': 'AddEnumeratedSpeakerIdentifiersTranscriptFilter'}
        ]

        result = Score.apply_processors_to_text(text, processors_config)

        # Should have Speaker A, B, and C
        self.assertIn("Speaker A:", result)
        self.assertIn("Speaker B:", result)
        self.assertIn("Speaker C:", result)

        # Should not have original speaker names
        self.assertNotIn("Agent:", result)
        self.assertNotIn("Customer:", result)
        self.assertNotIn("Supervisor:", result)

    def test_enumerate_maintains_speaker_consistency(self):
        """Test that same speaker always gets same label"""
        text = "Agent: First message. Customer: Response. Agent: Second message. Customer: Another response."

        processors_config = [
            {'class': 'AddEnumeratedSpeakerIdentifiersTranscriptFilter'}
        ]

        result = Score.apply_processors_to_text(text, processors_config)

        # Split by lines and check consistency
        lines = result.split('. ')

        # Agent should always be Speaker A
        agent_lines = [line for line in lines if 'First message' in line or 'Second message' in line]
        for line in agent_lines:
            self.assertIn("Speaker A:", line)

        # Customer should always be Speaker B
        customer_lines = [line for line in lines if 'Response' in line or 'Another response' in line]
        for line in customer_lines:
            self.assertIn("Speaker B:", line)

    def test_enumerate_with_multiline_text(self):
        """Test enumeration with multiline transcript"""
        text = """Agent: Hello, how can I help you?
Customer: I need assistance with my account.
Agent: Sure, let me check that for you.
Customer: Thank you."""

        processors_config = [
            {'class': 'AddEnumeratedSpeakerIdentifiersTranscriptFilter'}
        ]

        result = Score.apply_processors_to_text(text, processors_config)

        # Should have Speaker A and B
        self.assertIn("Speaker A:", result)
        self.assertIn("Speaker B:", result)

        # Original labels should be gone
        self.assertNotIn("Agent:", result)
        self.assertNotIn("Customer:", result)

        # Content preserved
        self.assertIn("Hello", result)
        self.assertIn("assistance", result)

    def test_enumerate_with_various_speaker_formats(self):
        """Test enumeration with different speaker label formats"""
        text = "Agent: Hi. Speaker1: Hello. Rep: Good morning. User123: Hey there."

        processors_config = [
            {'class': 'AddEnumeratedSpeakerIdentifiersTranscriptFilter'}
        ]

        result = Score.apply_processors_to_text(text, processors_config)

        # Should have Speaker A through D
        self.assertIn("Speaker A:", result)
        self.assertIn("Speaker B:", result)
        self.assertIn("Speaker C:", result)
        self.assertIn("Speaker D:", result)

    def test_enumerate_with_empty_text(self):
        """Test enumeration with empty text"""
        text = ""

        processors_config = [
            {'class': 'AddEnumeratedSpeakerIdentifiersTranscriptFilter'}
        ]

        result = Score.apply_processors_to_text(text, processors_config)

        self.assertEqual(result, "")

    def test_enumerate_with_no_speakers(self):
        """Test enumeration with text that has no speaker identifiers"""
        text = "This is just regular text without any speaker labels."

        processors_config = [
            {'class': 'AddEnumeratedSpeakerIdentifiersTranscriptFilter'}
        ]

        result = Score.apply_processors_to_text(text, processors_config)

        # Should remain unchanged
        self.assertEqual(result, text)

    def test_enumerate_speaker_order_by_first_appearance(self):
        """Test that speakers are labeled in order of first appearance"""
        text = "Customer: I have a question. Agent: How can I help? Customer: Thanks."

        processors_config = [
            {'class': 'AddEnumeratedSpeakerIdentifiersTranscriptFilter'}
        ]

        result = Score.apply_processors_to_text(text, processors_config)

        # Customer appears first, so should be Speaker A
        self.assertTrue(result.startswith("Speaker A:"))

        # Agent appears second, so should be Speaker B
        self.assertIn("Speaker B: How can I help", result)

    def test_enumerate_many_speakers(self):
        """Test enumeration with many speakers (> 26)"""
        # Create text with 28 different speakers
        speakers = [f"Speaker{i}" for i in range(28)]
        text = ". ".join([f"{speaker}: Message from {speaker}" for speaker in speakers])

        processors_config = [
            {'class': 'AddEnumeratedSpeakerIdentifiersTranscriptFilter'}
        ]

        result = Score.apply_processors_to_text(text, processors_config)

        # Should have A through Z (26 speakers)
        for i in range(26):
            letter = chr(65 + i)
            self.assertIn(f"Speaker {letter}:", result)

        # Should have AA and AB for speakers 27 and 28
        self.assertIn("Speaker AA:", result)
        self.assertIn("Speaker AB:", result)

    def test_enumerate_preserves_whitespace_and_punctuation(self):
        """Test that enumeration preserves whitespace and punctuation"""
        text = "Agent:   Hello!   Customer:  Hi there?  Agent:  How are you."

        processors_config = [
            {'class': 'AddEnumeratedSpeakerIdentifiersTranscriptFilter'}
        ]

        result = Score.apply_processors_to_text(text, processors_config)

        # Should preserve punctuation
        self.assertIn("Hello!", result)
        self.assertIn("Hi there?", result)
        self.assertIn("How are you.", result)

    def test_chain_with_other_processors(self):
        """Test chaining enumeration with other processors"""
        text = "Agent: I don't understand. Customer: It's not working."

        processors_config = [
            {'class': 'AddEnumeratedSpeakerIdentifiersTranscriptFilter'},
            {'class': 'ExpandContractionsProcessor'}
        ]

        result = Score.apply_processors_to_text(text, processors_config)

        # Should have enumerated speakers
        self.assertIn("Speaker A:", result)
        self.assertIn("Speaker B:", result)

        # Should have expanded contractions
        self.assertIn("do not", result)
        self.assertIn("It is not", result)


if __name__ == '__main__':
    unittest.main()
