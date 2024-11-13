import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from plexus.scores.LangGraphScore import LangGraphScore
from plexus.scores.Score import Score
from typing import Optional
from pydantic import BaseModel, Field, ConfigDict

# Set the default fixture loop scope to function
pytest.asyncio_fixture_scope = "function"
pytest_plugins = ('pytest_asyncio',)

class MockGraphState(BaseModel):
    model_config = ConfigDict(arbitrary_types_allowed=True)  # Use ConfigDict instead of Config class
    
    classification: Optional[str]
    explanation: Optional[str]
    retry_count: Optional[int] = Field(default=0)
    text: Optional[str]
    metadata: Optional[dict]
    results: Optional[dict]

@pytest.fixture
def basic_graph_config():
    return {
        "graph": [
            {
                "name": "classifier",
                "class": "YesOrNoClassifier",
                "prompt_template": "Is this text positive? {text}",
                "output": {
                    "value": "classification",
                    "explanation": "explanation"
                }
            }
        ],
        "model_provider": "AzureChatOpenAI",
        "model_name": "gpt-4",
        "temperature": 0.0,
        "openai_api_version": "2023-05-15",
        "openai_api_base": "https://test.openai.azure.com",
        "openai_api_key": "test-key",
        "output": {
            "value": "classification",
            "explanation": "explanation"
        }
    }

@pytest.fixture
async def mock_azure_openai():
    """Create a mock Azure OpenAI client with async capabilities"""
    mock = AsyncMock()
    mock.with_config = MagicMock(return_value=mock)
    mock.ainvoke = AsyncMock()
    return mock

@pytest.fixture
async def mock_yes_no_classifier():
    """Create a mock YesNoClassifier with async capabilities"""
    with patch('plexus.scores.nodes.YesOrNoClassifier') as mock:
        mock_instance = AsyncMock()
        mock_instance.GraphState = MagicMock()
        mock_instance.GraphState.__annotations__ = {
            'text': str,
            'metadata': Optional[dict],
            'results': Optional[dict],
            'value': Optional[str],
            'explanation': Optional[str],
            'classification': Optional[str]
        }
        mock.return_value = mock_instance
        yield mock_instance

@pytest.fixture
def mock_workflow():
    """Create a proper mock workflow"""
    mock = AsyncMock()
    mock.ainvoke = AsyncMock(return_value={
        "value": "Yes",
        "explanation": "Test explanation"
    })
    return mock

@pytest.mark.asyncio
async def test_create_instance(basic_graph_config, mock_azure_openai, mock_yes_no_classifier):
    with patch('plexus.LangChainUser.LangChainUser._initialize_model', return_value=mock_azure_openai):
        instance = await LangGraphScore.create(**basic_graph_config)
        assert isinstance(instance, LangGraphScore)
        assert instance.parameters.model_provider == "AzureChatOpenAI"
        assert instance.parameters.model_name == "gpt-4"

@pytest.mark.asyncio
async def test_predict_basic_flow(basic_graph_config, mock_azure_openai, mock_yes_no_classifier, mock_workflow):
    with patch('plexus.LangChainUser.LangChainUser._initialize_model', return_value=mock_azure_openai):
        instance = await LangGraphScore.create(**basic_graph_config)
        instance.workflow = mock_workflow
        
        input_data = Score.Input(
            text="This is a test text",
            metadata={},
            results=[]
        )
        
        mock_workflow.ainvoke.return_value = {"value": "Yes", "explanation": "Test explanation"}
        
        results = await instance.predict(None, input_data)
        
        assert len(results) == 1
        assert results[0].value == "Yes"
        assert results[0].explanation == "Test explanation"

@pytest.mark.asyncio
async def test_predict_with_list_text(basic_graph_config, mock_azure_openai, mock_yes_no_classifier, mock_workflow):
    with patch('plexus.LangChainUser.LangChainUser._initialize_model', return_value=mock_azure_openai):
        instance = await LangGraphScore.create(**basic_graph_config)
        instance.workflow = mock_workflow
        
        text = " ".join(["This is", "a test", "text"])
        input_data = Score.Input(
            text=text,
            metadata={},
            results=[]
        )
        
        mock_workflow.ainvoke.return_value = {"value": "No", "explanation": "Test explanation"}
        
        results = await instance.predict(None, input_data)
        
        assert len(results) == 1
        assert results[0].value == "No"
        mock_workflow.ainvoke.assert_called_with({
            "text": "This is a test text",
            "metadata": {},
            "results": {}
        })

@pytest.mark.asyncio
async def test_get_token_usage(basic_graph_config, mock_azure_openai, mock_yes_no_classifier):
    with patch('plexus.LangChainUser.LangChainUser._initialize_model', return_value=mock_azure_openai):
        instance = await LangGraphScore.create(**basic_graph_config)
        
        instance.node_instances = [
            ("node1", MagicMock(get_token_usage=lambda: {
                "prompt_tokens": 10,
                "completion_tokens": 5,
                "total_tokens": 15,
                "successful_requests": 1,
                "cached_tokens": 0
            })),
            ("node2", MagicMock(get_token_usage=lambda: {
                "prompt_tokens": 20,
                "completion_tokens": 10,
                "total_tokens": 30,
                "successful_requests": 2,
                "cached_tokens": 0
            }))
        ]
        
        usage = instance.get_token_usage()
        
        assert usage["prompt_tokens"] == 30
        assert usage["completion_tokens"] == 15
        assert usage["total_tokens"] == 45
        assert usage["successful_requests"] == 3
        assert usage["cached_tokens"] == 0

@pytest.mark.asyncio
async def test_reset_token_usage(basic_graph_config, mock_azure_openai, mock_yes_no_classifier):
    with patch('plexus.LangChainUser.LangChainUser._initialize_model', return_value=mock_azure_openai):
        instance = await LangGraphScore.create(**basic_graph_config)
        
        # Create a proper mock model
        mock_model = MagicMock()
        mock_model.with_config = MagicMock(return_value=mock_model)
        mock_model.ainvoke = AsyncMock()
        instance.model = mock_model
        
        instance.reset_token_usage()
        
        if instance.parameters.model_provider in ["AzureChatOpenAI", "ChatOpenAI"]:
            assert instance.openai_callback is not None
            mock_model.with_config.assert_called_once()

@pytest.mark.asyncio
async def test_conditional_graph_flow(basic_graph_config, mock_azure_openai, mock_yes_no_classifier, mock_workflow):
    """Test a graph with conditional branching logic"""
    config = basic_graph_config.copy()
    config["graph"] = [
        {
            "name": "classifier",
            "class": "YesOrNoClassifier",
            "prompt_template": "Is this text positive? {text}",
            "conditions": [
                {
                    "state": "value",
                    "value": "Yes",
                    "node": "positive_handler",
                    "output": {"value": "Positive", "explanation": "Handled positive case"}
                },
                {
                    "state": "value",
                    "value": "No",
                    "node": "END",
                    "output": {"value": "Negative", "explanation": "Terminated on negative"}
                }
            ]
        },
        {
            "name": "positive_handler",
            "class": "YesOrNoClassifier",
            "prompt_template": "Is this text positive? {text}"
        }
    ]

    with patch('plexus.LangChainUser.LangChainUser._initialize_model', return_value=mock_azure_openai):
        instance = await LangGraphScore.create(**config)
        instance.workflow = mock_workflow
        
        # Test positive path
        mock_workflow.ainvoke.return_value = {"value": "Positive", "explanation": "Handled positive case"}
        result = await instance.predict(None, Score.Input(text="test", metadata={}, results=[]))
        assert result[0].value == "Positive"
        assert result[0].explanation == "Handled positive case"

        # Test negative path
        mock_workflow.ainvoke.return_value = {"value": "Negative", "explanation": "Terminated on negative"}
        result = await instance.predict(None, Score.Input(text="test", metadata={}, results=[]))
        assert result[0].value == "Negative"

@pytest.mark.asyncio
async def test_input_output_aliasing(basic_graph_config, mock_azure_openai, mock_yes_no_classifier, mock_workflow):
    """Test input and output aliasing functionality"""
    config = basic_graph_config.copy()
    config["input"] = {"input_text": "text"}
    config["output"] = {"final_result": "value", "final_explanation": "explanation"}
    
    with patch('plexus.LangChainUser.LangChainUser._initialize_model', return_value=mock_azure_openai):
        instance = await LangGraphScore.create(**config)
        instance.workflow = mock_workflow
        
        mock_workflow.ainvoke.return_value = {
            "value": "Yes",
            "explanation": "Test explanation",
            "final_result": "Yes",
            "final_explanation": "Test explanation"
        }
        
        results = await instance.predict(None, Score.Input(text="test", metadata={}, results=[]))
        assert results[0].value == "Yes"
        assert "Test explanation" in results[0].explanation

@pytest.mark.asyncio
async def test_graph_with_previous_results(
    basic_graph_config,
    mock_azure_openai,
    mock_yes_no_classifier,
    mock_workflow
):
    """Test processing with previous results in the input"""
    with patch(
        'plexus.LangChainUser.LangChainUser._initialize_model',
        return_value=mock_azure_openai
    ):
        instance = await LangGraphScore.create(**basic_graph_config)
        instance.workflow = mock_workflow

        # Create a proper Result object with explanation using LangGraphScore.Result
        previous_result = LangGraphScore.Result(
            parameters=basic_graph_config,
            value="Yes",
            explanation="Previous explanation"
        )

        previous_results = [
            {
                "name": "previous_score",
                "id": "123",
                "result": previous_result  # Use LangGraphScore.Result object instead of dict
            }
        ]

        input_data = Score.Input(
            text="test",
            metadata={},
            results=previous_results
        )

        mock_workflow.ainvoke.return_value = {"value": "Yes", "explanation": "New explanation"}
        results = await instance.predict(None, input_data)

        # Verify the workflow was called with correct data
        mock_workflow.ainvoke.assert_called_with({
            "text": "test",
            "metadata": {},
            "results": {
                "previous_score": {
                    "id": "123",
                    "value": "Yes",
                    "explanation": "Previous explanation"
                }
            }
        })

@pytest.mark.xfail(reason="Need to fix error handling flow")
@pytest.mark.asyncio
async def test_invalid_graph_configurations():
    """Test various invalid graph configurations"""
    test_cases = [
        (
            {
                "model_provider": "AzureChatOpenAI",
                "model_name": "gpt-4"
                # Missing graph configuration
            },
            ValueError,
            "Invalid or missing graph configuration in parameters."
        ),
        (
            {
                "model_provider": "AzureChatOpenAI",
                "model_name": "gpt-4",
                "graph": [{
                    "name": "classifier",
                    "class": "NonExistentClassifier"
                }]
            },
            AttributeError,
            "module 'plexus.scores.nodes' has no attribute 'NonExistentClassifier'"
        ),
        (
            {
                "model_provider": "AzureChatOpenAI",
                "model_name": "gpt-4",
                "graph": [],
                "output": {
                    "value": "value",
                    "explanation": "explanation"
                }
            },
            ValueError,
            "Graph configuration cannot be empty"
        ),
        (
            {
                "model_provider": "AzureChatOpenAI",
                "model_name": "gpt-4",
                "graph": [{
                    "name": "classifier",
                    "class": "YesOrNoClassifier",
                    "conditions": "invalid_conditions"  # Should be a list
                }]
            },
            ValueError,
            "Conditions must be a list"
        )
    ]
    
    for config, expected_error, expected_message in test_cases:
        with pytest.raises(expected_error, match=expected_message):
            with patch('plexus.LangChainUser.LangChainUser._initialize_model', return_value=AsyncMock()):
                await LangGraphScore.create(**config)

@pytest.mark.asyncio
async def test_malformed_input_handling(basic_graph_config, mock_azure_openai, mock_yes_no_classifier, mock_workflow):
    """Test handling of malformed input data"""
    with patch('plexus.LangChainUser.LangChainUser._initialize_model', return_value=mock_azure_openai):
        instance = await LangGraphScore.create(**basic_graph_config)
        instance.workflow = mock_workflow
        
        # Test with None text
        with pytest.raises(ValueError):
            await instance.predict(None, Score.Input(text=None, metadata={}, results=[]))
        
        # Test with empty text
        mock_workflow.ainvoke.return_value = {"value": "", "explanation": "Empty input"}
        result = await instance.predict(None, Score.Input(text="", metadata={}, results=[]))
        assert result[0].value == ""

@pytest.mark.asyncio
async def test_token_usage_error_handling(basic_graph_config, mock_azure_openai, mock_yes_no_classifier):
    """Test token usage calculation when API calls fail"""
    with patch('plexus.LangChainUser.LangChainUser._initialize_model', return_value=mock_azure_openai):
        instance = await LangGraphScore.create(**basic_graph_config)
        
        # Mock node that raises an exception during token usage calculation
        error_node = MagicMock()
        error_node.get_token_usage.side_effect = Exception("API Error")
        
        normal_node = MagicMock()
        normal_node.get_token_usage.return_value = {
            "prompt_tokens": 10,
            "completion_tokens": 5,
            "total_tokens": 15,
            "successful_requests": 1,
            "cached_tokens": 0
        }
        
        # Set node instances in reverse order to test error handling
        instance.node_instances = [
            ("normal_node", normal_node),
            ("error_node", error_node)
        ]
        
        # Should handle errors gracefully and return partial usage data
        usage = instance.get_token_usage()
        assert usage["prompt_tokens"] == 10
        assert usage["completion_tokens"] == 5
        assert usage["total_tokens"] == 15

@pytest.mark.asyncio
async def test_state_management(basic_graph_config, mock_azure_openai, mock_workflow):
    """Test state management and propagation between nodes"""
    with patch('plexus.LangChainUser.LangChainUser._initialize_model',
              return_value=mock_azure_openai):
        instance = await LangGraphScore.create(**basic_graph_config)
        instance.workflow = mock_workflow
        
        # Mock workflow response
        mock_workflow.ainvoke.return_value = {
            "text": "test text",
            "metadata": {"key": "value"},
            "value": "Yes",
            "explanation": "Test explanation",
            "classification": "Yes"
        }
        
        # Test state propagation
        result = await instance.predict(None, Score.Input(
            text="test text",
            metadata={"key": "value"},
            results=[]
        ))
        
        assert result[0].value == "Yes"
        assert result[0].explanation == "Test explanation"

@pytest.mark.asyncio
async def test_combined_graphstate_creation(basic_graph_config, mock_azure_openai):
    """Test creation of combined GraphState class"""
    with patch('plexus.LangChainUser.LangChainUser._initialize_model', return_value=mock_azure_openai):
        instance = await LangGraphScore.create(**basic_graph_config)
        
        # Create test node instances with different GraphState attributes
        class TestNode1:
            class GraphState(BaseModel):
                attr1: str
                attr2: int
                classification: Optional[str]
                explanation: Optional[str]
                parameters: Optional[dict] = None

            parameters = MagicMock(output=None)

        class TestNode2:
            class GraphState(BaseModel):
                attr3: bool
                attr4: Optional[dict]
                classification: Optional[str]
                explanation: Optional[str]
                parameters: Optional[dict] = None

            parameters = MagicMock(output=None)

        node_instances = [
            ("node1", TestNode1()),
            ("node2", TestNode2())
        ]
        
        # Test combined GraphState creation
        combined_state = instance.create_combined_graphstate_class(
            [node for _, node in node_instances])
        
        # Verify attributes are present
        assert "attr1" in combined_state.__annotations__
        assert "attr2" in combined_state.__annotations__
        assert "attr3" in combined_state.__annotations__
        assert "attr4" in combined_state.__annotations__
        assert "classification" in combined_state.__annotations__
        assert "explanation" in combined_state.__annotations__