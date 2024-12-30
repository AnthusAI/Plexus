import unittest
from unittest.mock import Mock, patch
from plexus.Scorecard import Scorecard
import pytest

@pytest.mark.asyncio
class TestScorecard(unittest.TestCase):

    def setUp(self):
        # Create a mock scorecard configuration
        self.mock_config = {
            'name': 'TestScorecard',
            'scores': [
                {'name': 'Score1', 'id': 1},
                {'name': 'Score2', 'id': 2},
                {'name': 'Score3', 'id': 3}
            ]
        }
        self.scorecard = Scorecard(scorecard=self.mock_config['name'])

    @patch('plexus.Scorecard.Scorecard.get_score_result')
    async def test_score_entire_text_executes_all_scores(self, mock_get_score_result):
        # Setup mock return values
        mock_get_score_result.side_effect = [
            [Mock(name='Score1')],
            [Mock(name='Score2')],
            [Mock(name='Score3')]
        ]

        # Call the method we're testing (note it's async)
        result = await self.scorecard.score_entire_text(
            text="Sample text",
            metadata={},
            modality="test"
        )

        # Assert that get_score_result was called for each score
        self.assertEqual(mock_get_score_result.call_count, 3)

        # Assert that the result contains all scores
        self.assertEqual(len(result), 3)

if __name__ == '__main__':
    unittest.main()