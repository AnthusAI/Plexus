import unittest
from unittest.mock import Mock, patch
from plexus.Scorecard import Scorecard

class TestScorecard(unittest.TestCase):

    def setUp(self):
        # Create a mock scorecard configuration
        self.mock_config = {
            'scores': {
                'Score1': {'id': 1},
                'Score2': {'id': 2},
                'Score3': {'id': 3},
            }
        }
        self.scorecard = Scorecard(self.mock_config)

    @patch('Plexus.plexus.Scorecard.Scorecard.get_score_result')
    def test_score_entire_text_executes_all_scores(self, mock_get_score_result):
        # Setup mock return values
        mock_get_score_result.side_effect = [
            [Mock(name='Score1')],
            [Mock(name='Score2')],
            [Mock(name='Score3')]
        ]

        # Call the method we're testing
        result = self.scorecard.score_entire_text(text="Sample text")

        # Assert that get_score_result was called for each score
        self.assertEqual(mock_get_score_result.call_count, 3)

        # Assert that the result contains all scores
        self.assertIn('Score1', result)
        self.assertIn('Score2', result)
        self.assertIn('Score3', result)

if __name__ == '__main__':
    unittest.main()