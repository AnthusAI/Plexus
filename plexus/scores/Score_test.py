import os
import json
import unittest
from pydantic import ValidationError
from plexus.scores.Score import Score
from plexus.scores.MLClassifier import MLClassifier

# Create a concrete subclass of Score for testing
class ConcreteScore(Score):
    def load_context(self, context):
        pass
    def predict(self, model_input: MLClassifier.ModelInput):
        return "computed score"

class TestScore(unittest.TestCase):

    def test_compute_score_result(self):
        # Create an instance of the concrete subclass
        score = ConcreteScore(
            scorecard_name="Test scorecard",
            score_name="Test score"
        )
        
        # Call the compute_score_result method
        result = score.predict(
            MLClassifier.ModelInput(
                transcript="Test transcript"
            )
        )
        
        # Check that the method returns the expected score
        self.assertEqual(result, "computed score")

    def test_invalid_parameters(self):
        with self.assertRaises(ValidationError):
            ConcreteScore(scorecard_name=123, score_name=None)

    def test_report_directory_creation(self):
        score = ConcreteScore(scorecard_name="Test scorecard", score_name="Test score")
        report_directory = score.report_directory_path()
        self.assertTrue(os.path.exists(report_directory))

    def test_report_file_name(self):
        score = ConcreteScore(scorecard_name="Test scorecard", score_name="Test score")
        report_file = score.report_file_name("test_file.txt")
        expected_path = "./reports/Test_scorecard/Test_score/test_file.txt".replace(' ', '_')
        self.assertEqual(report_file, expected_path)

    def test_record_configuration(self):
        score = ConcreteScore(scorecard_name="Test scorecard", score_name="Test score")
        configuration = {"param1": "value1", "param2": "value2"}
        score.record_configuration(configuration)
        config_path = score.report_file_name("configuration.json")
        with open(config_path, 'r') as json_file:
            recorded_config = json.load(json_file)
        self.assertEqual(recorded_config, configuration)

if __name__ == '__main__':
    unittest.main()