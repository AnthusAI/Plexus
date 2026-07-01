import unittest
import asyncio
from unittest.mock import Mock, MagicMock, AsyncMock
from plexus.Scorecard import Scorecard
import pytest
import logging
from decimal import Decimal

def create_mock_score_instance():
    """Helper function to create a properly mocked score instance"""
    mock_score_instance = MagicMock()
    
    # Set up the async predict method
    async def mock_predict(*args, **kwargs):
        return Mock(value='Pass')
    mock_score_instance.predict = mock_predict
    
    # Set up the get_accumulated_costs method
    def mock_get_accumulated_costs():
        from decimal import Decimal
        return {
            'prompt_tokens': 100,
            'completion_tokens': 50,
            'cached_tokens': 0,
            'llm_calls': 1,
            'input_cost': Decimal('0.10'),
            'output_cost': Decimal('0.05'),
            'total_cost': Decimal('0.15')
        }
    mock_score_instance.get_accumulated_costs = mock_get_accumulated_costs
    
    return mock_score_instance

# Remove unittest.TestCase since we're using pure pytest style
class TestScorecard:

    def setUp(self):
        # Create a mock scorecard configuration
        self.mock_config = {
            'name': 'TestScorecard',
            'id': 'test-scorecard-123',
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
            # Check if we received a model_input parameter
            model_input = None
            for arg in args:
                if hasattr(arg, 'metadata'):
                    model_input = arg
                    break
            
            for key, value in kwargs.items():
                if key == 'model_input' and hasattr(value, 'metadata'):
                    model_input = value
                    break
            
            # Extract score name from model_input
            score_name = None
            if model_input and hasattr(model_input, 'metadata'):
                score_name = model_input.metadata.get('score_name', '')
            
            # Log for debugging
            logging.info(f"Default mock predict for score: {score_name}")
            
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
            metadata = kwargs.get('metadata', {})
            results = kwargs.get('results', [])
            
            # Important: Add score name to metadata like the real implementation does
            metadata = metadata or {}
            metadata.update({
                'score_name': score_name,
                'scorecard_name': self.mock_config['name']
            })
            
            # Instantiate the score class with the right configuration
            score_class = self.mock_registry.get(score_name)
            score_config = self.mock_registry.get_properties(score_name)
            if score_config:
                score_config = dict(score_config)  # make a copy
                score_config.update({
                    'score_name': score_name,
                    'scorecard_name': self.mock_config['name']
                })
            
            # Create and predict
            score_instance = await score_class.create(**(score_config or {}))
            
            # Call the predict method with the model_input
            from plexus.scores.Score import Score
            result = await score_instance.predict(
                context=None,
                model_input=Score.Input(
                    text=kwargs.get('text', ''),
                    metadata=metadata,
                    results=results
                )
            )
            
            # Return either a single result or a list, same as the real implementation
            if isinstance(result, list):
                return result
            else:
                return [result]
        
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
            'id': 'test-scorecard-123',
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

        # Set up the get_accumulated_costs method
        def mock_get_accumulated_costs():
            from decimal import Decimal
            return {
                'prompt_tokens': 100,
                'completion_tokens': 50,
                'cached_tokens': 0,
                'llm_calls': 1,
                'input_cost': Decimal('0.10'),
                'output_cost': Decimal('0.05'),
                'total_cost': Decimal('0.15')
            }
        
        mock_score_instance.get_accumulated_costs = mock_get_accumulated_costs

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
        
        # Set up the scorecard (use instance properties for API-first approach)
        self.scorecard.properties = dependency_config
        self.scorecard.scores = dependency_config['scores']
        
        # Create a mock score class
        mock_score_class = MagicMock()
        mock_score_instance = MagicMock()
        
        # Set up the async predict method
        async def mock_predict(*args, **kwargs):
            return Mock(value='Pass')
        
        mock_score_instance.predict = mock_predict

        # Set up the get_accumulated_costs method
        def mock_get_accumulated_costs():
            from decimal import Decimal
            return {
                'prompt_tokens': 100,
                'completion_tokens': 50,
                'cached_tokens': 0,
                'llm_calls': 1,
                'input_cost': Decimal('0.10'),
                'output_cost': Decimal('0.05'),
                'total_cost': Decimal('0.15')
            }
        
        mock_score_instance.get_accumulated_costs = mock_get_accumulated_costs

        # Set up the async create method
        async def mock_create(**kwargs):
            mock_score_instance.score_name = kwargs.get('score_name')
            return mock_score_instance

        mock_score_class.create = mock_create
        
        # Set up the registry's get method to return the mock score class
        def mock_get(score_name):
            return mock_score_class
            
        self.mock_registry.get.side_effect = mock_get
        
        # Update the mocks to provide score properties
        def get_properties_side_effect(score_name):
            for score in dependency_config['scores']:
                if score['name'] == score_name:
                    return score
            return None
        self.mock_registry.get_properties.side_effect = get_properties_side_effect
        
        # Create result objects for each score
        from plexus.scores.Score import Score
        score1_result = Score.Result(
            value='Pass', 
            parameters=Score.Parameters(name='Score1')
        )
        score2_result = Score.Result(
            value='Good', 
            parameters=Score.Parameters(name='Score2')
        )
        score3_result = Score.Result(
            value='Great', 
            parameters=Score.Parameters(name='Score3')
        )
        
        # Set up a custom mock for get_score_result that returns our predefined results
        async def mock_get_score_result(*, scorecard, score, text, metadata, modality, results, item=None):
            if score == 'Score1':
                return [score1_result]
            elif score == 'Score2':
                # For score2, we expect score1 results to be passed
                return [score2_result]
            elif score == 'Score3':
                # For score3, we also expect score1 results to be passed
                return [score3_result]

            return [Score.Result(value="Error", error=f"Score not found: {score}")]
        
        self.scorecard.get_score_result = mock_get_score_result

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
    async def test_score_entire_text_adds_dependency_trace_for_information_accuracy_composite(self):
        """Evaluation-path composite results should persist same-run dependency payloads."""
        from plexus.scores.Score import Score

        child_scores = [
            {
                "name": "Information Accuracy: Copay Guarantees",
                "id": "child-1",
                "key": "copay",
            },
            {
                "name": "Information Accuracy: Savings Promises",
                "id": "child-2",
                "key": "savings",
            },
        ]
        composite_name = "Information Accuracy (Composite)"
        dependency_config = {
            "name": "SelectQuote HCS Medium-Risk",
            "id": "59125ba2-670c-4aa5-b796-c2085cf38a0c",
            "key": "selectquote-hcs-medium-risk",
            "scores": [
                *child_scores,
                {
                    "name": composite_name,
                    "id": "258bee07-c6c0-492d-b95f-96581a5cfc6c",
                    "key": "information-accuracy-composite",
                    "version": "version-1",
                    "depends_on": [score["name"] for score in child_scores],
                },
            ],
        }
        self.scorecard.properties = dependency_config
        self.scorecard.scores = dependency_config["scores"]

        def get_properties(score_name):
            for score in dependency_config["scores"]:
                if score["name"] == score_name:
                    return score
            return None

        self.scorecard.score_registry = MagicMock()
        self.scorecard.score_registry.get_properties.side_effect = get_properties

        async def mock_get_score_result(*, scorecard, score, text, metadata, modality, results, item=None):
            if score == "Information Accuracy: Savings Promises":
                return Score.Result(
                    value="No",
                    metadata={"explanation": "Savings promise failed"},
                    parameters=Score.Parameters(name=score),
                )
            if score == composite_name:
                failed = [
                    result.parameters.name
                    for result in results
                    if result.value == "No"
                ]
                return Score.Result(
                    value="No" if failed else "Yes",
                    metadata={
                        "explanation": f"Failed: {', '.join(failed)}",
                        "failed_elements": failed,
                    },
                    parameters=Score.Parameters(name=score),
                )
            return Score.Result(
                value="Yes",
                metadata={"explanation": f"{score} passed"},
                parameters=Score.Parameters(name=score),
            )

        self.scorecard.get_score_result = mock_get_score_result

        result = await self.scorecard.score_entire_text(
            text="Sample text",
            metadata={},
            modality="test",
            subset_of_score_names=[composite_name],
        )

        composite_result = result["258bee07-c6c0-492d-b95f-96581a5cfc6c"]
        trace = composite_result.metadata["trace"]
        assert trace["trace_schema_version"] == "score_result_dependency_v1"
        assert trace["caller_path"] == "scorecard.score_entire_text"
        assert [
            {"name": item["name"], "value": item["value"]}
            for item in trace["composite_input_results"]
        ] == [
            {"name": "Information Accuracy: Copay Guarantees", "value": "Yes"},
            {"name": "Information Accuracy: Savings Promises", "value": "No"},
        ]
        assert trace["integrity_checks"]["child_no_roots"] == [
            "Information Accuracy: Savings Promises"
        ]
        assert trace["integrity_checks"]["failed_elements_match_child_no_roots"] is True

    @pytest.mark.asyncio
    async def test_score_entire_text_skips_failed_conditions(self):
        """Test that scores are skipped when their dependency conditions are not met"""
        # Create the test configuration with a conditional dependency
        cond_dependency_config = {
            'name': 'TestScorecard',
            'scores': [
                {'name': 'Score1', 'id': '1'},
                # Score3 depends on Score1 having the value 'Pass'
                {'name': 'Score3', 'id': '3', 'depends_on': {'Score1': {'operator': '==', 'value': 'Pass'}}}
            ]
        }
        
        # Set up the scorecard (use instance properties for API-first approach)
        self.scorecard.properties = cond_dependency_config
        self.scorecard.scores = cond_dependency_config['scores']
        
        # Create a mock score class
        mock_score_class = MagicMock()
        mock_score_instance = MagicMock()
        
        # Set up the async predict method
        async def mock_predict(*args, **kwargs):
            return Mock(value='Pass')
        
        mock_score_instance.predict = mock_predict

        # Set up the get_accumulated_costs method
        def mock_get_accumulated_costs():
            from decimal import Decimal
            return {
                'prompt_tokens': 100,
                'completion_tokens': 50,
                'cached_tokens': 0,
                'llm_calls': 1,
                'input_cost': Decimal('0.10'),
                'output_cost': Decimal('0.05'),
                'total_cost': Decimal('0.15')
            }
        
        mock_score_instance.get_accumulated_costs = mock_get_accumulated_costs

        # Set up the async create method
        async def mock_create(**kwargs):
            mock_score_instance.score_name = kwargs.get('score_name')
            return mock_score_instance

        mock_score_class.create = mock_create
        
        # Set up the registry's get method to return the mock score class
        def mock_get(score_name):
            return mock_score_class
            
        self.mock_registry.get.side_effect = mock_get
        
        # Update the mocks to provide score properties
        def get_properties_side_effect(score_name):
            for score in cond_dependency_config['scores']:
                if score['name'] == score_name:
                    return score
            return None
        self.mock_registry.get_properties.side_effect = get_properties_side_effect
        
        # Create result objects for each score
        from plexus.scores.Score import Score
        # Critical: Score1 must have 'Fail' value to trigger the condition check
        score1_result = Score.Result(
            value='Fail', 
            parameters=Score.Parameters(name='Score1')
        )
        score3_result = Score.Result(
            value='Pass', 
            parameters=Score.Parameters(name='Score3')
        )
        
        # Set up a custom mock for get_score_result
        async def mock_get_score_result(*, scorecard, score, text, metadata, modality, results, item=None):
            if score == 'Score1':
                return [score1_result]  # Return Fail to trigger condition check
            elif score == 'Score3':
                # This should never be called due to dependency condition
                return [score3_result]

            return [Score.Result(value="Error", error=f"Score not found: {score}")]
        
        self.scorecard.get_score_result = mock_get_score_result

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
        assert '3' in result  # Score3 should be included with SKIPPED status
        assert result['3'] == 'SKIPPED'  # Score3 should be skipped

    @pytest.mark.asyncio
    async def test_score_entire_text_handles_single_result(self):
        """Test that score_entire_text correctly handles a single Result object"""
        # Create a simple config without dependencies for this test
        simple_config = {
            'name': 'TestScorecard',
            'id': 'test-scorecard-123',
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

        # Set up the get_accumulated_costs method
        def mock_get_accumulated_costs():
            from decimal import Decimal
            return {
                'prompt_tokens': 100,
                'completion_tokens': 50,
                'cached_tokens': 0,
                'llm_calls': 1,
                'input_cost': Decimal('0.10'),
                'output_cost': Decimal('0.05'),
                'total_cost': Decimal('0.15')
            }
        
        mock_score_instance.get_accumulated_costs = mock_get_accumulated_costs

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
            'id': 'test-scorecard-123',
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

        # Set up the get_accumulated_costs method
        def mock_get_accumulated_costs():
            from decimal import Decimal
            return {
                'prompt_tokens': 100,
                'completion_tokens': 50,
                'cached_tokens': 0,
                'llm_calls': 1,
                'input_cost': Decimal('0.10'),
                'output_cost': Decimal('0.05'),
                'total_cost': Decimal('0.15')
            }
        
        mock_score_instance.get_accumulated_costs = mock_get_accumulated_costs

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

    @pytest.mark.asyncio
    async def test_score_entire_text_handles_float_costs(self):
        """Regression: float cost values should be accumulated into Decimal totals."""
        simple_config = {
            'name': 'TestScorecard',
            'id': 'test-scorecard-123',
            'scores': [
                {'name': 'FloatCostScore', 'id': 1}
            ]
        }
        self.scorecard.properties = simple_config
        self.scorecard.scores = simple_config['scores']

        def get_properties_side_effect(score_name):
            for score in simple_config['scores']:
                if score['name'] == score_name:
                    return score
            return None
        self.mock_registry.get_properties.side_effect = get_properties_side_effect

        mock_score_class = MagicMock()
        mock_score_instance = MagicMock()

        async def mock_predict(*args, **kwargs):
            return Mock(value='Pass')

        mock_score_instance.predict = mock_predict

        def mock_get_accumulated_costs():
            return {
                'prompt_tokens': 100,
                'completion_tokens': 50,
                'cached_tokens': 0,
                'llm_calls': 1,
                'input_cost': 0.10,
                'output_cost': 0.05,
                'total_cost': 0.15,
                'cost_per_text': 0.15,
            }

        mock_score_instance.get_accumulated_costs = mock_get_accumulated_costs

        async def mock_create(**kwargs):
            return mock_score_instance

        mock_score_class.create = mock_create
        self.mock_registry.get.side_effect = lambda score_name: mock_score_class

        # Use the real implementation so we exercise cost accumulation behavior.
        original_get_score_result = self.scorecard.get_score_result
        self.scorecard.get_score_result = Scorecard.get_score_result.__get__(self.scorecard, Scorecard)
        original_method = self.scorecard.score_names_to_process
        self.scorecard.score_names_to_process = lambda: ['FloatCostScore']

        try:
            result = await self.scorecard.score_entire_text(
                text="Sample text",
                metadata={},
                modality="test"
            )
            assert len(result) == 1
            assert self.scorecard.input_cost == Decimal("0.1")
            assert self.scorecard.output_cost == Decimal("0.05")
            assert self.scorecard.total_cost == Decimal("0.15")
        finally:
            self.scorecard.score_names_to_process = original_method
            self.scorecard.get_score_result = original_get_score_result

    @pytest.mark.asyncio
    async def test_score_entire_text_runs_independent_scores_in_parallel(self):
        simple_config = {
            'name': 'TestScorecard',
            'id': 'test-scorecard-123',
            'scores': [
                {'name': 'ParallelScore1', 'id': 1},
                {'name': 'ParallelScore2', 'id': 2},
            ]
        }
        self.scorecard.properties = simple_config
        self.scorecard.scores = simple_config['scores']

        def get_properties_side_effect(score_name):
            for score in simple_config['scores']:
                if score['name'] == score_name:
                    return score
            return None

        self.mock_registry.get_properties.side_effect = get_properties_side_effect

        in_flight = 0
        max_in_flight = 0
        lock = asyncio.Lock()

        async def mock_get_score_result(*_args, **_kwargs):
            nonlocal in_flight, max_in_flight
            async with lock:
                in_flight += 1
                max_in_flight = max(max_in_flight, in_flight)
            await asyncio.sleep(0.05)
            async with lock:
                in_flight -= 1
            return [Mock(value='Pass')]

        original_get_score_result = self.scorecard.get_score_result
        original_score_names = self.scorecard.score_names_to_process
        self.scorecard.get_score_result = mock_get_score_result
        self.scorecard.score_names_to_process = lambda: ['ParallelScore1', 'ParallelScore2']

        import os
        original_parallelism = os.environ.get('PLEXUS_SCORECARD_MAX_CONCURRENT_SCORES')
        os.environ['PLEXUS_SCORECARD_MAX_CONCURRENT_SCORES'] = '4'

        try:
            result = await self.scorecard.score_entire_text(
                text="Sample text",
                metadata={},
                modality="test"
            )
            assert len(result) == 2
            assert max_in_flight >= 2
        finally:
            self.scorecard.get_score_result = original_get_score_result
            self.scorecard.score_names_to_process = original_score_names
            if original_parallelism is None:
                os.environ.pop('PLEXUS_SCORECARD_MAX_CONCURRENT_SCORES', None)
            else:
                os.environ['PLEXUS_SCORECARD_MAX_CONCURRENT_SCORES'] = original_parallelism

    @pytest.mark.asyncio
    async def test_get_score_result_cleans_up_score_instance(self):
        """Regression: score instances should be cleaned up after each execution."""
        simple_config = {
            'name': 'TestScorecard',
            'id': 'test-scorecard-123',
            'scores': [
                {'name': 'CleanupScore', 'id': 1}
            ]
        }
        self.scorecard.properties = simple_config
        self.scorecard.scores = simple_config['scores']

        def get_properties_side_effect(score_name):
            for score in simple_config['scores']:
                if score['name'] == score_name:
                    return score
            return None
        self.mock_registry.get_properties.side_effect = get_properties_side_effect

        mock_score_class = MagicMock()
        mock_score_instance = MagicMock()
        cleanup_mock = AsyncMock()

        async def mock_predict(*args, **kwargs):
            return Mock(value='Pass')

        mock_score_instance.predict = mock_predict
        mock_score_instance.cleanup = cleanup_mock
        mock_score_instance.get_accumulated_costs = lambda: {
            'prompt_tokens': 0,
            'completion_tokens': 0,
            'cached_tokens': 0,
            'llm_calls': 0,
            'input_cost': Decimal('0'),
            'output_cost': Decimal('0'),
            'total_cost': Decimal('0'),
        }

        async def mock_create(**kwargs):
            return mock_score_instance

        mock_score_class.create = mock_create
        self.mock_registry.get.side_effect = lambda score_name: mock_score_class

        result = await Scorecard.get_score_result(
            self.scorecard,
            scorecard='TestScorecard',
            score='CleanupScore',
            text='Sample text',
            metadata={},
            modality='test',
            results=[],
        )

        assert len(result) == 1
        assert result[0].value == 'Pass'
        cleanup_mock.assert_awaited_once()

if __name__ == '__main__':
    pytest.main()
