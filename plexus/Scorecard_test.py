import unittest
from unittest.mock import Mock, patch, MagicMock
from plexus.Scorecard import Scorecard
import pytest

# Remove unittest.TestCase since we're using pure pytest style
class TestScorecard:

    def setUp(self):
        # Create a mock scorecard configuration
        self.mock_config = {
            'name': 'TestScorecard',
            'scores': [
                {'name': 'Score1', 'id': 1},
                {'name': 'Score2', 'id': 2, 'depends_on': ['Score1']},
                {'name': 'Score3', 'id': 3, 'depends_on': {'Score1': {'operator': '==', 'value': 'Pass'}}},
                {'name': 'Score4', 'id': 4, 'depends_on': {'Score1': {'operator': '!=', 'value': 'Fail'}}},
                {'name': 'Score5', 'id': 5, 'depends_on': {'Score1': {'operator': 'in', 'value': ['Pass', 'Partial']}}},
                {'name': 'Score6', 'id': 6, 'depends_on': {'Score1': {'operator': 'not in', 'value': ['Fail', 'N/A']}}}
            ]
        }
        self.scorecard = Scorecard(scorecard=self.mock_config['name'])
        # Set the properties and scores directly since we're not loading from YAML
        self.scorecard.properties = self.mock_config
        Scorecard.scores = self.mock_config['scores']
        
        # Mock the score registry
        self.mock_registry = MagicMock()
        self.scorecard.score_registry = self.mock_registry
        
        # Setup the get_properties mock to return score configs
        def get_properties_side_effect(score_name):
            for score in self.mock_config['scores']:
                if score['name'] == score_name:
                    return score
            return None
        self.mock_registry.get_properties.side_effect = get_properties_side_effect

    @pytest.fixture(autouse=True)
    def setup_method(self):
        self.setUp()

    def test_build_dependency_graph(self):
        """Test that dependency graph is built correctly"""
        subset_scores = ['Score1', 'Score2', 'Score3']
        graph, name_to_id = self.scorecard.build_dependency_graph(subset_scores)
        
        assert len(graph) == 3
        assert graph['1']['name'] == 'Score1'
        assert graph['1']['deps'] == []
        assert graph['2']['deps'] == ['1']
        assert graph['3']['deps'] == ['1']
        assert graph['3']['conditions']['1'] == {'operator': '==', 'value': 'Pass'}

    def test_check_dependency_conditions(self):
        """Test condition checking with different operators"""
        graph, _ = self.scorecard.build_dependency_graph(['Score1', 'Score3', 'Score4', 'Score5', 'Score6'])
        
        # Mock results for Score1
        results = {
            '1': Mock(value='Pass')  # Score1 result
        }
        
        # Test == operator
        assert self.scorecard.check_dependency_conditions('3', graph, results)  # Score3 depends on Score1 == Pass
        results['1'].value = 'Fail'
        assert not self.scorecard.check_dependency_conditions('3', graph, results)
        
        # Test != operator
        assert not self.scorecard.check_dependency_conditions('4', graph, results)  # Score4 depends on Score1 != Fail
        results['1'].value = 'Pass'
        assert self.scorecard.check_dependency_conditions('4', graph, results)
        
        # Test in operator
        assert self.scorecard.check_dependency_conditions('5', graph, results)  # Score5 depends on Score1 in [Pass, Partial]
        results['1'].value = 'Fail'
        assert not self.scorecard.check_dependency_conditions('5', graph, results)
        
        # Test not in operator
        assert not self.scorecard.check_dependency_conditions('6', graph, results)  # Score6 depends on Score1 not in [Fail, N/A]
        results['1'].value = 'Pass'
        assert self.scorecard.check_dependency_conditions('6', graph, results)

    @pytest.mark.asyncio
    @patch('plexus.Scorecard.get_score_result')
    async def test_score_entire_text_executes_all_scores(self, mock_get_score_result):
        """Test that all scores are executed when there are no dependencies"""
        # Create a simple config without dependencies for this test
        simple_config = {
            'name': 'TestScorecard',
            'scores': [
                {'name': 'SimpleScore1', 'id': 1},
                {'name': 'SimpleScore2', 'id': 2},
                {'name': 'SimpleScore3', 'id': 3}
            ]
        }
        self.scorecard.properties = simple_config
        Scorecard.scores = simple_config['scores']
        
        # Update the get_properties mock for simple scores
        def get_properties_side_effect(score_name):
            for score in simple_config['scores']:
                if score['name'] == score_name:
                    return score
            return None
        self.mock_registry.get_properties.side_effect = get_properties_side_effect

        # Setup mock return values
        mock_get_score_result.side_effect = [
            [Mock(name='SimpleScore1')],
            [Mock(name='SimpleScore2')],
            [Mock(name='SimpleScore3')]
        ]

        # Call the method we're testing
        result = await self.scorecard.score_entire_text(
            text="Sample text",
            metadata={},
            modality="test"
        )

        # Assert that get_score_result was called for each score
        assert mock_get_score_result.call_count == 3

        # Assert that the result contains all scores
        assert len(result) == 3

    @pytest.mark.asyncio
    @patch('plexus.Scorecard.get_score_result')
    async def test_score_entire_text_with_dependencies(self, mock_get_score_result):
        """Test scoring with dependencies"""
        # Setup mock return values
        mock_get_score_result.side_effect = [
            [Mock(value='Pass')],  # Score1 result
            [Mock(value='Good')],  # Score2 result (depends on Score1)
            [Mock(value='Great')]  # Score3 result (depends on Score1 with condition)
        ]

        # Call the method we're testing
        result = await self.scorecard.score_entire_text(
            text="Sample text",
            metadata={},
            modality="test",
            subset_of_score_names=['Score1', 'Score2', 'Score3']
        )

        # Assert that get_score_result was called in the correct order
        assert mock_get_score_result.call_count == 3
        # Score1 should be processed first as it has no dependencies
        assert mock_get_score_result.call_args_list[0][1]['score'] == 'Score1'
        
        # Verify results were stored correctly
        assert len(result) == 3
        assert result['1'].value == 'Pass'
        assert result['2'].value == 'Good'
        assert result['3'].value == 'Great'

    @pytest.mark.asyncio
    @patch('plexus.Scorecard.get_score_result')
    async def test_score_entire_text_skips_failed_conditions(self, mock_get_score_result):
        """Test that scores are skipped when their dependency conditions are not met"""
        # Setup mock return values
        mock_get_score_result.side_effect = [
            [Mock(value='Fail')]  # Score1 result - will cause Score3's condition to fail
        ]

        # Call the method we're testing
        result = await self.scorecard.score_entire_text(
            text="Sample text",
            metadata={},
            modality="test",
            subset_of_score_names=['Score1', 'Score3']  # Score3 depends on Score1 == 'Pass'
        )

        # Assert that get_score_result was only called for Score1
        assert mock_get_score_result.call_count == 1
        assert mock_get_score_result.call_args_list[0][1]['score'] == 'Score1'
        
        # Verify Score3 was skipped (not in results)
        assert '1' in result  # Score1 should be present
        assert '3' not in result  # Score3 should be skipped

if __name__ == '__main__':
    pytest.main()