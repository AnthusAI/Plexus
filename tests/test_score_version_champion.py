
import unittest
from unittest.mock import Mock, patch, MagicMock
from plexus.dashboard.api.models.score import Score

class TestScoreVersionChampion(unittest.TestCase):
    def setUp(self):
        self.mock_client = Mock()
        self.score = Score(
            id="score-123",
            name="Test Score",
            key="test_score",
            externalId="ext-123",
            type="SimpleLLMScore",
            order=1,
            sectionId="section-1",
            client=self.mock_client
        )

    def test_auto_promote_champion_when_none_exists(self):
        """Test that a new version is auto-promoted to champion if no champion exists."""
        
        # 1. Mock getScore response to return NO championVersionId
        self.mock_client.execute.side_effect = [
            # First call: getScore (check current champion)
            {
                'getScore': {
                    'championVersionId': None
                }
            },
            # Second call: createScoreVersion
            {
                'createScoreVersion': {
                    'id': 'version-new-123',
                    'configuration': 'yaml: content',
                    'createdAt': '2023-01-01T00:00:00Z',
                    'updatedAt': '2023-01-01T00:00:00Z',
                    'note': 'Test note',
                    'score': {
                        'id': 'score-123',
                        'championVersionId': None
                    }
                }
            },
            # Third call: updateScore (promote to champion)
            {
                'updateScore': {
                    'id': 'score-123',
                    'championVersionId': 'version-new-123'
                }
            }
        ]

        # Call create_version_from_code
        result = self.score.create_version_from_code("yaml: content", "Test note")

        # Verify assertions
        self.assertTrue(result['success'])
        self.assertEqual(result['version_id'], 'version-new-123')
        self.assertTrue(result['champion_updated']) # Should be true because we promoted it

        # Verify updateScore was called with correct parameters
        # We expect 3 calls to execute: getScore, createScoreVersion, updateScore
        self.assertEqual(self.mock_client.execute.call_count, 3)
        
        # Check the third call (updateScore)
        args, kwargs = self.mock_client.execute.call_args
        query = args[0]
        variables = args[1]
        
        self.assertIn('mutation UpdateScore', query)
        self.assertEqual(variables['input']['id'], 'score-123')
        self.assertEqual(variables['input']['championVersionId'], 'version-new-123')

    def test_do_not_auto_promote_champion_when_one_exists(self):
        """Test that a new version is NOT auto-promoted if a champion already exists."""
        
        # 1. Mock getScore response to return EXISTING championVersionId
        self.mock_client.execute.side_effect = [
            # First call: getScore (check current champion)
            {
                'getScore': {
                    'championVersionId': 'version-existing-999'
                }
            },
            # Second call: getScoreVersion (compare content)
            {
                'getScoreVersion': {
                    'configuration': 'yaml: old_content',
                    'guidelines': ''
                }
            },
            # Third call: createScoreVersion
            {
                'createScoreVersion': {
                    'id': 'version-new-123',
                    'configuration': 'yaml: new_content',
                    'createdAt': '2023-01-01T00:00:00Z',
                    'updatedAt': '2023-01-01T00:00:00Z',
                    'note': 'Test note',
                    'score': {
                        'id': 'score-123',
                        'championVersionId': 'version-existing-999'
                    }
                }
            }
        ]

        # Call create_version_from_code
        result = self.score.create_version_from_code("yaml: new_content", "Test note")

        # Verify assertions
        self.assertTrue(result['success'])
        self.assertEqual(result['version_id'], 'version-new-123')
        self.assertFalse(result['champion_updated']) # Should be false

        # Verify execute calls - should NOT include updateScore
        self.assertEqual(self.mock_client.execute.call_count, 3) 
        
        # Iterate through calls to ensure UpdateScore was NOT called
        for call in self.mock_client.execute.call_args_list:
            query = call[0][0]
            self.assertNotIn('mutation UpdateScore', query)

if __name__ == '__main__':
    unittest.main()
