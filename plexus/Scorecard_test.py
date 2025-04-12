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

        # Create a mock score class
        mock_score_class = MagicMock()
        mock_score_instance = MagicMock()

        # Set up the async get_score_result method
        async def mock_get_score_result(*args, **kwargs):
            return Mock(value='Pass')
        
        mock_score_instance.get_score_result = mock_get_score_result

        # Set up the async predict method
        async def mock_predict(*args, **kwargs):
            return Mock(value='Pass')
        
        mock_score_instance.predict = mock_predict

        # Set up the async create method
        async def mock_create(**kwargs):
            return mock_score_instance

        mock_score_class.create = mock_create
        
        # Set up the registry's get method to return the mock score class
        def mock_get(score_name):
            return mock_score_class
            
        self.mock_registry.get.side_effect = mock_get

        # Mock get_score_result to be async
        async def mock_get_score_result(*args, **kwargs):
            score_name = kwargs.get('score')
            return Mock(name=score_name, value='Pass')
        
        self.scorecard.get_score_result = mock_get_score_result

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
    async def test_score_entire_text_executes_all_scores(self):
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
        self.scorecard.scores = simple_config['scores']  # Use instance scores instead of class level
        
        # Update the get_properties mock for simple scores
        def get_properties_side_effect(score_name):
            for score in simple_config['scores']:
                if score['name'] == score_name:
                    return score
            return None
        self.mock_registry.get_properties.side_effect = get_properties_side_effect

        # Create a mock score class
        mock_score_class = MagicMock()
        mock_score_instance = MagicMock()

        # Set up the async get_score_result method
        async def mock_get_score_result(*args, **kwargs):
            return Mock(value='Pass')
        
        mock_score_instance.get_score_result = mock_get_score_result

        # Set up the async predict method
        async def mock_predict(*args, **kwargs):
            return Mock(value='Pass')
        
        mock_score_instance.predict = mock_predict

        # Set up the async create method
        async def mock_create(**kwargs):
            return mock_score_instance

        mock_score_class.create = mock_create
        
        # Set up the registry's get method to return the mock score class
        def mock_get(score_name):
            return mock_score_class
            
        self.mock_registry.get.side_effect = mock_get

        # Override score_names_to_process to use our simple scores
        def mock_score_names_to_process():
            return ['SimpleScore1', 'SimpleScore2', 'SimpleScore3']
        
        original_method = self.scorecard.score_names_to_process
        self.scorecard.score_names_to_process = mock_score_names_to_process

        try:
            # Call the method we're testing
            result = await self.scorecard.score_entire_text(
                text="Sample text",
                metadata={},
                modality="test"
            )
            
            # Assert that the result contains all scores
            assert len(result) == 3
        finally:
            # Restore the original method
            self.scorecard.score_names_to_process = original_method

    @pytest.mark.asyncio
    async def test_score_entire_text_with_dependencies(self):
        """Test scoring with dependencies"""
        # Create a config with dependencies for this test
        dependency_config = {
            'name': 'TestScorecard',
            'scores': [
                {'name': 'Score1', 'id': '1'},
                {'name': 'Score2', 'id': '2', 'depends_on': ['Score1']},
                {'name': 'Score3', 'id': '3', 'depends_on': ['Score1']}
            ]
        }
        
        # Set up the scorecard (use instance properties)
        self.scorecard.properties = dependency_config
        self.scorecard.scores = dependency_config['scores']
        
        # Update the mocks to provide score properties
        def get_properties_side_effect(score_name):
            for score in dependency_config['scores']:
                if score['name'] == score_name:
                    return score
            return None
        self.mock_registry.get_properties.side_effect = get_properties_side_effect
            
        # Create a mock score class
        mock_score_class = MagicMock()
        mock_score_instance = MagicMock()

        # Set up the async predict method
        async def mock_predict(context=None, model_input=None):
            # Extract score name from the configuration
            score_name = mock_score_instance.score_name
            mock_results = {
                'Score1': Mock(value='Pass'),
                'Score2': Mock(value='Good'),
                'Score3': Mock(value='Great')
            }
            return mock_results.get(score_name, Mock(value='Pass'))
        
        mock_score_instance.predict = mock_predict

        # Set up the async create method
        async def mock_create(**kwargs):
            mock_score_instance.score_name = kwargs.get('score_name')
            return mock_score_instance

        mock_score_class.create = mock_create
        
        # Set up the registry's get method to return the mock score class
        def mock_get(score_name):
            return mock_score_class
            
        self.mock_registry.get.side_effect = mock_get

        # Call the method we're testing
        result = await self.scorecard.score_entire_text(
            text="Sample text",
            metadata={},
            modality="test",
            subset_of_score_names=['Score1', 'Score2', 'Score3']
        )
        
        # Verify results were stored correctly
        assert len(result) == 3
        assert result['1'].value == 'Pass'
        assert result['2'].value == 'Good'
        assert result['3'].value == 'Great'

    @pytest.mark.asyncio
    async def test_score_entire_text_skips_failed_conditions(self):
        """Test that scores are skipped when their dependency conditions are not met"""
        # Create a mock score class
        mock_score_class = MagicMock()
        mock_score_instance = MagicMock()

        # Set up the async predict method
        async def mock_predict(context=None, model_input=None):
            # Extract score name from the configuration
            score_name = mock_score_instance.score_name
            mock_results = {
                'Score1': Mock(value='Fail'),
                'Score3': Mock(value='Pass')  # This should be skipped due to Score1's Fail value
            }
            return mock_results.get(score_name, Mock(value='Pass'))
        
        mock_score_instance.predict = mock_predict

        # Set up the async create method
        async def mock_create(**kwargs):
            mock_score_instance.score_name = kwargs.get('score_name')
            return mock_score_instance

        mock_score_class.create = mock_create
        
        # Set up the registry's get method to return the mock score class
        def mock_get(score_name):
            return mock_score_class
            
        self.mock_registry.get.side_effect = mock_get

        # Call the method we're testing
        result = await self.scorecard.score_entire_text(
            text="Sample text",
            metadata={},
            modality="test",
            subset_of_score_names=['Score1', 'Score3']  # Score3 depends on Score1 == 'Pass'
        )
        
        # Verify Score3 was skipped (not in results)
        assert '1' in result  # Score1 should be present
        assert result['1'].value == 'Fail'  # Score1 should have failed
        assert '3' not in result  # Score3 should be skipped

    @pytest.mark.asyncio
    async def test_score_entire_text_handles_single_result(self):
        """Test that score_entire_text correctly handles a single Result object"""
        # Create a simple config without dependencies for this test
        simple_config = {
            'name': 'TestScorecard',
            'scores': [
                {'name': 'SingleResultScore', 'id': 1}
            ]
        }
        self.scorecard.properties = simple_config
        self.scorecard.scores = simple_config['scores']
        
        # Update the get_properties mock for simple scores
        def get_properties_side_effect(score_name):
            for score in simple_config['scores']:
                if score['name'] == score_name:
                    return score
            return None
        self.mock_registry.get_properties.side_effect = get_properties_side_effect

        # Create a mock score class
        mock_score_class = MagicMock()
        mock_score_instance = MagicMock()

        # Set up the async get_score_result method
        async def mock_get_score_result(*args, **kwargs):
            return Mock(value='Pass')
        
        mock_score_instance.get_score_result = mock_get_score_result

        # Set up the async predict method
        async def mock_predict(*args, **kwargs):
            return Mock(value='Pass')
        
        mock_score_instance.predict = mock_predict

        # Set up the async create method
        async def mock_create(**kwargs):
            return mock_score_instance

        mock_score_class.create = mock_create
        
        # Set up the registry's get method to return the mock score class
        def mock_get(score_name):
            return mock_score_class
            
        self.mock_registry.get.side_effect = mock_get

        # Override score_names_to_process to use our simple score
        def mock_score_names_to_process():
            return ['SingleResultScore']
        
        original_method = self.scorecard.score_names_to_process
        self.scorecard.score_names_to_process = mock_score_names_to_process

        try:
            # Call the method we're testing
            result = await self.scorecard.score_entire_text(
                text="Sample text",
                metadata={},
                modality="test"
            )
            
            # Assert that the result contains the score
            assert len(result) == 1
            assert result['1'].value == 'Pass'
        finally:
            # Restore the original method
            self.scorecard.score_names_to_process = original_method

    @pytest.mark.asyncio
    async def test_score_entire_text_handles_result_list(self):
        """Test that score_entire_text correctly handles a list of Result objects"""
        # Create a simple config without dependencies for this test
        simple_config = {
            'name': 'TestScorecard',
            'scores': [
                {'name': 'ListResultScore', 'id': 1}
            ]
        }
        self.scorecard.properties = simple_config
        self.scorecard.scores = simple_config['scores']  # Use instance scores instead of class level
        
        # Update the get_properties mock for simple scores
        def get_properties_side_effect(score_name):
            for score in simple_config['scores']:
                if score['name'] == score_name:
                    return score
            return None
        self.mock_registry.get_properties.side_effect = get_properties_side_effect

        # Create a mock score class
        mock_score_class = MagicMock()
        mock_score_instance = MagicMock()

        # Set up the async get_score_result method
        async def mock_get_score_result(*args, **kwargs):
            return [Mock(value='Pass')]
        
        mock_score_instance.get_score_result = mock_get_score_result

        # Set up the async predict method
        async def mock_predict(*args, **kwargs):
            return [Mock(value='Pass')]
        
        mock_score_instance.predict = mock_predict

        # Set up the async create method
        async def mock_create(**kwargs):
            return mock_score_instance

        mock_score_class.create = mock_create
        
        # Set up the registry's get method to return the mock score class
        def mock_get(score_name):
            return mock_score_class
            
        self.mock_registry.get.side_effect = mock_get

        # Override score_names_to_process to use our simple score
        def mock_score_names_to_process():
            return ['ListResultScore']
        
        original_method = self.scorecard.score_names_to_process
        self.scorecard.score_names_to_process = mock_score_names_to_process

        try:
            # Call the method we're testing
            result = await self.scorecard.score_entire_text(
                text="Sample text",
                metadata={},
                modality="test"
            )
            
            # Assert that the result contains the score
            assert len(result) == 1
            assert result['1'].value == 'Pass'
        finally:
            # Restore the original method
            self.scorecard.score_names_to_process = original_method

if __name__ == '__main__':
    pytest.main()