import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from plexus.scores.LangGraphScore import LangGraphScore, BatchProcessingPause
from plexus.scores.Score import Score
from typing import Optional
from pydantic import BaseModel, Field, ConfigDict
import logging
import os

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

@pytest.mark.skip(reason="Needs update: state handling has changed significantly")
@pytest.mark.asyncio
async def test_predict_basic_flow(basic_graph_config, mock_azure_openai):
    """Test basic prediction flow"""
    with patch('plexus.LangChainUser.LangChainUser._initialize_model', 
               return_value=mock_azure_openai):
        instance = await LangGraphScore.create(**basic_graph_config)
        
        # Mock workflow with ainvoke instead of astream
        mock_workflow = AsyncMock()
        mock_workflow.ainvoke = AsyncMock(return_value={
            "value": "Yes",
            "explanation": "Test explanation"
        })
        instance.workflow = mock_workflow
        
        input_data = Score.Input(
            text="This is a test text",
            metadata={
                "account_key": "test-account",
                "scorecard_key": "test-scorecard",
                "score_name": "test-score",
                "evaluation_mode": True  # Allow missing account_key
            },
            results=[]
        )
        
        results = await instance.predict(None, input_data)
        
        assert len(results) == 1
        assert results[0].value == "Yes"
        assert results[0].explanation == "Test explanation"
        
        # Verify workflow was called with correct initial state
        mock_workflow.ainvoke.assert_called_once()
        call_args = mock_workflow.ainvoke.call_args[0]
        assert len(call_args) >= 1
        initial_state = call_args[0]
        assert initial_state["text"] == "This is a test text"
        assert initial_state["metadata"]["account_key"] == "test-account"

@pytest.mark.skip(reason="Needs update: state handling and text preprocessing has changed")
@pytest.mark.asyncio
async def test_predict_with_list_text(basic_graph_config, mock_azure_openai):
    """Test processing with list text input"""
    with patch('plexus.LangChainUser.LangChainUser._initialize_model', 
               return_value=mock_azure_openai):
        instance = await LangGraphScore.create(**basic_graph_config)
        
        # Mock workflow
        mock_workflow = AsyncMock()
        mock_workflow.ainvoke = AsyncMock(return_value={
            "value": "No",
            "explanation": "Test explanation"
        })
        instance.workflow = mock_workflow
        
        text_list = ["This is", "a test", "text"]
        input_data = Score.Input(
            text=text_list,
            metadata={
                "account_key": "test-account",
                "scorecard_key": "test-scorecard",
                "score_name": "test-score"
            },
            results=[]
        )
        
        results = await instance.predict(None, input_data)
        
        assert len(results) == 1
        assert results[0].value == "No"
        
        # Verify text was properly joined
        mock_workflow.ainvoke.assert_called_once()
        call_args = mock_workflow.ainvoke.call_args[0]
        assert len(call_args) >= 1
        initial_state = call_args[0]
        assert initial_state["text"] == "This is a test text"

@pytest.mark.skip(reason="Needs update: token usage collection has changed")
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

@pytest.mark.skip(reason="Needs update: token usage reset mechanism has changed")
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

@pytest.mark.skip(reason="Needs update: requires account_key in metadata")
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

@pytest.mark.skip(reason="Needs update: requires account_key in metadata")
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

@pytest.mark.skip(reason="Needs update: requires account_key in metadata")
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

@pytest.mark.skip(reason="Needs update: requires account_key in metadata")
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

@pytest.mark.skip(reason="Needs update: requires account_key in metadata")
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

@pytest.mark.skip(reason="Needs update: requires account_key in metadata")
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

@pytest.mark.skip(reason="Needs update: requires account_key in metadata")
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

@pytest.mark.skip(reason="Needs update: batch processing and state management has changed")
@pytest.mark.asyncio
async def test_batch_processing_pause_basic(basic_graph_config, mock_azure_openai):
    """Test that workflow correctly pauses at LLM breakpoint"""
    with patch('plexus.LangChainUser.LangChainUser._initialize_model', 
               return_value=mock_azure_openai):
        instance = await LangGraphScore.create(**basic_graph_config)
        
        # Mock workflow to return state with LLM breakpoint
        mock_workflow = AsyncMock()
        mock_workflow.ainvoke = AsyncMock(return_value={
            "text": "test text",
            "metadata": {
                "account_key": "test-account",
                "content_id": "test-thread"
            },
            "at_llm_breakpoint": True,
            "messages": [{"type": "human", "content": "test"}]
        })
        instance.workflow = mock_workflow
        
        with pytest.raises(BatchProcessingPause) as exc_info:
            await instance.predict(None, Score.Input(
                text="test text",
                metadata={
                    "account_key": "test-account",
                    "content_id": "test-thread"
                },
                results=[]
            ))
        
        assert exc_info.value.thread_id == "test-thread"
        assert exc_info.value.state["at_llm_breakpoint"] is True
        assert exc_info.value.state["messages"] is not None
        assert len(exc_info.value.state["messages"]) == 1
        assert exc_info.value.state["messages"][0]["content"] == "test"

@pytest.mark.skip(reason="Needs update: batch processing resume flow has changed")
@pytest.mark.asyncio
async def test_batch_processing_resume(basic_graph_config, mock_azure_openai):
    """Test resuming workflow after a pause"""
    with patch('plexus.LangChainUser.LangChainUser._initialize_model', 
               return_value=mock_azure_openai):
        instance = await LangGraphScore.create(**basic_graph_config)
        
        # Mock workflow
        mock_workflow = AsyncMock()
        call_count = 0
        
        async def mock_ainvoke(*args, **kwargs):
            nonlocal call_count
            if call_count == 0:
                call_count += 1
                return {
                    "text": "test text",
                    "metadata": {
                        "account_key": "test-account",
                        "content_id": "test-thread"
                    },
                    "at_llm_breakpoint": True,
                    "messages": [{"type": "human", "content": "test"}]
                }
            else:
                return {
                    "text": "test text",
                    "metadata": {
                        "account_key": "test-account",
                        "content_id": "test-thread"
                    },
                    "messages": [{"type": "human", "content": "test"}],
                    "at_llm_breakpoint": False,
                    "completion": "test completion",
                    "value": "Yes",
                    "explanation": "test explanation"
                }
        
        mock_workflow.ainvoke = mock_ainvoke
        instance.workflow = mock_workflow
        
        # First call should pause
        with pytest.raises(BatchProcessingPause) as exc_info:
            await instance.predict(None, Score.Input(
                text="test text",
                metadata={
                    "account_key": "test-account",
                    "content_id": "test-thread"
                },
                results=[]
            ))
        
        # Save state from pause
        paused_state = exc_info.value.state
        
        # Resume with batch completion data
        results = await instance.predict(
            None, 
            Score.Input(
                text=paused_state["text"],
                metadata={
                    "account_key": "test-account",
                    "content_id": "test-thread",
                    "batch": {
                        "completion": "test completion"
                    }
                },
                results=[]
            )
        )
        
        assert len(results) == 1
        assert results[0].value == "Yes"
        assert results[0].explanation == "test explanation"

@pytest.mark.skip(reason="Needs update: requires account_key in metadata")
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

@pytest.mark.skip(reason="Needs update: checkpointing mechanism has changed")
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
        
        # Mock workflow
        mock_workflow = AsyncMock()
        mock_workflow.ainvoke = AsyncMock(return_value={
            "text": "test text",
            "metadata": {
                "account_key": "test-account",
                "content_id": "test-thread"
            },
            "at_llm_breakpoint": True,
            "messages": [{"type": "human", "content": "test"}]
        })
        instance.workflow = mock_workflow
        
        # Should initialize checkpointer
        assert instance.checkpointer is mock_checkpointer
        mock_checkpointer.setup.assert_called_once()
        
        # Should pause at LLM breakpoint
        with pytest.raises(BatchProcessingPause) as exc_info:
            await instance.predict(None, Score.Input(
                text="test text",
                metadata={
                    "account_key": "test-account",
                    "content_id": "test-thread"
                },
                results=[]
            ))
        
        assert exc_info.value.thread_id == "test-thread"
        assert exc_info.value.state["at_llm_breakpoint"] is True
        
        # Should cleanup checkpointer on pause
        await instance.cleanup()
        mock_checkpointer_context.__aexit__.assert_called_once()

@pytest.mark.skip(reason="Needs update: batch mode and thread identification has changed")
@pytest.mark.asyncio
async def test_batch_mode_with_item_id(basic_graph_config, mock_azure_openai):
    """Test batch mode with content_id for thread identification"""
    with patch('plexus.LangChainUser.LangChainUser._initialize_model', 
               return_value=mock_azure_openai):
        
        instance = await LangGraphScore.create(**basic_graph_config)
        
        # Mock workflow
        mock_workflow = AsyncMock()
        mock_workflow.ainvoke = AsyncMock(return_value={
            "text": "test text",
            "metadata": {
                "account_key": "test-account",
                "content_id": "test_content_123"
            },
            "at_llm_breakpoint": True,
            "messages": [{"type": "human", "content": "test"}]
        })
        instance.workflow = mock_workflow
        
        test_content_id = "test_content_123"
        with pytest.raises(BatchProcessingPause) as exc_info:
            await instance.predict(None, Score.Input(
                text="test text",
                metadata={
                    "account_key": "test-account",
                    "content_id": test_content_id
                },
                results=[]
            ))
        
        assert exc_info.value.thread_id == test_content_id
        assert exc_info.value.state["at_llm_breakpoint"] is True
        assert exc_info.value.state["messages"] is not None
        assert exc_info.value.state["metadata"]["content_id"] == test_content_id

@pytest.fixture
def graph_config_with_edge():
    return {
        "graph": [
            {
                "name": "first_classifier",
                "class": "YesOrNoClassifier",
                "prompt_template": "Is this a revenue only customer?",
                "output": {
                    "customer_type": "classification",
                    "reason": "explanation"
                },
                "edge": {
                    "node": "revenue_classifier",
                    "output": {
                        "value": "customer_type",  # Alias from state variable
                        "explanation": "reason",    # Alias from state variable
                        "source": "first_classifier"  # Literal value
                    }
                }
            },
            {
                "name": "revenue_classifier",
                "class": "YesOrNoClassifier",
                "prompt_template": "Revenue classifier prompt"
            },
            {
                "name": "general_classifier",
                "class": "YesOrNoClassifier",
                "prompt_template": "General classifier prompt"
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

@pytest.mark.asyncio
async def test_edge_routing(graph_config_with_edge, mock_azure_openai, mock_yes_no_classifier):
    """Test that edge clause correctly routes to specified node with output aliasing"""
    with patch('plexus.LangChainUser.LangChainUser._initialize_model', return_value=mock_azure_openai):
        instance = await LangGraphScore.create(**graph_config_with_edge)
        
        # Mock workflow to simulate state with classification and explanation
        mock_workflow = MagicMock()
        mock_workflow.ainvoke = AsyncMock(return_value={
            "customer_type": "Revenue Only",  # This comes from classification
            "reason": "Customer is marked as revenue only",  # This comes from explanation
            "value": "Revenue Only",  # This should come from customer_type alias
            "explanation": "Customer is marked as revenue only",  # This should come from reason alias
            "source": "first_classifier",  # This is a literal value
            "text": "test text",  # Required by GraphState
            "metadata": {"key": "value"},  # Required by GraphState
            "results": {}  # Required by GraphState
        })
        
        # Mock the graph structure
        mock_graph = MagicMock()
        mock_graph.nodes = {
            "first_classifier": MagicMock(),
            "first_classifier_value_setter": MagicMock(),
            "revenue_classifier": MagicMock()
        }
        mock_workflow.graph = mock_graph
        instance.workflow = mock_workflow
        
        result = await instance.predict(Score.Input(
            text="test text",
            metadata={"key": "value"},
            results=[]
        ))
        
        # Verify the result includes both aliased variables and literal values
        assert result.value == "Revenue Only"  # Aliased from customer_type
        assert result.metadata["explanation"] == "Customer is marked as revenue only"  # Aliased from reason
        assert result.metadata["source"] == "first_classifier"  # Literal value

        # Verify the workflow was created with correct edges
        workflow = instance.workflow
        assert hasattr(workflow, 'graph')  # Verify workflow has a graph
        
        # Check that the edge from first_classifier goes to the value setter
        value_setter_node = "first_classifier_value_setter"
        assert value_setter_node in workflow.graph.nodes
        
        # Check that the value setter connects to revenue_classifier
        assert "revenue_classifier" in workflow.graph.nodes

@pytest.mark.asyncio
async def test_conditions_with_edge_fallback():
    """Test that both conditions and edge clauses work together correctly"""
    
    # Create a graph config that mimics the CS3ServicesV2 pattern
    config = {
        "graph": [
            {
                "name": "main_classifier",
                "class": "Classifier",
                "valid_classes": ["Yes", "No", "Maybe"],
                "system_message": "Classify the input",
                "user_message": "{{text}}",
                "conditions": [
                    {
                        "value": "Yes",
                        "node": "END",
                        "output": {
                            "value": "Yes",
                            "explanation": "None"
                        }
                    }
                ],
                "edge": {
                    "node": "fallback_classifier",
                    "output": {
                        "good_call": "classification",
                        "good_call_explanation": "explanation"
                    }
                }
            },
            {
                "name": "fallback_classifier", 
                "class": "Classifier",
                "valid_classes": ["NQ - Parts Call", "NQ - Other"],
                "system_message": "Classify the reason for non-qualification",
                "user_message": "Previous: {{good_call}} - {{good_call_explanation}}",
                "edge": {
                    "node": "END",
                    "output": {
                        "non_qualifying_reason": "classification",
                        "non_qualifying_explanation": "explanation"
                    }
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
            "value": "good_call",
            "explanation": "non_qualifying_reason"
        }
    }
    
    # Mock the node classes
    with patch('plexus.scores.LangGraphScore.LangGraphScore._import_class') as mock_import:
        # Create mock classifier class
        mock_classifier_class = MagicMock()
        mock_classifier_instance = MagicMock()
        
        # Set up GraphState annotations
        mock_classifier_instance.GraphState = MagicMock()
        mock_classifier_instance.GraphState.__annotations__ = {
            'text': str,
            'metadata': Optional[dict],
            'results': Optional[dict],
            'classification': Optional[str],
            'explanation': Optional[str],
            'good_call': Optional[str],
            'good_call_explanation': Optional[str],
            'non_qualifying_reason': Optional[str],
            'non_qualifying_explanation': Optional[str],
            'value': Optional[str]
        }
        
        # Set up parameters
        mock_classifier_instance.parameters = MagicMock()
        mock_classifier_instance.parameters.output = None
        mock_classifier_instance.parameters.edge = None
        mock_classifier_instance.parameters.conditions = None
        
        # Mock build_compiled_workflow method
        mock_classifier_instance.build_compiled_workflow = MagicMock(
            return_value=lambda state: state
        )
        
        mock_classifier_class.return_value = mock_classifier_instance
        mock_import.return_value = mock_classifier_class
        
        # Mock the model initialization
        with patch('plexus.LangChainUser.LangChainUser._initialize_model') as mock_init_model:
            mock_model = AsyncMock()
            mock_init_model.return_value = mock_model
            
            # Create the LangGraphScore instance
            instance = await LangGraphScore.create(**config)
            
            # Test 1: Condition match - "Yes" should route to END with specific output
            mock_workflow_yes = AsyncMock()
            mock_workflow_yes.ainvoke = AsyncMock(return_value={
                "text": "test positive case",
                "metadata": {},
                "classification": "Yes",
                "explanation": "This is a good call",
                "value": "Yes",  # Set by condition output
                "explanation": "None",  # Set by condition output 
                "good_call": "Yes",
                "good_call_explanation": "This is a good call"
            })
            instance.workflow = mock_workflow_yes
            
            input_data = Score.Input(
                text="test positive case",
                metadata={},
                results=[]
            )
            
            result = await instance.predict(input_data)
            
            # Verify the "Yes" condition worked correctly
            assert result.value == "Yes"
            assert result.metadata.get('explanation') == "None"
            
            # Test 2: Edge fallback - "No" should route to fallback_classifier
            mock_workflow_no = AsyncMock()
            mock_workflow_no.ainvoke = AsyncMock(return_value={
                "text": "test negative case",
                "metadata": {},
                "classification": "No",
                "explanation": "This is not a good call",
                "good_call": "No",  # Set by edge output aliasing
                "good_call_explanation": "This is not a good call",  # Set by edge output aliasing
                "non_qualifying_reason": "NQ - Parts Call",  # Set by fallback classifier
                "non_qualifying_explanation": "Customer wants to buy parts",
                "value": "No",  # Final output aliasing
                "explanation": "NQ - Parts Call"  # Final output aliasing
            })
            instance.workflow = mock_workflow_no
            
            input_data = Score.Input(
                text="test negative case", 
                metadata={},
                results=[]
            )
            
            result = await instance.predict(input_data)
            
            # Verify the edge fallback worked correctly
            assert result.value == "No"
            assert result.metadata.get('explanation') == "NQ - Parts Call"
            assert result.metadata.get('good_call') == "No"
            assert result.metadata.get('good_call_explanation') == "This is not a good call"
            assert result.metadata.get('non_qualifying_reason') == "NQ - Parts Call"
            
            # Test 3: Edge fallback with different classification - "Maybe" should also route to fallback
            mock_workflow_maybe = AsyncMock()
            mock_workflow_maybe.ainvoke = AsyncMock(return_value={
                "text": "test unclear case",
                "metadata": {},
                "classification": "Maybe",
                "explanation": "This is unclear",
                "good_call": "Maybe",  # Set by edge output aliasing
                "good_call_explanation": "This is unclear",  # Set by edge output aliasing
                "non_qualifying_reason": "NQ - Other",  # Set by fallback classifier
                "non_qualifying_explanation": "Unclear intent",
                "value": "Maybe",  # Final output aliasing  
                "explanation": "NQ - Other"  # Final output aliasing
            })
            instance.workflow = mock_workflow_maybe
            
            input_data = Score.Input(
                text="test unclear case",
                metadata={},
                results=[]
            )
            
            result = await instance.predict(input_data)
            
            # Verify the edge fallback also works for "Maybe"
            assert result.value == "Maybe"
            assert result.metadata.get('explanation') == "NQ - Other"
            assert result.metadata.get('good_call') == "Maybe"
            assert result.metadata.get('non_qualifying_reason') == "NQ - Other"

@pytest.mark.asyncio
async def test_condition_output_preservation_with_end_routing():
    """Test that conditional outputs are preserved and not overwritten by final output aliasing"""
    # This test verifies that values set by conditional routing are preserved
    
    # Test the output aliasing function directly
    from plexus.scores.LangGraphScore import LangGraphScore
    
    # Create a mock state that simulates what happens after a condition runs
    class MockState:
        def __init__(self, **kwargs):
            self.value = kwargs.get("value", "NA")  # Set by condition
            self.explanation = kwargs.get("explanation", "Customer did not mention the criteria.")  # Set by condition  
            self.classification = kwargs.get("classification", "No")  # Original classifier result
            # Simulate that value and explanation were set by conditional routing
            self.conditional_outputs = {"value", "explanation"}
            # Accept any additional kwargs to handle aliasing
            for key, val in kwargs.items():
                setattr(self, key, val)
            
        def model_dump(self):
            return {attr: getattr(self, attr) for attr in dir(self) 
                   if not attr.startswith('_') and not callable(getattr(self, attr))}
    
    # Test the output aliasing with scorecard config that maps value->classification
    output_mapping = {"value": "classification", "explanation": "explanation"}
    
    # Mock graph config with conditions that set value
    mock_graph_config = [
        {
            "name": "test_node",
            "conditions": [
                {
                    "value": "NA",
                    "node": "END",
                    "output": {
                        "value": "NA",
                        "explanation": "Customer did not mention the criteria."
                    }
                }
            ]
        }
    ]
    
    aliasing_func = LangGraphScore.generate_output_aliasing_function(output_mapping, mock_graph_config)
    
    # Create state where condition has set value="NA" but classification="No"
    state = MockState()
    
    # Run output aliasing 
    result = aliasing_func(state)
    
    # With our fix, conditional outputs should be preserved over final output aliasing
    # Since value="NA" was set by a condition, it should be preserved and NOT overwritten by classification="No"
    assert result.value == "NA"  # Conditional output should be preserved
    assert result.explanation == "Customer did not mention the criteria."

@pytest.mark.asyncio
async def test_na_output_aliasing_bug_replication():
    """Test that replicates the bug where NA classification and explanation are incorrectly overwritten"""
    
    # Test the output aliasing function directly to isolate the bug
    from plexus.scores.LangGraphScore import LangGraphScore
    
    # Create a mock state that simulates the problematic scenario
    class MockState:
        def __init__(self, **kwargs):
            # This simulates the state after a node has run and set its output
            self.classification = "NA"  # Node classified as NA
            self.explanation = "Customer only wants cosmetic changes"  # Node's explanation
            self.value = "NA"  # Node's output aliasing set this 
            self.text = "I just want to change the style"
            self.metadata = {}
            self.results = {}
            # Accept any additional kwargs
            for key, val in kwargs.items():
                setattr(self, key, val)
            
        def model_dump(self):
            return {attr: getattr(self, attr) for attr in dir(self) 
                   if not attr.startswith('_') and not callable(getattr(self, attr))}
    
    # Test the final output aliasing that maps value->classification, explanation->explanation  
    output_mapping = {"value": "classification", "explanation": "explanation"}
    aliasing_func = LangGraphScore.generate_output_aliasing_function(output_mapping)
    
    # Create state where:
    # - classification = "NA" (what we want to map to value)
    # - explanation = "Customer only wants cosmetic changes" (what we want to preserve)
    # - value = "NA" (already set by node, should be preserved)
    state = MockState()
    
    print(f"BEFORE aliasing:")
    print(f"  state.value = {getattr(state, 'value', 'NOT_SET')!r}")
    print(f"  state.explanation = {getattr(state, 'explanation', 'NOT_SET')!r}")
    print(f"  state.classification = {getattr(state, 'classification', 'NOT_SET')!r}")
    
    # Run output aliasing 
    result = aliasing_func(state)
    
    print(f"AFTER aliasing:")
    print(f"  result.value = {getattr(result, 'value', 'NOT_SET')!r}")
    print(f"  result.explanation = {getattr(result, 'explanation', 'NOT_SET')!r}")
    print(f"  result.classification = {getattr(result, 'classification', 'NOT_SET')!r}")
    
    # These should be the correct behaviors:
    assert result.value == "NA", f"Expected value='NA' but got value='{result.value}'"
    assert result.explanation == "Customer only wants cosmetic changes", \
        f"Expected explanation='Customer only wants cosmetic changes' but got explanation='{result.explanation}'"


@pytest.mark.asyncio  
async def test_na_output_aliasing_bug_when_original_is_none():
    """Test the specific case where the original field is None, triggering the default logic"""
    
    from plexus.scores.LangGraphScore import LangGraphScore
    
    # Create a mock state where classification is None (this might trigger the bug)
    class MockState:
        def __init__(self, **kwargs):
            self.classification = None  # This is None, should trigger default logic
            self.explanation = "Customer only wants cosmetic changes"  # This should be preserved
            self.value = "NA"  # This was set by node output aliasing and should be preserved
            self.text = "I just want to change the style"
            self.metadata = {}
            self.results = {}
            
        def model_dump(self):
            return {attr: getattr(self, attr) for attr in dir(self) 
                   if not attr.startswith('_') and not callable(getattr(self, attr))}
    
    # Test the final output aliasing
    output_mapping = {"value": "classification", "explanation": "explanation"}
    aliasing_func = LangGraphScore.generate_output_aliasing_function(output_mapping)
    
    state = MockState()
    
    print(f"BEFORE aliasing (None case):")
    print(f"  state.value = {getattr(state, 'value', 'NOT_SET')!r}")
    print(f"  state.explanation = {getattr(state, 'explanation', 'NOT_SET')!r}")
    print(f"  state.classification = {getattr(state, 'classification', 'NOT_SET')!r}")
    
    # Run output aliasing 
    result = aliasing_func(state)
    
    print(f"AFTER aliasing (None case):")
    print(f"  result.value = {getattr(result, 'value', 'NOT_SET')!r}")
    print(f"  result.explanation = {getattr(result, 'explanation', 'NOT_SET')!r}")
    print(f"  result.classification = {getattr(result, 'classification', 'NOT_SET')!r}")
    
    # BUG: When classification is None, the function defaults value to "No" 
    # instead of preserving the existing value="NA"
    
    # This assertion should pass (preserve existing value):
    assert result.value == "NA", f"Expected value='NA' but got value='{result.value}' - BUG: defaults to 'No' when classification is None"
    
    # This should also pass (preserve explanation):
    assert result.explanation == "Customer only wants cosmetic changes", \
        f"Expected explanation='Customer only wants cosmetic changes' but got explanation='{result.explanation}'"


@pytest.mark.asyncio
async def test_value_setter_node_bug_replication():
    """Test that replicates the exact bug scenario with value setter nodes"""
    
    from plexus.scores.LangGraphScore import LangGraphScore
    from pydantic import BaseModel, ConfigDict
    from typing import Optional
    
    # This test simulates the exact flow from your scorecard:
    # 1. Node outputs classification="NA", explanation="Customer only wants cosmetic changes"
    # 2. Node's output clause creates a value setter that should set value="NA", explanation="Customer only wants cosmetic changes"
    # 3. Final output aliasing should preserve these values
    
    # Create a proper Pydantic model like the real GraphState
    class MockGraphState(BaseModel):
        model_config = ConfigDict(extra='allow', arbitrary_types_allowed=True)
        
        text: str
        metadata: Optional[dict] = None
        results: Optional[dict] = None
        classification: Optional[str] = None
        explanation: Optional[str] = None
        value: Optional[str] = None
    
    # First, test the value setter node function
    output_mapping = {"value": "classification", "explanation": "explanation"}
    value_setter_func = LangGraphScore.create_value_setter_node(output_mapping)
    
    # Create state as it would be after the classifier node runs
    state_after_classifier = MockGraphState(
        text="I just want to change the style",
        metadata={},
        results={},
        classification="NA",  # Node classified as NA
        explanation="Customer only wants cosmetic changes",  # Node's explanation
        # value is not set yet - this is key
    )
    
    print(f"AFTER classifier node:")
    print(f"  state.classification = {getattr(state_after_classifier, 'classification', 'NOT_SET')!r}")
    print(f"  state.explanation = {getattr(state_after_classifier, 'explanation', 'NOT_SET')!r}")
    print(f"  state.value = {getattr(state_after_classifier, 'value', 'NOT_SET')!r}")
    
    # Run the value setter (this should set value="NA", explanation remains the same)
    state_after_value_setter = value_setter_func(state_after_classifier)
    
    print(f"AFTER value setter node:")
    print(f"  state.classification = {getattr(state_after_value_setter, 'classification', 'NOT_SET')!r}")
    print(f"  state.explanation = {getattr(state_after_value_setter, 'explanation', 'NOT_SET')!r}")
    print(f"  state.value = {getattr(state_after_value_setter, 'value', 'NOT_SET')!r}")
    
    # Now test the final output aliasing (this should preserve the values)
    final_output_mapping = {"value": "classification", "explanation": "explanation"}
    final_aliasing_func = LangGraphScore.generate_output_aliasing_function(final_output_mapping)
    
    final_result = final_aliasing_func(state_after_value_setter)
    
    print(f"AFTER final output aliasing:")
    print(f"  result.classification = {getattr(final_result, 'classification', 'NOT_SET')!r}")
    print(f"  result.explanation = {getattr(final_result, 'explanation', 'NOT_SET')!r}")
    print(f"  result.value = {getattr(final_result, 'value', 'NOT_SET')!r}")
    
    # These should be the correct behaviors:
    assert final_result.value == "NA", f"Expected final value='NA' but got value='{final_result.value}'"
    assert final_result.explanation == "Customer only wants cosmetic changes", \
        f"Expected final explanation='Customer only wants cosmetic changes' but got explanation='{final_result.explanation}'"


@pytest.mark.asyncio
async def test_output_aliasing_bug_with_empty_value():
    """Test that output aliasing correctly preserves None values instead of overwriting them"""
    
    from plexus.scores.LangGraphScore import LangGraphScore
    
    # This might be the actual bug: when value is None/empty, it gets overwritten incorrectly
    class MockState:
        def __init__(self, **kwargs):
            self.classification = "NA"
            self.explanation = "Customer only wants cosmetic changes"
            # value is None/not set - this might trigger the bug
            self.value = None  # or could be missing entirely
            self.text = "I just want to change the style"
            self.metadata = {}
            self.results = {}
            
        def model_dump(self):
            return {attr: getattr(self, attr) for attr in dir(self) 
                   if not attr.startswith('_') and not callable(getattr(self, attr))}
    
    # Test the final output aliasing
    output_mapping = {"value": "classification", "explanation": "explanation"}
    aliasing_func = LangGraphScore.generate_output_aliasing_function(output_mapping)
    
    state = MockState()
    
    print(f"BEFORE aliasing (empty value case):")
    print(f"  state.value = {getattr(state, 'value', 'NOT_SET')!r}")
    print(f"  state.explanation = {getattr(state, 'explanation', 'NOT_SET')!r}")
    print(f"  state.classification = {getattr(state, 'classification', 'NOT_SET')!r}")
    
    # Run output aliasing 
    result = aliasing_func(state)
    
    print(f"AFTER aliasing (empty value case):")
    print(f"  result.value = {getattr(result, 'value', 'NOT_SET')!r}")
    print(f"  result.explanation = {getattr(result, 'explanation', 'NOT_SET')!r}")
    print(f"  result.classification = {getattr(result, 'classification', 'NOT_SET')!r}")
    
    # When value is None, the current logic preserves it (doesn't overwrite with classification)
    # This is the correct behavior - output aliasing only applies when target field is not already set
    assert result.value is None, f"Expected value=None but got value='{result.value}'"
    assert result.explanation == "Customer only wants cosmetic changes", \
        f"Expected explanation='Customer only wants cosmetic changes' but got explanation='{result.explanation}'"


@pytest.mark.asyncio
async def test_output_aliasing_bug_preserves_old_value():
    """Test the actual bug: previous node's 'No' value is preserved instead of being updated to 'NA'"""
    
    from plexus.scores.LangGraphScore import LangGraphScore
    from pydantic import BaseModel, ConfigDict
    from typing import Optional
    
    # This replicates the exact bug scenario:
    # 1. Previous node set value="No" 
    # 2. Final node outputs classification="NA", explanation="Customer only wants cosmetic changes"
    # 3. Final output aliasing should update value to "NA" but incorrectly preserves "No"
    # 4. Final output aliasing overwrites explanation with "NA" instead of preserving the actual explanation
    
    class MockGraphState(BaseModel):
        model_config = ConfigDict(extra='allow', arbitrary_types_allowed=True)
        
        text: str
        metadata: Optional[dict] = None
        results: Optional[dict] = None
        classification: Optional[str] = None
        explanation: Optional[str] = None
        value: Optional[str] = None
    
    # Create state as it would be after the final node runs, but with a previous value set
    state_with_previous_value = MockGraphState(
        text="I just want to change the style",
        metadata={},
        results={},
        classification="NA",  # Final node classified as NA
        explanation="Customer only wants cosmetic changes",  # Final node's explanation
        value="No",  # THIS IS THE BUG: Previous node set this to "No", should be updated to "NA"
    )
    
    print(f"BEFORE final output aliasing (bug scenario):")
    print(f"  state.classification = {state_with_previous_value.classification!r}")
    print(f"  state.explanation = {state_with_previous_value.explanation!r}")
    print(f"  state.value = {state_with_previous_value.value!r}")
    
    # Test the final output aliasing that should update value and preserve explanation
    final_output_mapping = {"value": "classification", "explanation": "explanation"}
    final_aliasing_func = LangGraphScore.generate_output_aliasing_function(final_output_mapping)
    
    final_result = final_aliasing_func(state_with_previous_value)
    
    print(f"AFTER final output aliasing (bug scenario):")
    print(f"  result.classification = {final_result.classification!r}")
    print(f"  result.explanation = {final_result.explanation!r}")
    print(f"  result.value = {final_result.value!r}")
    
    # BUG DETECTION: These assertions should fail if the bug exists
    # The bug is that the function preserves existing "No" value instead of updating to "NA"
    assert final_result.value == "NA", f"BUG: Expected value='NA' but got value='{final_result.value}' - function preserved old 'No' value"
    
    # BUG DETECTION: The explanation should be preserved, not overwritten with "NA"
    assert final_result.explanation == "Customer only wants cosmetic changes", \
        f"BUG: Expected explanation='Customer only wants cosmetic changes' but got explanation='{final_result.explanation}' - explanation was overwritten"


@pytest.mark.asyncio
async def test_output_aliasing_with_same_field_mapping():
    """Test the edge case where both value and explanation map to the same source field"""
    
    from plexus.scores.LangGraphScore import LangGraphScore
    from pydantic import BaseModel, ConfigDict
    from typing import Optional
    
    # This might reveal another bug: what happens when multiple aliases point to the same source?
    
    class MockGraphState(BaseModel):
        model_config = ConfigDict(extra='allow', arbitrary_types_allowed=True)
        
        text: str
        metadata: Optional[dict] = None
        results: Optional[dict] = None
        classification: Optional[str] = None
        explanation: Optional[str] = None
        value: Optional[str] = None
    
    # Create state where classification="NA" and explanation="Customer explanation"
    state = MockGraphState(
        text="I just want to change the style",
        metadata={},
        results={},
        classification="NA",
        explanation="Customer only wants cosmetic changes",
        value="No",  # Previous value
    )
    
    # Test what happens if both value and explanation map to classification
    # This might cause the explanation to be overwritten with "NA"
    problematic_mapping = {"value": "classification", "explanation": "classification"}
    aliasing_func = LangGraphScore.generate_output_aliasing_function(problematic_mapping)
    
    print(f"BEFORE problematic aliasing:")
    print(f"  state.classification = {state.classification!r}")
    print(f"  state.explanation = {state.explanation!r}")
    print(f"  state.value = {state.value!r}")
    
    result = aliasing_func(state)
    
    print(f"AFTER problematic aliasing:")
    print(f"  result.classification = {result.classification!r}")
    print(f"  result.explanation = {result.explanation!r}")
    print(f"  result.value = {result.value!r}")
    
    # In this case, both value and explanation should be set to "NA"
    # But this might reveal how the explanation gets overwritten in the real bug
    assert result.value == "NA", f"Expected value='NA' but got value='{result.value}'"
    assert result.explanation == "NA", f"Expected explanation='NA' but got explanation='{result.explanation}'"


@pytest.mark.asyncio
async def test_output_aliasing_fix_verification():
    """Test that verifies the fix: final output aliasing now properly updates values"""
    
    from plexus.scores.LangGraphScore import LangGraphScore
    from pydantic import BaseModel, ConfigDict
    from typing import Optional
    
    # This test verifies that the fix works correctly:
    # 1. Previous node set value="No" 
    # 2. Final node outputs classification="NA", explanation="Customer only wants cosmetic changes"
    # 3. Final output aliasing should now UPDATE value to "NA" (not preserve "No")
    # 4. Final output aliasing should preserve the actual explanation
    
    class MockGraphState(BaseModel):
        model_config = ConfigDict(extra='allow', arbitrary_types_allowed=True)
        
        text: str
        metadata: Optional[dict] = None
        results: Optional[dict] = None
        classification: Optional[str] = None
        explanation: Optional[str] = None
        value: Optional[str] = None
    
    # Create state as it would be after the final node runs, but with a previous value set
    state_with_previous_value = MockGraphState(
        text="I just want to change the style",
        metadata={},
        results={},
        classification="NA",  # Final node classified as NA
        explanation="Customer only wants cosmetic changes",  # Final node's explanation
        value="No",  # Previous node set this to "No", should be updated to "NA"
    )
    
    print(f"BEFORE final output aliasing (fix verification):")
    print(f"  state.classification = {state_with_previous_value.classification!r}")
    print(f"  state.explanation = {state_with_previous_value.explanation!r}")
    print(f"  state.value = {state_with_previous_value.value!r}")
    
    # Test the final output aliasing that should update value and preserve explanation
    final_output_mapping = {"value": "classification", "explanation": "explanation"}
    final_aliasing_func = LangGraphScore.generate_output_aliasing_function(final_output_mapping)
    
    final_result = final_aliasing_func(state_with_previous_value)
    
    print(f"AFTER final output aliasing (fix verification):")
    print(f"  result.classification = {final_result.classification!r}")
    print(f"  result.explanation = {final_result.explanation!r}")
    print(f"  result.value = {final_result.value!r}")
    
    # FIXED: These assertions should now pass
    assert final_result.value == "NA", f"FIXED: Expected value='NA' and got value='{final_result.value}' - function now properly updates value"
    assert final_result.explanation == "Customer only wants cosmetic changes", \
        f"FIXED: Expected explanation='Customer only wants cosmetic changes' and got explanation='{final_result.explanation}' - explanation is preserved"


@pytest.mark.asyncio
async def test_output_aliasing_fix_with_multiple_scenarios():
    """Test the fix with multiple scenarios to ensure it works correctly"""
    
    from plexus.scores.LangGraphScore import LangGraphScore
    from pydantic import BaseModel, ConfigDict
    from typing import Optional
    
    class MockGraphState(BaseModel):
        model_config = ConfigDict(extra='allow', arbitrary_types_allowed=True)
        
        text: str
        metadata: Optional[dict] = None
        results: Optional[dict] = None
        classification: Optional[str] = None
        explanation: Optional[str] = None
        value: Optional[str] = None
    
    # Test scenario 1: NA classification should update No value
    state1 = MockGraphState(
        text="test", metadata={}, results={},
        classification="NA", explanation="Customer wants cosmetic changes", value="No"
    )
    
    mapping = {"value": "classification", "explanation": "explanation"}
    aliasing_func = LangGraphScore.generate_output_aliasing_function(mapping)
    result1 = aliasing_func(state1)
    
    assert result1.value == "NA", f"Scenario 1: Expected 'NA' but got '{result1.value}'"
    assert result1.explanation == "Customer wants cosmetic changes"
    
    # Test scenario 2: Yes classification should update No value  
    state2 = MockGraphState(
        text="test", metadata={}, results={},
        classification="Yes", explanation="Customer meets criteria", value="No"
    )
    
    result2 = aliasing_func(state2)
    assert result2.value == "Yes", f"Scenario 2: Expected 'Yes' but got '{result2.value}'"
    assert result2.explanation == "Customer meets criteria"
    
    # Test scenario 3: No classification should update Yes value
    state3 = MockGraphState(
        text="test", metadata={}, results={},
        classification="No", explanation="Customer doesn't meet criteria", value="Yes"
    )
    
    result3 = aliasing_func(state3)
    assert result3.value == "No", f"Scenario 3: Expected 'No' but got '{result3.value}'"
    assert result3.explanation == "Customer doesn't meet criteria"
    
    print("✅ All scenarios passed - the fix works correctly!")


@pytest.mark.asyncio
async def test_explanation_overwriting_bug_replication():
    """Test to replicate the bug where explanation gets overwritten with classification value"""
    
    from plexus.scores.LangGraphScore import LangGraphScore
    from pydantic import BaseModel, ConfigDict
    from typing import Optional
    
    # This test aims to replicate the specific bug where:
    # 1. Final node outputs classification="NA", explanation="Customer only wants cosmetic changes"
    # 2. Final output aliasing maps value->classification, explanation->explanation  
    # 3. BUG: explanation somehow gets overwritten with "NA" instead of preserving the actual explanation
    
    class MockGraphState(BaseModel):
        model_config = ConfigDict(extra='allow', arbitrary_types_allowed=True)
        
        text: str
        metadata: Optional[dict] = None
        results: Optional[dict] = None
        classification: Optional[str] = None
        explanation: Optional[str] = None
        value: Optional[str] = None
    
    # Test scenario: Final node outputs NA classification with detailed explanation
    state = MockGraphState(
        text="I just want to change the style of my windows",
        metadata={},
        results={},
        classification="NA",  # Final node classification
        explanation="Customer only wants cosmetic changes and windows are less than 5 years old",  # Detailed explanation
        value="No",  # Previous value (we know this gets fixed)
    )
    
    print(f"BEFORE final output aliasing (explanation bug test):")
    print(f"  state.classification = {state.classification!r}")
    print(f"  state.explanation = {state.explanation!r}")
    print(f"  state.value = {state.value!r}")
    
    # Test the standard final output mapping from your scorecard
    final_output_mapping = {"value": "classification", "explanation": "explanation"}
    final_aliasing_func = LangGraphScore.generate_output_aliasing_function(final_output_mapping)
    
    result = final_aliasing_func(state)
    
    print(f"AFTER final output aliasing (explanation bug test):")
    print(f"  result.classification = {result.classification!r}")
    print(f"  result.explanation = {result.explanation!r}")
    print(f"  result.value = {result.value!r}")
    
    # These should pass if there's no bug:
    assert result.value == "NA", f"Expected value='NA' but got value='{result.value}'"
    
    # This is the key test - explanation should NOT be overwritten
    assert result.explanation == "Customer only wants cosmetic changes and windows are less than 5 years old", \
        f"BUG: Expected explanation='Customer only wants cosmetic changes and windows are less than 5 years old' but got explanation='{result.explanation}' - explanation was overwritten!"


@pytest.mark.asyncio
async def test_explanation_overwriting_with_different_mappings():
    """Test explanation overwriting with various mapping configurations that might cause the bug"""
    
    from plexus.scores.LangGraphScore import LangGraphScore
    from pydantic import BaseModel, ConfigDict
    from typing import Optional
    
    class MockGraphState(BaseModel):
        model_config = ConfigDict(extra='allow', arbitrary_types_allowed=True)
        
        text: str
        metadata: Optional[dict] = None
        results: Optional[dict] = None
        classification: Optional[str] = None
        explanation: Optional[str] = None
        value: Optional[str] = None
    
    # Test Case 1: Standard mapping (value->classification, explanation->explanation)
    state1 = MockGraphState(
        text="test", metadata={}, results={},
        classification="NA", 
        explanation="Detailed explanation about why NA",
        value="No"
    )
    
    mapping1 = {"value": "classification", "explanation": "explanation"}
    aliasing_func1 = LangGraphScore.generate_output_aliasing_function(mapping1)
    result1 = aliasing_func1(state1)
    
    print(f"Test Case 1 - Standard mapping:")
    print(f"  BEFORE: classification={state1.classification!r}, explanation={state1.explanation!r}")
    print(f"  AFTER:  value={result1.value!r}, explanation={result1.explanation!r}")
    
    # This should preserve the explanation
    assert result1.explanation == "Detailed explanation about why NA", \
        f"Case 1 BUG: explanation='{result1.explanation}' should be 'Detailed explanation about why NA'"
    
    # Test Case 2: What if both map to the same source? (This might cause the bug)
    state2 = MockGraphState(
        text="test", metadata={}, results={},
        classification="NA",
        explanation="Original explanation", 
        value="No"
    )
    
    # Both value and explanation map to classification - this might cause explanation overwriting
    mapping2 = {"value": "classification", "explanation": "classification"}
    aliasing_func2 = LangGraphScore.generate_output_aliasing_function(mapping2)
    result2 = aliasing_func2(state2)
    
    print(f"Test Case 2 - Both map to classification:")
    print(f"  BEFORE: classification={state2.classification!r}, explanation={state2.explanation!r}")
    print(f"  AFTER:  value={result2.value!r}, explanation={result2.explanation!r}")
    
    # In this case, explanation SHOULD be overwritten with classification value
    assert result2.value == "NA"
    assert result2.explanation == "NA", f"Case 2: explanation should be 'NA' but got '{result2.explanation}'"
    
    # Test Case 3: What if explanation maps to classification but we have different values?
    state3 = MockGraphState(
        text="test", metadata={}, results={},
        classification="NA",
        explanation="Should be preserved",
        value="No"  
    )
    
    # This might reveal if there's confusion in the mapping logic
    mapping3 = {"value": "classification", "explanation": "explanation"}
    aliasing_func3 = LangGraphScore.generate_output_aliasing_function(mapping3)
    result3 = aliasing_func3(state3)
    
    print(f"Test Case 3 - Standard mapping with different explanation:")
    print(f"  BEFORE: classification={state3.classification!r}, explanation={state3.explanation!r}")
    print(f"  AFTER:  value={result3.value!r}, explanation={result3.explanation!r}")
    
    # This should preserve the original explanation
    assert result3.explanation == "Should be preserved", \
        f"Case 3 BUG: explanation='{result3.explanation}' should be 'Should be preserved'"


@pytest.mark.asyncio
async def test_explanation_overwriting_order_dependency():
    """Test if the order of mappings affects explanation overwriting"""
    
    from plexus.scores.LangGraphScore import LangGraphScore
    from pydantic import BaseModel, ConfigDict
    from typing import Optional
    
    class MockGraphState(BaseModel):
        model_config = ConfigDict(extra='allow', arbitrary_types_allowed=True)
        
        text: str
        metadata: Optional[dict] = None
        results: Optional[dict] = None
        classification: Optional[str] = None
        explanation: Optional[str] = None
        value: Optional[str] = None
    
    state = MockGraphState(
        text="test", metadata={}, results={},
        classification="NA",
        explanation="This explanation should be preserved",
        value="No"
    )
    
    # Test different orders of the same mapping
    mapping_order1 = {"value": "classification", "explanation": "explanation"}
    mapping_order2 = {"explanation": "explanation", "value": "classification"}
    
    aliasing_func1 = LangGraphScore.generate_output_aliasing_function(mapping_order1)
    aliasing_func2 = LangGraphScore.generate_output_aliasing_function(mapping_order2)
    
    result1 = aliasing_func1(state)
    result2 = aliasing_func2(state)
    
    print(f"Order Test - value first:")
    print(f"  result1.value={result1.value!r}, result1.explanation={result1.explanation!r}")
    print(f"Order Test - explanation first:")
    print(f"  result2.value={result2.value!r}, result2.explanation={result2.explanation!r}")
    
    # Both should give the same results regardless of order
    assert result1.value == result2.value == "NA"
    assert result1.explanation == result2.explanation == "This explanation should be preserved", \
        f"Order dependency BUG: result1.explanation='{result1.explanation}', result2.explanation='{result2.explanation}'"


@pytest.mark.asyncio
async def test_classifier_log_state_explanation_overwriting_bug():
    """Test that replicates the exact bug in Classifier's get_parser_node method where log_state might be overwriting explanation"""
    
    from plexus.scores.LangGraphScore import LangGraphScore
    from plexus.scores.nodes.BaseNode import BaseNode
    from pydantic import BaseModel, ConfigDict
    from typing import Optional
    
    # This test simulates the exact flow in Classifier.get_parser_node() that might cause the bug:
    # 1. Parser outputs classification="NA", explanation="Detailed explanation"
    # 2. new_state is created with these values
    # 3. log_state() is called and creates a new state object
    # 4. BUG: During log_state reconstruction, explanation might get overwritten
    
    class MockGraphState(BaseModel):
        model_config = ConfigDict(extra='allow', arbitrary_types_allowed=True)
        
        text: str
        metadata: Optional[dict] = None
        results: Optional[dict] = None
        classification: Optional[str] = None
        explanation: Optional[str] = None
        value: Optional[str] = None
        completion: Optional[str] = None
        
    # Create a mock node to test log_state
    class MockNode(BaseNode):
        def __init__(self):
            # Initialize with required parameters for BaseNode
            super().__init__(name="test_classifier")
            self.GraphState = MockGraphState
            
        def add_core_nodes(self, workflow):
            pass
            
    mock_node = MockNode()
    
    # Simulate the exact scenario from Classifier.get_parser_node()
    # Step 1: Create initial state (what comes into the parser)
    initial_state = MockGraphState(
        text="I just want to change the style",
        metadata={},
        results={},
        classification=None,  # Not set yet
        explanation=None,     # Not set yet
        value="No",          # Previous node's value
        completion="NA - Customer only wants cosmetic changes and windows are less than 5 years old"
    )
    
    # Step 2: Simulate parser result
    parser_result = {
        "classification": "NA",
        "explanation": "Customer only wants cosmetic changes and windows are less than 5 years old"
    }
    
    print(f"PARSER RESULT:")
    print(f"  parser_result = {parser_result}")
    
    # Step 3: Create new_state (exactly like in Classifier.get_parser_node)
    new_state = MockGraphState(
        **{k: v for k, v in initial_state.model_dump().items() if k not in ['classification', 'explanation']},
        classification=parser_result['classification'],
        explanation=parser_result['explanation']
    )
    
    print(f"AFTER creating new_state:")
    print(f"  new_state.classification = {new_state.classification!r}")
    print(f"  new_state.explanation = {new_state.explanation!r}")
    print(f"  new_state.value = {new_state.value!r}")
    
    # Step 4: Call log_state (exactly like in Classifier.get_parser_node)
    output_state = {
        "classification": parser_result['classification'],
        "explanation": parser_result['explanation']
    }
    
    final_state = mock_node.log_state(new_state, None, output_state)
    
    print(f"AFTER log_state:")
    print(f"  final_state.classification = {final_state.classification!r}")
    print(f"  final_state.explanation = {final_state.explanation!r}")
    print(f"  final_state.value = {final_state.value!r}")
    
    # The critical test - explanation should NOT be overwritten by log_state
    assert final_state.classification == "NA", f"Expected classification='NA' but got '{final_state.classification}'"
    assert final_state.explanation == "Customer only wants cosmetic changes and windows are less than 5 years old", \
        f"BUG: log_state overwrote explanation! Expected 'Customer only wants cosmetic changes and windows are less than 5 years old' but got '{final_state.explanation}'"
    assert final_state.value == "No", f"Expected value='No' but got '{final_state.value}'"


@pytest.mark.asyncio
async def test_log_state_with_node_level_output_aliasing():
    """Test if log_state interacts badly with node-level output aliasing"""
    
    from plexus.scores.LangGraphScore import LangGraphScore
    from plexus.scores.nodes.BaseNode import BaseNode
    from pydantic import BaseModel, ConfigDict
    from typing import Optional
    
    class MockGraphState(BaseModel):
        model_config = ConfigDict(extra='allow', arbitrary_types_allowed=True)
        
        text: str
        metadata: Optional[dict] = None
        results: Optional[dict] = None
        classification: Optional[str] = None
        explanation: Optional[str] = None
        value: Optional[str] = None
        
    class MockNode(BaseNode):
        def __init__(self):
            # Initialize with required parameters for BaseNode
            super().__init__(name="test_node")
            self.GraphState = MockGraphState
            
        def add_core_nodes(self, workflow):
            pass
    
    mock_node = MockNode()
    
    # Test scenario: Node has output aliasing that should set value=classification, explanation=explanation
    # But then log_state creates a new state object - does this preserve the aliasing correctly?
    
    state_before_log = MockGraphState(
        text="test",
        metadata={},
        results={},
        classification="NA",
        explanation="Detailed explanation that should be preserved",
        value="No"  # This should get updated by node-level output aliasing
    )
    
    # Simulate the node-level output aliasing (this would happen in a value setter node)
    node_output_mapping = {"value": "classification", "explanation": "explanation"}
    value_setter_func = LangGraphScore.create_value_setter_node(node_output_mapping)
    
    state_after_aliasing = value_setter_func(state_before_log)
    
    print(f"AFTER node-level output aliasing:")
    print(f"  state_after_aliasing.classification = {state_after_aliasing.classification!r}")
    print(f"  state_after_aliasing.explanation = {state_after_aliasing.explanation!r}")
    print(f"  state_after_aliasing.value = {state_after_aliasing.value!r}")
    
    # Now call log_state - does it preserve the aliased values?
    output_state = {
        "classification": "NA",
        "explanation": "Detailed explanation that should be preserved"
    }
    
    final_state = mock_node.log_state(state_after_aliasing, None, output_state)
    
    print(f"AFTER log_state:")
    print(f"  final_state.classification = {final_state.classification!r}")
    print(f"  final_state.explanation = {final_state.explanation!r}")
    print(f"  final_state.value = {final_state.value!r}")
    
    # Test that log_state preserves the aliased values
    assert final_state.value == "NA", f"Expected value='NA' but got '{final_state.value}'"
    assert final_state.explanation == "Detailed explanation that should be preserved", \
        f"BUG: log_state overwrote explanation! Expected 'Detailed explanation that should be preserved' but got '{final_state.explanation}'"


@pytest.mark.asyncio
async def test_full_scorecard_flow_explanation_overwriting_bug():
    """Test the complete flow from scorecard that might cause explanation overwriting"""
    
    from plexus.scores.LangGraphScore import LangGraphScore
    from pydantic import BaseModel, ConfigDict
    from typing import Optional
    
    # This test simulates the EXACT flow from your Andersen Windows scorecard:
    # 1. Previous node sets value="No"
    # 2. Final classifier node outputs classification="NA", explanation="detailed explanation"
    # 3. Node-level output aliasing: value=classification, explanation=explanation
    # 4. Final output aliasing: value=classification, explanation=explanation
    # 5. BUG: Somewhere in this flow, explanation gets overwritten with "NA"
    
    class MockGraphState(BaseModel):
        model_config = ConfigDict(extra='allow', arbitrary_types_allowed=True)
        
        text: str
        metadata: Optional[dict] = None
        results: Optional[dict] = None
        classification: Optional[str] = None
        explanation: Optional[str] = None
        value: Optional[str] = None
        
    print("=== FULL SCORECARD FLOW TEST ===")
    
    # Step 1: Initial state (after previous nodes have run)
    initial_state = MockGraphState(
        text="I just want to change the style of my windows",
        metadata={},
        results={},
        classification=None,
        explanation=None,
        value="No"  # Previous node classified as "No"
    )
    
    print(f"STEP 1 - Initial state:")
    print(f"  classification = {initial_state.classification!r}")
    print(f"  explanation = {initial_state.explanation!r}")
    print(f"  value = {initial_state.value!r}")
    
    # Step 2: Final classifier node runs and sets classification and explanation
    after_classifier = MockGraphState(
        **{k: v for k, v in initial_state.model_dump().items() if k not in ['classification', 'explanation']},
        classification="NA",  # Final node classification
        explanation="Customer only wants cosmetic changes and windows are less than 5 years old"  # Final node explanation
    )
    
    print(f"STEP 2 - After final classifier node:")
    print(f"  classification = {after_classifier.classification!r}")
    print(f"  explanation = {after_classifier.explanation!r}")
    print(f"  value = {after_classifier.value!r}")
    
    # Step 3: Node-level output aliasing (from the node's output clause)
    # This is what happens in the value setter node created for the final classifier
    node_output_mapping = {"value": "classification", "explanation": "explanation"}
    node_value_setter = LangGraphScore.create_value_setter_node(node_output_mapping)
    
    after_node_aliasing = node_value_setter(after_classifier)
    
    print(f"STEP 3 - After node-level output aliasing:")
    print(f"  classification = {after_node_aliasing.classification!r}")
    print(f"  explanation = {after_node_aliasing.explanation!r}")
    print(f"  value = {after_node_aliasing.value!r}")
    
    # Step 4: Final output aliasing (from the main output clause)
    # This is what happens in the final output_aliasing node
    final_output_mapping = {"value": "classification", "explanation": "explanation"}
    final_aliasing_func = LangGraphScore.generate_output_aliasing_function(final_output_mapping)
    
    final_result = final_aliasing_func(after_node_aliasing)
    
    print(f"STEP 4 - After final output aliasing:")
    print(f"  classification = {final_result.classification!r}")
    print(f"  explanation = {final_result.explanation!r}")
    print(f"  value = {final_result.value!r}")
    
    # The critical assertions - this should catch the bug
    assert final_result.value == "NA", f"Expected final value='NA' but got '{final_result.value}'"
    assert final_result.explanation == "Customer only wants cosmetic changes and windows are less than 5 years old", \
        f"BUG: Final explanation was overwritten! Expected 'Customer only wants cosmetic changes and windows are less than 5 years old' but got '{final_result.explanation}'"
    
    print("✅ FULL FLOW TEST PASSED - No explanation overwriting detected")


@pytest.mark.asyncio
async def test_explanation_overwriting_with_same_source_field():
    """Test if explanation overwriting happens when both value and explanation map to the same source"""
    
    from plexus.scores.LangGraphScore import LangGraphScore
    from pydantic import BaseModel, ConfigDict
    from typing import Optional
    
    # This test checks if the bug happens when the mapping is confusing the system
    # Maybe the issue is that both value and explanation are mapping to "classification"
    # in some part of the flow, causing explanation to get the classification value
    
    class MockGraphState(BaseModel):
        model_config = ConfigDict(extra='allow', arbitrary_types_allowed=True)
        
        text: str
        metadata: Optional[dict] = None
        results: Optional[dict] = None
        classification: Optional[str] = None
        explanation: Optional[str] = None
        value: Optional[str] = None
        
    print("=== SAME SOURCE FIELD TEST ===")
    
    # Test scenario: What if there's a bug where both value and explanation
    # are accidentally getting mapped to the same source field?
    
    state = MockGraphState(
        text="test",
        metadata={},
        results={},
        classification="NA",
        explanation="Detailed explanation that should be preserved",
        value="No"
    )
    
    print(f"BEFORE aliasing:")
    print(f"  classification = {state.classification!r}")
    print(f"  explanation = {state.explanation!r}")
    print(f"  value = {state.value!r}")
    
    # Test case 1: Correct mapping
    correct_mapping = {"value": "classification", "explanation": "explanation"}
    correct_func = LangGraphScore.generate_output_aliasing_function(correct_mapping)
    correct_result = correct_func(state)
    
    print(f"AFTER correct mapping:")
    print(f"  value = {correct_result.value!r}")
    print(f"  explanation = {correct_result.explanation!r}")
    
    # Test case 2: Buggy mapping - both map to classification (this would cause explanation overwriting)
    buggy_mapping = {"value": "classification", "explanation": "classification"}
    buggy_func = LangGraphScore.generate_output_aliasing_function(buggy_mapping)
    buggy_result = buggy_func(state)
    
    print(f"AFTER buggy mapping (both->classification):")
    print(f"  value = {buggy_result.value!r}")
    print(f"  explanation = {buggy_result.explanation!r}")
    
    # The correct mapping should preserve explanation
    assert correct_result.explanation == "Detailed explanation that should be preserved", \
        f"Correct mapping failed: explanation='{correct_result.explanation}'"
    
    # The buggy mapping should overwrite explanation with classification value
    assert buggy_result.explanation == "NA", \
        f"Buggy mapping should set explanation='NA' but got '{buggy_result.explanation}'"
    
    print("✅ SAME SOURCE FIELD TEST PASSED")


@pytest.mark.asyncio  
async def test_explanation_overwriting_with_field_order():
    """Test if the order of field processing in output aliasing causes explanation overwriting"""
    
    from plexus.scores.LangGraphScore import LangGraphScore
    from pydantic import BaseModel, ConfigDict
    from typing import Optional
    
    # This test checks if the order of processing fields in the output aliasing
    # could cause the explanation to be overwritten
    
    class MockGraphState(BaseModel):
        model_config = ConfigDict(extra='allow', arbitrary_types_allowed=True)
        
        text: str
        metadata: Optional[dict] = None
        results: Optional[dict] = None
        classification: Optional[str] = None
        explanation: Optional[str] = None
        value: Optional[str] = None
        
    print("=== FIELD ORDER TEST ===")
    
    state = MockGraphState(
        text="test",
        metadata={},
        results={},
        classification="NA",
        explanation="Original detailed explanation",
        value="No"
    )
    
    # Test different orders of the same mappings
    order1 = {"value": "classification", "explanation": "explanation"}
    order2 = {"explanation": "explanation", "value": "classification"}
    
    func1 = LangGraphScore.generate_output_aliasing_function(order1)
    func2 = LangGraphScore.generate_output_aliasing_function(order2)
    
    result1 = func1(state)
    result2 = func2(state)
    
    print(f"Order 1 (value first): value={result1.value!r}, explanation={result1.explanation!r}")
    print(f"Order 2 (explanation first): value={result2.value!r}, explanation={result2.explanation!r}")
    
    # Both should give identical results
    assert result1.value == result2.value == "NA"
    assert result1.explanation == result2.explanation == "Original detailed explanation", \
        f"Field order caused different results: result1.explanation='{result1.explanation}', result2.explanation='{result2.explanation}'"
    
    print("✅ FIELD ORDER TEST PASSED")


@pytest.mark.asyncio
async def test_classification_parser_explanation_bug_fix():
    """Test that the ClassificationOutputParser now correctly preserves the explanation instead of overwriting it with classification"""
    
    from plexus.scores.nodes.Classifier import Classifier
    
    print("=== CLASSIFICATION PARSER BUG FIX TEST ===")
    
    # Create a ClassificationOutputParser with valid classes
    parser = Classifier.ClassificationOutputParser(
        valid_classes=["Yes", "No", "NA"],
        parse_from_start=False
    )
    
    # Test case 1: LLM output with NA classification and detailed explanation
    llm_output_1 = "NA - Customer only wants cosmetic changes and windows are less than 5 years old"
    result_1 = parser.parse(llm_output_1)
    
    print(f"TEST 1 - LLM output: {llm_output_1!r}")
    print(f"  Parsed classification: {result_1['classification']!r}")
    print(f"  Parsed explanation: {result_1['explanation']!r}")
    
    # The fix should preserve the full explanation, not just the classification
    assert result_1['classification'] == "NA", f"Expected classification='NA' but got '{result_1['classification']}'"
    assert result_1['explanation'] == "NA - Customer only wants cosmetic changes and windows are less than 5 years old", \
        f"BUG STILL EXISTS: Expected full explanation but got '{result_1['explanation']}'"
    
    # Test case 2: LLM output with Yes classification and detailed explanation  
    llm_output_2 = "Yes, this customer is requesting replacement windows due to damage"
    result_2 = parser.parse(llm_output_2)
    
    print(f"TEST 2 - LLM output: {llm_output_2!r}")
    print(f"  Parsed classification: {result_2['classification']!r}")
    print(f"  Parsed explanation: {result_2['explanation']!r}")
    
    assert result_2['classification'] == "Yes", f"Expected classification='Yes' but got '{result_2['classification']}'"
    assert result_2['explanation'] == "Yes, this customer is requesting replacement windows due to damage", \
        f"Expected full explanation but got '{result_2['explanation']}'"
    
    # Test case 3: LLM output with No classification and detailed explanation
    llm_output_3 = "No - Customer is asking about maintenance, not window replacement"
    result_3 = parser.parse(llm_output_3)
    
    print(f"TEST 3 - LLM output: {llm_output_3!r}")
    print(f"  Parsed classification: {result_3['classification']!r}")
    print(f"  Parsed explanation: {result_3['explanation']!r}")
    
    assert result_3['classification'] == "No", f"Expected classification='No' but got '{result_3['classification']}'"
    assert result_3['explanation'] == "No - Customer is asking about maintenance, not window replacement", \
        f"Expected full explanation but got '{result_3['explanation']}'"
    
    # Test case 4: Invalid classification should still work
    llm_output_4 = "Maybe - I'm not sure about this case"
    result_4 = parser.parse(llm_output_4)
    
    print(f"TEST 4 - LLM output: {llm_output_4!r}")
    print(f"  Parsed classification: {result_4['classification']!r}")
    print(f"  Parsed explanation: {result_4['explanation']!r}")
    
    assert result_4['classification'] is None, f"Expected classification=None but got '{result_4['classification']}'"
    assert result_4['explanation'] == "Maybe - I'm not sure about this case", \
        f"Expected full explanation but got '{result_4['explanation']}'"
    
    print("✅ CLASSIFICATION PARSER BUG FIX TEST PASSED - Explanations are now preserved!")


@pytest.mark.asyncio
async def test_both_bugs_fixed_comprehensive():
    """Comprehensive test that verifies both the output aliasing bug and explanation overwriting bug are fixed"""
    
    from plexus.scores.LangGraphScore import LangGraphScore
    from plexus.scores.nodes.Classifier import Classifier
    from pydantic import BaseModel, ConfigDict
    from typing import Optional
    
    print("=== COMPREHENSIVE BOTH BUGS FIXED TEST ===")
    
    # This test verifies that both bugs we identified and fixed are working correctly:
    # 1. Output aliasing bug: Final output aliasing should update existing values
    # 2. Explanation overwriting bug: ClassificationOutputParser should preserve full explanation
    
    class MockGraphState(BaseModel):
        model_config = ConfigDict(extra='allow', arbitrary_types_allowed=True)
        
        text: str
        metadata: Optional[dict] = None
        results: Optional[dict] = None
        classification: Optional[str] = None
        explanation: Optional[str] = None
        value: Optional[str] = None
        
    # Step 1: Test the ClassificationOutputParser fix
    parser = Classifier.ClassificationOutputParser(
        valid_classes=["Yes", "No", "NA"],
        parse_from_start=False
    )
    
    llm_output = "NA - Customer only wants cosmetic changes and windows are less than 5 years old"
    parser_result = parser.parse(llm_output)
    
    print(f"STEP 1 - Parser test:")
    print(f"  LLM output: {llm_output!r}")
    print(f"  Parsed classification: {parser_result['classification']!r}")
    print(f"  Parsed explanation: {parser_result['explanation']!r}")
    
    # Verify the explanation bug is fixed
    assert parser_result['classification'] == "NA"
    assert parser_result['explanation'] == "NA - Customer only wants cosmetic changes and windows are less than 5 years old"
    
    # Step 2: Test the output aliasing fix with the correct explanation
    initial_state = MockGraphState(
        text="I just want to change the style",
        metadata={},
        results={},
        classification="NA",
        explanation="NA - Customer only wants cosmetic changes and windows are less than 5 years old",
        value="No"  # Previous node's value that should be updated
    )
    
    print(f"STEP 2 - Before final output aliasing:")
    print(f"  classification = {initial_state.classification!r}")
    print(f"  explanation = {initial_state.explanation!r}")
    print(f"  value = {initial_state.value!r}")
    
    # Apply final output aliasing
    final_output_mapping = {"value": "classification", "explanation": "explanation"}
    final_aliasing_func = LangGraphScore.generate_output_aliasing_function(final_output_mapping)
    
    final_result = final_aliasing_func(initial_state)
    
    print(f"STEP 3 - After final output aliasing:")
    print(f"  classification = {final_result.classification!r}")
    print(f"  explanation = {final_result.explanation!r}")
    print(f"  value = {final_result.value!r}")
    
    # Verify both bugs are fixed:
    # 1. Output aliasing bug fix: value should be updated from "No" to "NA"
    assert final_result.value == "NA", f"Output aliasing bug NOT fixed: Expected value='NA' but got '{final_result.value}'"
    
    # 2. Explanation overwriting bug fix: explanation should be preserved
    assert final_result.explanation == "NA - Customer only wants cosmetic changes and windows are less than 5 years old", \
        f"Explanation overwriting bug NOT fixed: Expected full explanation but got '{final_result.explanation}'"
    
    print("✅ COMPREHENSIVE TEST PASSED - Both bugs are fixed!")
    print("  ✓ Output aliasing now correctly updates values")
    print("  ✓ Explanation is preserved instead of being overwritten")
