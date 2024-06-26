import unittest

from plexus.Score import Score

# Create a concrete subclass of Score for testing
class ConcreteScore(Score):
    def compute_result(self):
        # Implement the abstract method with a simple return value for testing
        return "computed score"

class TestScore(unittest.TestCase):

    def test_process_transcript(self):
        # Create an instance of the concrete subclass
        score = ConcreteScore(transcript="Test transcript")
        
        # Call the process_transcript method
        processed_transcript = score.process_transcript(score.transcript)
        
        # Check that the method returns the transcript as is
        self.assertEqual(processed_transcript, "Test transcript")

    def test_compute_score_result(self):
        # Create an instance of the concrete subclass
        score = ConcreteScore(transcript="Test transcript")
        
        # Call the compute_score_result method
        result = score.compute_result()
        
        # Check that the method returns the expected score
        self.assertEqual(result, "computed score")

if __name__ == '__main__':
    unittest.main()