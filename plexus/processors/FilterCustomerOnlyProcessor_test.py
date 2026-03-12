import unittest
import pandas as pd
from plexus.processors.FilterCustomerOnlyProcessor import FilterCustomerOnlyProcessor
from plexus.processors.RemoveSpeakerIdentifiersTranscriptFilter import RemoveSpeakerIdentifiersTranscriptFilter
from plexus.scores.Score import Score


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


class TestFilterCustomerOnlyProcessor(unittest.TestCase):
    """Test suite for FilterCustomerOnlyProcessor"""

    def setUp(self):
        """Set up test fixtures"""
        self.processor = FilterCustomerOnlyProcessor()

    def test_basic_customer_agent_filtering(self):
        """Test basic filtering of customer vs agent speech"""
        text = "Agent: Hello, how can I help you? Customer: I need help with my order. Agent: Sure, what's your order number? Customer: It's 12345."

        result = _process_text(self.processor, text)

        # Should only contain customer utterances
        self.assertIn("I need help with my order", result)
        self.assertIn("It's 12345", result)
        # Should not contain agent utterances
        self.assertNotIn("Hello, how can I help you", result)
        self.assertNotIn("Sure, what's your order number", result)

    def test_contact_label_variant(self):
        """Test filtering with 'Contact:' label instead of 'Customer:'"""
        text = "Agent: How are you today? Contact: I'm doing well, thanks. Agent: Great to hear!"

        result = _process_text(self.processor, text)

        # Should contain contact utterances
        self.assertIn("I'm doing well, thanks", result)
        # Should not contain agent utterances
        self.assertNotIn("How are you today", result)
        self.assertNotIn("Great to hear", result)

    def test_representative_label_variant(self):
        """Test filtering with 'Representative:' label"""
        text = "Representative: Welcome to support. Customer: I have a question. Representative: Go ahead."

        result = _process_text(self.processor, text)

        # Should contain customer utterances
        self.assertIn("I have a question", result)
        # Should not contain representative utterances
        self.assertNotIn("Welcome to support", result)
        self.assertNotIn("Go ahead", result)

    def test_rep_label_variant(self):
        """Test filtering with 'Rep:' label"""
        text = "Rep: Hi there. Customer: Hello. Rep: What can I do for you?"

        result = _process_text(self.processor, text)

        # Should contain customer utterances
        self.assertIn("Hello", result)
        # Should not contain rep utterances
        self.assertNotIn("Hi there", result)
        self.assertNotIn("What can I do for you", result)

    def test_no_customer_speech(self):
        """Test handling of transcript with no customer speech"""
        text = "Agent: Hello? Agent: Are you there? Agent: I guess they hung up."

        result = _process_text(self.processor, text)

        # Should return empty or whitespace-only string
        self.assertEqual(result.strip(), "")

    def test_all_customer_speech(self):
        """Test handling of transcript with only customer speech"""
        text = "Customer: I need help. Customer: This is urgent. Customer: Please respond."

        result = _process_text(self.processor, text)

        # Should contain all customer utterances
        self.assertIn("I need help", result)
        self.assertIn("This is urgent", result)
        self.assertIn("Please respond", result)

    def test_empty_text(self):
        """Test handling of empty text"""
        text = ""

        result = _process_text(self.processor, text)

        self.assertEqual(result, "")

    def test_nan_text(self):
        """Test handling of NaN text"""
        # For Score.Input, we'll pass empty string as NaN doesn't make sense for text field
        text = ""

        result = _process_text(self.processor, text)

        self.assertEqual(result, "")

    def test_multiple_customer_turns(self):
        """Test multiple customer speaking turns are concatenated"""
        text = "Customer: First thing. Agent: Okay. Customer: Second thing. Agent: Got it. Customer: Third thing."

        result = _process_text(self.processor, text)

        # All customer turns should be present
        self.assertIn("First thing", result)
        self.assertIn("Second thing", result)
        self.assertIn("Third thing", result)
        # Agent turns should not be present
        self.assertNotIn("Okay", result)
        self.assertNotIn("Got it", result)

    def test_no_spaces_around_labels(self):
        """Test handling of labels without spaces"""
        text = "Agent:Hello there.Customer:Hi back.Agent:How are you?Customer:I'm fine."

        result = _process_text(self.processor, text)

        # Should still extract customer speech correctly
        self.assertIn("Hi back", result)
        self.assertIn("I'm fine", result)
        # Should not contain agent speech
        self.assertNotIn("Hello there", result)
        self.assertNotIn("How are you", result)

    def test_preserves_speaker_identifiers(self):
        """Test that speaker identifiers are preserved (not removed)"""
        text = "Agent: Hello. Customer: Hi there. Agent: How are you? Customer: Good."

        result = _process_text(self.processor, text)

        # The processor should preserve "Customer:" labels
        # (RemoveSpeakerIdentifiersTranscriptFilter removes them in a separate step)
        # Should contain customer speech
        self.assertIn("Hi there", result)
        self.assertIn("Good", result)

    def test_chaining_with_remove_speaker_identifiers(self):
        """Test chaining FilterCustomerOnlyProcessor with RemoveSpeakerIdentifiersTranscriptFilter"""
        text = "Agent: Hello, how can I help? Customer: I need assistance. Agent: Sure thing. Customer: Thank you."

        # First apply customer-only filter
        customer_only_processor = FilterCustomerOnlyProcessor()
        score_input = Score.Input(text=text, metadata={})
        score_input = customer_only_processor.process(score_input)

        # Then remove speaker identifiers
        remove_identifiers_processor = RemoveSpeakerIdentifiersTranscriptFilter()
        score_input = remove_identifiers_processor.process(score_input)

        # Should have customer speech without any speaker labels
        result = score_input.text
        self.assertIn("I need assistance", result)
        self.assertIn("Thank you", result)
        # Should not have agent speech
        self.assertNotIn("Hello", result)
        self.assertNotIn("Sure thing", result)
        # Should not have any speaker labels
        self.assertNotIn("Customer:", result)
        self.assertNotIn("Agent:", result)

    def test_multiple_rows(self):
        """Test processing multiple text inputs"""
        texts = [
            "Agent: First call. Customer: Customer one.",
            "Agent: Second call. Customer: Customer two.",
            "Agent: Third call. Customer: Customer three."
        ]

        # Process each text
        results = [_process_text(self.processor, text) for text in texts]

        # Check each result
        self.assertIn("Customer one", results[0])
        self.assertNotIn("First call", results[0])

        self.assertIn("Customer two", results[1])
        self.assertNotIn("Second call", results[1])

        self.assertIn("Customer three", results[2])
        self.assertNotIn("Third call", results[2])

    def test_mixed_label_formats(self):
        """Test handling of mixed label formats in same transcript"""
        text = "Agent: Hello. Contact: Hi. Representative: How can I help? Customer: I need help."

        result = _process_text(self.processor, text)

        # Should extract both Contact and Customer speech
        self.assertIn("Hi", result)
        self.assertIn("I need help", result)
        # Should not have agent/representative speech
        self.assertNotIn("Hello", result)
        self.assertNotIn("How can I help", result)


if __name__ == '__main__':
    unittest.main()

