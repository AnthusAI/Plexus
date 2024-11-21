import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from plexus.scores.LangGraphScore import LangGraphScore, BatchProcessingPause
from plexus.scores.Score import Score
from typing import Optional
from pydantic import BaseModel, Field, ConfigDict
import logging

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

class AsyncIteratorMock:
    """Mock async iterator for testing"""
    def __init__(self, seq):
        self.iter = iter(seq)

    def __aiter__(self):
        return self

    async def __anext__(self):
        try:
            return next(self.iter)
        except StopIteration:
            raise StopAsyncIteration

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
async def test_predict_basic_flow(basic_graph_config, mock_azure_openai):
    """Test basic prediction flow"""
    with patch('plexus.LangChainUser.LangChainUser._initialize_model', 
               return_value=mock_azure_openai):
        instance = await LangGraphScore.create(**basic_graph_config)
        
        # Create the iterator first
        iterator = AsyncIteratorMock([{
            "value": "Yes",
            "explanation": "Test explanation"
        }])
        
        # Mock workflow with a simple async function that returns the iterator
        mock_workflow = MagicMock()
        mock_workflow.astream = MagicMock(return_value=iterator)
        instance.workflow = mock_workflow
        
        input_data = Score.Input(
            text="This is a test text",
            metadata={},
            results=[]
        )
        
        # Add debug logging
        logging.info(f"Iterator type: {type(iterator)}")
        logging.info(f"Has __aiter__: {hasattr(iterator, '__aiter__')}")
        logging.info(f"Has __anext__: {hasattr(iterator, '__anext__')}")
        
        results = await instance.predict(None, input_data)
        
        assert len(results) == 1
        assert results[0].value == "Yes"
        assert results[0].explanation == "Test explanation"

@pytest.mark.asyncio
async def test_predict_with_list_text(basic_graph_config, mock_azure_openai):
    """Test processing with list text input"""
    with patch('plexus.LangChainUser.LangChainUser._initialize_model', 
               return_value=mock_azure_openai):
        instance = await LangGraphScore.create(**basic_graph_config)
        
        # Mock workflow
        mock_workflow = MagicMock()
        mock_workflow.astream = MagicMock(return_value=AsyncIteratorMock([{
            "value": "No",
            "explanation": "Test explanation"
        }]))
        instance.workflow = mock_workflow
        
        text = " ".join(["This is", "a test", "text"])
        input_data = Score.Input(
            text=text,
            metadata={},
            results=[]
        )
        
        results = await instance.predict(None, input_data)
        
        assert len(results) == 1
        assert results[0].value == "No"

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
async def test_conditional_graph_flow(basic_graph_config, mock_azure_openai):
    """Test a graph with conditional branching logic"""
    config = basic_graph_config.copy()
    graph_config = [
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
    config["graph"] = graph_config

    with patch('plexus.LangChainUser.LangChainUser._initialize_model', 
               return_value=mock_azure_openai):
        instance = await LangGraphScore.create(**config)
        
        # Test positive path
        mock_workflow = MagicMock()
        mock_workflow.astream = MagicMock(return_value=AsyncIteratorMock([{
            "value": "Positive",
            "explanation": "Handled positive case"
        }]))
        instance.workflow = mock_workflow
        
        result = await instance.predict(None, Score.Input(
            text="test",
            metadata={},
            results=[]
        ))
        assert result[0].value == "Positive"
        assert result[0].explanation == "Handled positive case"

        # Test negative path
        mock_workflow.astream = MagicMock(return_value=AsyncIteratorMock([{
            "value": "Negative",
            "explanation": "Terminated on negative"
        }]))
        
        result = await instance.predict(None, Score.Input(
            text="test",
            metadata={},
            results=[]
        ))
        assert result[0].value == "Negative"

@pytest.mark.asyncio
async def test_input_output_aliasing(basic_graph_config, mock_azure_openai, mock_yes_no_classifier):
    """Test input and output aliasing functionality"""
    config = basic_graph_config.copy()
    config["input"] = {"input_text": "text"}
    config["output"] = {"final_result": "value", "final_explanation": "explanation"}
    
    with patch('plexus.LangChainUser.LangChainUser._initialize_model', 
               return_value=mock_azure_openai):
        instance = await LangGraphScore.create(**config)
        
        # Mock workflow
        mock_workflow = MagicMock()
        mock_workflow.astream = MagicMock(return_value=AsyncIteratorMock([{
            "value": "Yes",
            "explanation": "Test explanation",
            "final_result": "Yes",
            "final_explanation": "Test explanation"
        }]))
        instance.workflow = mock_workflow
        
        results = await instance.predict(None, Score.Input(
            text="test",
            metadata={},
            results=[]
        ))
        assert results[0].value == "Yes"
        assert "Test explanation" in results[0].explanation

@pytest.mark.asyncio
async def test_graph_with_previous_results(basic_graph_config, mock_azure_openai):
    """Test processing with previous results in the input"""
    with patch('plexus.LangChainUser.LangChainUser._initialize_model',
               return_value=mock_azure_openai):
        instance = await LangGraphScore.create(**basic_graph_config)

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
                "result": previous_result
            }
        ]

        input_data = Score.Input(
            text="test",
            metadata={},
            results=previous_results
        )

        # Mock workflow with AsyncIteratorMock
        mock_workflow = MagicMock()
        mock_workflow.astream = MagicMock(return_value=AsyncIteratorMock([{
            "value": "Yes",
            "explanation": "New explanation"
        }]))
        instance.workflow = mock_workflow

        results = await instance.predict(None, input_data)
        assert results[0].value == "Yes"
        assert results[0].explanation == "New explanation"

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
async def test_malformed_input_handling(basic_graph_config, mock_azure_openai):
    """Test handling of malformed input data"""
    with patch('plexus.LangChainUser.LangChainUser._initialize_model', 
               return_value=mock_azure_openai):
        instance = await LangGraphScore.create(**basic_graph_config)
        
        # Mock workflow
        mock_workflow = MagicMock()
        mock_workflow.astream = MagicMock(return_value=AsyncIteratorMock([{
            "value": "",
            "explanation": "Empty input"
        }]))
        instance.workflow = mock_workflow
        
        # Test with empty text
        result = await instance.predict(None, Score.Input(
            text="",
            metadata={},
            results=[]
        ))
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
async def test_state_management(basic_graph_config, mock_azure_openai):
    """Test state management and propagation between nodes"""
    with patch('plexus.LangChainUser.LangChainUser._initialize_model',
               return_value=mock_azure_openai):
        instance = await LangGraphScore.create(**basic_graph_config)
        
        # Mock workflow
        mock_workflow = MagicMock()
        mock_workflow.astream = MagicMock(return_value=AsyncIteratorMock([{
            "text": "test text",
            "metadata": {"key": "value"},
            "value": "Yes",
            "explanation": "Test explanation",
            "classification": "Yes"
        }]))
        instance.workflow = mock_workflow
        
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

@pytest.mark.asyncio
async def test_batch_processing_pause_basic(basic_graph_config, mock_azure_openai):
    """Test that workflow correctly pauses at LLM breakpoint"""
    with patch('plexus.LangChainUser.LangChainUser._initialize_model', 
               return_value=mock_azure_openai):
        instance = await LangGraphScore.create(**basic_graph_config)
        
        # Mock workflow
        mock_workflow = MagicMock()
        mock_workflow.astream = MagicMock(return_value=AsyncIteratorMock([{
            "text": "test text",
            "metadata": {},
            "at_llm_breakpoint": True,
            "messages": [{"type": "human", "content": "test"}],
            "thread_id": "test-thread"
        }]))
        instance.workflow = mock_workflow
        
        with pytest.raises(BatchProcessingPause) as exc_info:
            await instance.predict(None, Score.Input(
                text="test text",
                metadata={},
                results=[]
            ))
        
        assert exc_info.value.thread_id is not None
        assert exc_info.value.state["at_llm_breakpoint"] is True
        assert exc_info.value.state["messages"] is not None

@pytest.mark.asyncio
async def test_batch_processing_resume(basic_graph_config, mock_azure_openai):
    """Test resuming workflow after a pause"""
    with patch('plexus.LangChainUser.LangChainUser._initialize_model', 
               return_value=mock_azure_openai):
        # Add thread_id to config instead of passing it to predict
        config = basic_graph_config.copy()
        config["thread_id"] = "test-thread"
        instance = await LangGraphScore.create(**config)
        
        # Mock workflow
        mock_workflow = MagicMock()
        call_count = 0
        
        def get_mock_iterator(*args, **kwargs):
            nonlocal call_count
            if call_count == 0:
                call_count += 1
                return AsyncIteratorMock([{
                    "text": "test text",
                    "metadata": {},
                    "at_llm_breakpoint": True,
                    "messages": [{"type": "human", "content": "test"}],
                    "thread_id": "test-thread"
                }])
            else:
                return AsyncIteratorMock([{
                    "text": "test text",
                    "metadata": {},
                    "messages": [{"type": "human", "content": "test"}],
                    "thread_id": "test-thread",
                    "at_llm_breakpoint": False,
                    "completion": "test completion",
                    "classification": "Yes",
                    "explanation": "test explanation"
                }])
        
        mock_workflow.astream = MagicMock(side_effect=get_mock_iterator)
        instance.workflow = mock_workflow
        
        # First call should pause
        with pytest.raises(BatchProcessingPause) as exc_info:
            await instance.predict(None, Score.Input(
                text="test text",
                metadata={},
                results=[]
            ))
        
        # Save state from pause
        paused_state = exc_info.value.state
        
        # Resume with saved state (no thread_id parameter)
        results = await instance.predict(
            None, 
            Score.Input(
                text=paused_state["text"],
                metadata=paused_state["metadata"],
                results=[]
            )
        )
        
        assert len(results) == 1
        assert results[0].value == "Yes"
        assert results[0].explanation == "test explanation"

@pytest.mark.asyncio
async def test_batch_processing_cleanup(basic_graph_config, mock_azure_openai):
    """Test cleanup is called when workflow pauses"""
    with patch('plexus.LangChainUser.LangChainUser._initialize_model', 
               return_value=mock_azure_openai):
        instance = await LangGraphScore.create(**basic_graph_config)
        
        # Mock workflow and cleanup
        mock_workflow = AsyncMock()
        async def mock_astream(*args, **kwargs):
            yield {
                "at_llm_breakpoint": True,
                "thread_id": "test-thread"
            }
        mock_workflow.astream = mock_astream
        instance.workflow = mock_workflow
        
        cleanup_called = False
        async def mock_cleanup():
            nonlocal cleanup_called
            cleanup_called = True
        instance.cleanup = mock_cleanup
        
        # Should call cleanup when pausing
        with pytest.raises(BatchProcessingPause):
            await instance.predict(None, Score.Input(
                text="test",
                metadata={},
                results=[]
            ))
        
        assert cleanup_called is True

@pytest.mark.asyncio
async def test_batch_processing_with_checkpointer(basic_graph_config, mock_azure_openai):
    """Test pause/resume with PostgreSQL checkpointer"""
    # Mock PostgreSQL checkpointer
    mock_checkpointer = AsyncMock()
    mock_checkpointer.setup = AsyncMock()
    mock_checkpointer.get_tuple = AsyncMock()
    mock_checkpointer.put = AsyncMock()
    mock_checkpointer_context = AsyncMock()
    mock_checkpointer_context.__aenter__ = AsyncMock(return_value=mock_checkpointer)
    mock_checkpointer_context.__aexit__ = AsyncMock()
    
    with patch('plexus.LangChainUser.LangChainUser._initialize_model', 
               return_value=mock_azure_openai), \
         patch('langgraph.checkpoint.postgres.aio.AsyncPostgresSaver.from_conn_string',
               return_value=mock_checkpointer_context):
        
        # Configure with PostgreSQL URL
        config = basic_graph_config.copy()
        config["postgres_url"] = "postgresql://test:test@localhost:5432/test"
        
        instance = await LangGraphScore.create(**config)
        
        # Mock workflow with AsyncIteratorMock
        mock_workflow = MagicMock()
        mock_workflow.astream = MagicMock(return_value=AsyncIteratorMock([{
            "at_llm_breakpoint": True,
            "thread_id": "test-thread"
        }]))
        instance.workflow = mock_workflow
        
        # Should initialize checkpointer
        assert instance.checkpointer is mock_checkpointer
        mock_checkpointer.setup.assert_called_once()
        
        # Should cleanup checkpointer on pause
        with pytest.raises(BatchProcessingPause):
            await instance.predict(None, Score.Input(
                text="test",
                metadata={},
                results=[]
            ))
        
        mock_checkpointer_context.__aexit__.assert_called_once()