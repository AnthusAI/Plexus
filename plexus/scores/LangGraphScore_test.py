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
async def test_condition_output_preservation_with_end_routing():
    """Test that condition outputs are preserved when routing to END with final output aliasing"""
    # This test verifies the fix for the issue where condition outputs 
    # were being overwritten by final output aliasing
    
    # Test the output aliasing function directly
    from plexus.scores.LangGraphScore import LangGraphScore
    
    # Create a mock state that simulates what happens after a condition runs
    class MockState:
        def __init__(self, **kwargs):
            self.value = kwargs.get("value", "NA")  # Set by condition
            self.explanation = kwargs.get("explanation", "Customer did not mention the criteria.")  # Set by condition  
            self.classification = kwargs.get("classification", "No")  # Original classifier result
            # Accept any additional kwargs to handle aliasing
            for key, val in kwargs.items():
                setattr(self, key, val)
            
        def model_dump(self):
            return {attr: getattr(self, attr) for attr in dir(self) 
                   if not attr.startswith('_') and not callable(getattr(self, attr))}
    
    # Test the output aliasing with scorecard config that maps value->classification
    output_mapping = {"value": "classification", "explanation": "explanation"}
    aliasing_func = LangGraphScore.generate_output_aliasing_function(output_mapping)
    
    # Create state where condition has set value="NA" but classification="No"
    state = MockState()
    
    # Run output aliasing 
    result = aliasing_func(state)
    
    # Verify that condition output is preserved (should NOT be overwritten by classification)
    assert result.value == "NA"  # Should preserve condition output, not overwrite with "No"
    assert result.explanation == "Customer did not mention the criteria."
