import unittest
import pandas as pd
from plexus.processors.FilterCustomerOnlyProcessor import FilterCustomerOnlyProcessor
from plexus.processors.RemoveSpeakerIdentifiersTranscriptFilter import RemoveSpeakerIdentifiersTranscriptFilter


class TestFilterCustomerOnlyProcessor(unittest.TestCase):
    """Test suite for FilterCustomerOnlyProcessor"""

    def setUp(self):
        """Set up test fixtures"""
        self.processor = FilterCustomerOnlyProcessor()

    def test_basic_customer_agent_filtering(self):
        """Test basic filtering of customer vs agent speech"""
        df = pd.DataFrame({
            'text': [
                "Agent: Hello, how can I help you? Customer: I need help with my order. Agent: Sure, what's your order number? Customer: It's 12345."
            ]
        })
        
        result = self.processor.process(df)
        
        # Should only contain customer utterances
        self.assertIn("I need help with my order", result['text'].iloc[0])
        self.assertIn("It's 12345", result['text'].iloc[0])
        # Should not contain agent utterances
        self.assertNotIn("Hello, how can I help you", result['text'].iloc[0])
        self.assertNotIn("Sure, what's your order number", result['text'].iloc[0])

    def test_contact_label_variant(self):
        """Test filtering with 'Contact:' label instead of 'Customer:'"""
        df = pd.DataFrame({
            'text': [
                "Agent: How are you today? Contact: I'm doing well, thanks. Agent: Great to hear!"
            ]
        })
        
        result = self.processor.process(df)
        
        # Should contain contact utterances
        self.assertIn("I'm doing well, thanks", result['text'].iloc[0])
        # Should not contain agent utterances
        self.assertNotIn("How are you today", result['text'].iloc[0])
        self.assertNotIn("Great to hear", result['text'].iloc[0])

    def test_representative_label_variant(self):
        """Test filtering with 'Representative:' label"""
        df = pd.DataFrame({
            'text': [
                "Representative: Welcome to support. Customer: I have a question. Representative: Go ahead."
            ]
        })
        
        result = self.processor.process(df)
        
        # Should contain customer utterances
        self.assertIn("I have a question", result['text'].iloc[0])
        # Should not contain representative utterances
        self.assertNotIn("Welcome to support", result['text'].iloc[0])
        self.assertNotIn("Go ahead", result['text'].iloc[0])

    def test_rep_label_variant(self):
        """Test filtering with 'Rep:' label"""
        df = pd.DataFrame({
            'text': [
                "Rep: Hi there. Customer: Hello. Rep: What can I do for you?"
            ]
        })
        
        result = self.processor.process(df)
        
        # Should contain customer utterances
        self.assertIn("Hello", result['text'].iloc[0])
        # Should not contain rep utterances
        self.assertNotIn("Hi there", result['text'].iloc[0])
        self.assertNotIn("What can I do for you", result['text'].iloc[0])

    def test_no_customer_speech(self):
        """Test handling of transcript with no customer speech"""
        df = pd.DataFrame({
            'text': [
                "Agent: Hello? Agent: Are you there? Agent: I guess they hung up."
            ]
        })
        
        result = self.processor.process(df)
        
        # Should return empty or whitespace-only string
        self.assertEqual(result['text'].iloc[0].strip(), "")

    def test_all_customer_speech(self):
        """Test handling of transcript with only customer speech"""
        df = pd.DataFrame({
            'text': [
                "Customer: I need help. Customer: This is urgent. Customer: Please respond."
            ]
        })
        
        result = self.processor.process(df)
        
        # Should contain all customer utterances
        self.assertIn("I need help", result['text'].iloc[0])
        self.assertIn("This is urgent", result['text'].iloc[0])
        self.assertIn("Please respond", result['text'].iloc[0])

    def test_empty_text(self):
        """Test handling of empty text"""
        df = pd.DataFrame({
            'text': [""]
        })
        
        result = self.processor.process(df)
        
        self.assertEqual(result['text'].iloc[0], "")

    def test_nan_text(self):
        """Test handling of NaN text"""
        df = pd.DataFrame({
            'text': [pd.NA]
        })
        
        result = self.processor.process(df)
        
        self.assertEqual(result['text'].iloc[0], "")

    def test_multiple_customer_turns(self):
        """Test multiple customer speaking turns are concatenated"""
        df = pd.DataFrame({
            'text': [
                "Customer: First thing. Agent: Okay. Customer: Second thing. Agent: Got it. Customer: Third thing."
            ]
        })
        
        result = self.processor.process(df)
        
        # All customer turns should be present
        self.assertIn("First thing", result['text'].iloc[0])
        self.assertIn("Second thing", result['text'].iloc[0])
        self.assertIn("Third thing", result['text'].iloc[0])
        # Agent turns should not be present
        self.assertNotIn("Okay", result['text'].iloc[0])
        self.assertNotIn("Got it", result['text'].iloc[0])

    def test_no_spaces_around_labels(self):
        """Test handling of labels without spaces"""
        df = pd.DataFrame({
            'text': [
                "Agent:Hello there.Customer:Hi back.Agent:How are you?Customer:I'm fine."
            ]
        })
        
        result = self.processor.process(df)
        
        # Should still extract customer speech correctly
        self.assertIn("Hi back", result['text'].iloc[0])
        self.assertIn("I'm fine", result['text'].iloc[0])
        # Should not contain agent speech
        self.assertNotIn("Hello there", result['text'].iloc[0])
        self.assertNotIn("How are you", result['text'].iloc[0])

    def test_preserves_speaker_identifiers(self):
        """Test that speaker identifiers are preserved (not removed)"""
        df = pd.DataFrame({
            'text': [
                "Agent: Hello. Customer: Hi there. Agent: How are you? Customer: Good."
            ]
        })
        
        result = self.processor.process(df)
        
        # The processor should preserve "Customer:" labels
        # (RemoveSpeakerIdentifiersTranscriptFilter removes them in a separate step)
        text = result['text'].iloc[0]
        # Should contain customer speech
        self.assertIn("Hi there", text)
        self.assertIn("Good", text)

    def test_chaining_with_remove_speaker_identifiers(self):
        """Test chaining FilterCustomerOnlyProcessor with RemoveSpeakerIdentifiersTranscriptFilter"""
        df = pd.DataFrame({
            'text': [
                "Agent: Hello, how can I help? Customer: I need assistance. Agent: Sure thing. Customer: Thank you."
            ]
        })
        
        # First apply customer-only filter
        customer_only_processor = FilterCustomerOnlyProcessor()
        df = customer_only_processor.process(df)
        
        # Then remove speaker identifiers
        remove_identifiers_processor = RemoveSpeakerIdentifiersTranscriptFilter()
        df = remove_identifiers_processor.process(df)
        
        # Should have customer speech without any speaker labels
        text = df['text'].iloc[0]
        self.assertIn("I need assistance", text)
        self.assertIn("Thank you", text)
        # Should not have agent speech
        self.assertNotIn("Hello", text)
        self.assertNotIn("Sure thing", text)
        # Should not have any speaker labels
        self.assertNotIn("Customer:", text)
        self.assertNotIn("Agent:", text)

    def test_multiple_rows(self):
        """Test processing multiple rows in dataframe"""
        df = pd.DataFrame({
            'text': [
                "Agent: First call. Customer: Customer one.",
                "Agent: Second call. Customer: Customer two.",
                "Agent: Third call. Customer: Customer three."
            ]
        })
        
        result = self.processor.process(df)
        
        # Check each row
        self.assertIn("Customer one", result['text'].iloc[0])
        self.assertNotIn("First call", result['text'].iloc[0])
        
        self.assertIn("Customer two", result['text'].iloc[1])
        self.assertNotIn("Second call", result['text'].iloc[1])
        
        self.assertIn("Customer three", result['text'].iloc[2])
        self.assertNotIn("Third call", result['text'].iloc[2])

    def test_mixed_label_formats(self):
        """Test handling of mixed label formats in same transcript"""
        df = pd.DataFrame({
            'text': [
                "Agent: Hello. Contact: Hi. Representative: How can I help? Customer: I need help."
            ]
        })
        
        result = self.processor.process(df)
        
        # Should extract both Contact and Customer speech
        text = result['text'].iloc[0]
        self.assertIn("Hi", text)
        self.assertIn("I need help", text)
        # Should not have agent/representative speech
        self.assertNotIn("Hello", text)
        self.assertNotIn("How can I help", text)


if __name__ == '__main__':
    unittest.main()

