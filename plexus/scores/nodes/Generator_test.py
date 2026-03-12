import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from plexus.scores.nodes.Generator import Generator
from langchain_core.messages import AIMessage, HumanMessage, SystemMessage
from plexus.scores.LangGraphScore import BatchProcessingPause

pytest.asyncio_fixture_scope = "function"
pytest_plugins = ('pytest_asyncio',)

@pytest.fixture(autouse=True)
def disable_batch_mode(monkeypatch):
    monkeypatch.setenv('PLEXUS_ENABLE_BATCH_MODE', 'false')
    monkeypatch.setenv('PLEXUS_ENABLE_LLM_BREAKPOINTS', 'false')

@pytest.fixture
def basic_generator_config():
    return {
        "name": "test_generator",
        "system_message": "You are a helpful content generator.",
        "user_message": "Generate content for: {text}",
        "model_provider": "AzureChatOpenAI",
        "model_name": "gpt-4",
        "temperature": 0.7,
        "maximum_retry_count": 3
    }

@pytest.fixture
def summary_generator_config():
    return {
        "name": "summary_generator",
        "system_message": "You are a summarization assistant.",
        "user_message": "Summarize this text: {text}",
        "model_provider": "AzureChatOpenAI",
        "model_name": "gpt-4",
        "temperature": 0.0,
        "maximum_retry_count": 3
    }

@pytest.fixture
def creative_generator_config():
    return {
        "name": "creative_writer",
        "system_message": "You are a creative writing assistant.",
        "user_message": "Write a creative response to: {text}",
        "model_provider": "AzureChatOpenAI",
        "model_name": "gpt-4",
        "temperature": 1.0,
        "maximum_retry_count": 2
    }

@pytest.mark.asyncio
async def test_generator_successful_generation(basic_generator_config):
    """Test that Generator successfully generates content on first attempt."""
    mock_model = AsyncMock()
    mock_response = AIMessage(content="This is a successful generation of content based on the input.")
    mock_model.ainvoke = AsyncMock(return_value=mock_response)

    with patch('plexus.LangChainUser.LangChainUser._initialize_model',
               return_value=mock_model):
        generator = Generator(**basic_generator_config)
        generator.model = mock_model

        state = generator.GraphState(
            text="Generate something interesting",
            metadata={},
            results={},
            retry_count=0,
            completion=None,
            explanation=None
        )

        llm_prompt_node = generator.get_llm_prompt_node()
        llm_call_node = generator.get_llm_call_node()

        # Run prompt node
        state_after_prompt = await llm_prompt_node(state)
        # Run LLM call node
        final_state = await llm_call_node(state_after_prompt)

        assert final_state.completion == "This is a successful generation of content based on the input."
        assert final_state.retry_count == 0

@pytest.mark.asyncio
async def test_generator_empty_response_triggers_retry(basic_generator_config):
    """Test that Generator retries when LLM returns empty content."""
    mock_model = AsyncMock()
    responses = [
        AIMessage(content=""),  # Empty response - should trigger retry
        AIMessage(content="This is the successful retry response.")
    ]
    mock_model.ainvoke = AsyncMock(side_effect=responses)

    with patch('plexus.LangChainUser.LangChainUser._initialize_model',
               return_value=mock_model):
        generator = Generator(**basic_generator_config)
        generator.model = mock_model

        state = generator.GraphState(
            text="Generate content for this topic",
            metadata={},
            results={},
            retry_count=0,
            completion=None,
            explanation=None
        )

        llm_prompt_node = generator.get_llm_prompt_node()
        llm_call_node = generator.get_llm_call_node()
        retry_node = generator.get_retry_node()

        # First attempt - should get empty response
        state_after_prompt = await llm_prompt_node(state)
        state_after_llm = await llm_call_node(state_after_prompt)

        # Should have empty completion
        assert state_after_llm.completion is None
        assert state_after_llm.explanation == "No completion received from LLM"

        # Should need retry
        retry_decision = generator.should_retry(state_after_llm)
        assert retry_decision == "retry"

        # Retry attempt
        state_after_retry = await retry_node(state_after_llm)
        assert state_after_retry.retry_count == 1

        # Second attempt should succeed
        state_after_prompt2 = await llm_prompt_node(state_after_retry)
        final_state = await llm_call_node(state_after_prompt2)

        assert final_state.completion == "This is the successful retry response."
        assert final_state.retry_count == 1

@pytest.mark.asyncio
async def test_generator_whitespace_response_triggers_retry(summary_generator_config):
    """Test that Generator retries when LLM returns only whitespace."""
    mock_model = AsyncMock()
    responses = [
        AIMessage(content="   \n\t  "),  # Whitespace only - should trigger retry
        AIMessage(content="Here is a proper summary of the content.")
    ]
    mock_model.ainvoke = AsyncMock(side_effect=responses)

    with patch('plexus.LangChainUser.LangChainUser._initialize_model',
               return_value=mock_model):
        generator = Generator(**summary_generator_config)
        generator.model = mock_model

        state = generator.GraphState(
            text="This is a long document that needs summarization.",
            metadata={},
            results={},
            retry_count=0,
            completion=None,
            explanation=None
        )

        llm_prompt_node = generator.get_llm_prompt_node()
        llm_call_node = generator.get_llm_call_node()
        retry_node = generator.get_retry_node()

        # First attempt - should get whitespace response
        state_after_prompt = await llm_prompt_node(state)
        state_after_llm = await llm_call_node(state_after_prompt)

        # Should trigger retry due to whitespace
        retry_decision = generator.should_retry(state_after_llm)
        assert retry_decision == "retry"

        # Retry and succeed
        state_after_retry = await retry_node(state_after_llm)
        state_after_prompt2 = await llm_prompt_node(state_after_retry)
        final_state = await llm_call_node(state_after_prompt2)

        assert final_state.completion == "Here is a proper summary of the content."

@pytest.mark.asyncio
async def test_generator_multiple_retries_before_success(creative_generator_config):
    """Test Generator with multiple retries before success."""
    mock_model = AsyncMock()
    responses = [
        AIMessage(content=""),                    # First attempt: empty
        AIMessage(content="   "),                 # Second attempt: whitespace
        AIMessage(content="Finally, a creative story about adventure!")  # Third attempt: success
    ]
    mock_model.ainvoke = AsyncMock(side_effect=responses)

    with patch('plexus.LangChainUser.LangChainUser._initialize_model',
               return_value=mock_model):
        generator = Generator(**creative_generator_config)
        generator.model = mock_model

        state = generator.GraphState(
            text="Write a creative story",
            metadata={},
            results={},
            retry_count=0,
            completion=None,
            explanation=None
        )

        llm_prompt_node = generator.get_llm_prompt_node()
        llm_call_node = generator.get_llm_call_node()
        retry_node = generator.get_retry_node()

        # First attempt (empty response)
        state = await llm_prompt_node(state)
        state = await llm_call_node(state)
        assert state.completion is None
        assert generator.should_retry(state) == "retry"

        # First retry (whitespace response)
        state = await retry_node(state)
        assert state.retry_count == 1
        state = await llm_prompt_node(state)
        state = await llm_call_node(state)
        assert generator.should_retry(state) == "retry"

        # Second retry (success)
        state = await retry_node(state)
        assert state.retry_count == 2
        state = await llm_prompt_node(state)
        final_state = await llm_call_node(state)

        assert final_state.completion == "Finally, a creative story about adventure!"
        assert final_state.retry_count == 2
        assert generator.should_retry(final_state) == "end"

@pytest.mark.asyncio
async def test_generator_maximum_retries_reached(basic_generator_config):
    """Test Generator behavior when maximum retries are reached."""
    mock_model = AsyncMock()
    responses = [
        AIMessage(content=""),     # First attempt: empty
        AIMessage(content=""),     # First retry: empty
        AIMessage(content=""),     # Second retry: empty
        AIMessage(content="")      # Third retry: empty
    ]
    mock_model.ainvoke = AsyncMock(side_effect=responses)

    with patch('plexus.LangChainUser.LangChainUser._initialize_model',
               return_value=mock_model):
        generator = Generator(**basic_generator_config)
        generator.model = mock_model

        initial_state = generator.GraphState(
            text="Generate content",
            metadata={},
            results={},
            retry_count=0,
            completion=None,
            explanation=None
        )

        llm_prompt_node = generator.get_llm_prompt_node()
        llm_call_node = generator.get_llm_call_node()
        retry_node = generator.get_retry_node()
        max_retries_node = generator.get_max_retries_node()

        current_state = initial_state

        # Simulate multiple failed attempts
        for _ in range(3):  # maximum_retry_count = 3
            current_state = await llm_prompt_node(current_state)
            current_state = await llm_call_node(current_state)

            if current_state.completion is None:
                current_state = await retry_node(current_state)

        # Final attempt should also fail
        current_state = await llm_prompt_node(current_state)
        current_state = await llm_call_node(current_state)

        # Handle max retries
        final_state = await max_retries_node(current_state)

        assert "Failed to generate a valid completion" in final_state.completion
        assert final_state.retry_count == 3
        assert mock_model.ainvoke.call_count == 4  # Initial + 3 retries

@pytest.mark.asyncio
async def test_generator_state_isolation_retry_bug():
    """
    Test for state isolation retry bug in Generator nodes.

    Similar to Classifier, this ensures Generator nodes only consider their own
    results when making retry decisions, not combined state from other nodes.
    """
    mock_model = AsyncMock()

    # Responses for both generators
    responses = [
        # Generator A: succeeds immediately
        AIMessage(content="Generator A produced this content successfully."),

        # Generator B: fails first attempt (empty), then succeeds
        AIMessage(content=""),
        AIMessage(content="Generator B finally produced this content."),

        # Second scenario responses
        # Generator A: succeeds immediately
        AIMessage(content="Generator A second success."),

        # Generator B: fails with whitespace, then succeeds
        AIMessage(content="   \n  "),
        AIMessage(content="Generator B second success.")
    ]

    mock_model.ainvoke = AsyncMock(side_effect=responses)

    with patch('plexus.LangChainUser.LangChainUser._initialize_model',
               return_value=mock_model):

        # Create Generator A - content generator
        gen_a_config = {
            "name": "content_generator",
            "system_message": "You are a content generator.",
            "user_message": "Generate content about: {text}",
            "model_provider": "AzureChatOpenAI",
            "model_name": "gpt-4",
            "maximum_retry_count": 3
        }

        # Create Generator B - summary generator
        gen_b_config = {
            "name": "summary_generator",
            "system_message": "You are a summary generator.",
            "user_message": "Summarize: {text}",
            "model_provider": "AzureChatOpenAI",
            "model_name": "gpt-4",
            "maximum_retry_count": 3
        }

        gen_a = Generator(**gen_a_config)
        gen_b = Generator(**gen_b_config)

        gen_a.model = mock_model
        gen_b.model = mock_model

        # === Test Scenario 1: Generator B fails with empty response ===
        initial_state = gen_a.GraphState(
            text="Create comprehensive content about AI",
            metadata={'trace': {'node_results': []}},
            results={},
            retry_count=0,
            completion=None,
            explanation=None
        )

        # Generator A execution (should succeed)
        state = await gen_a.get_llm_prompt_node()(initial_state)
        state = await gen_a.get_llm_call_node()(state)

        assert state.completion == "Generator A produced this content successfully."

        # Simulate trace metadata storage
        if not hasattr(state, 'metadata') or not state.metadata:
            state.metadata = {}
        if 'trace' not in state.metadata:
            state.metadata['trace'] = {'node_results': []}

        state.metadata['trace']['node_results'].append({
            'node_name': 'content_generator',
            'input': {},
            'output': {'explanation': 'Generator A produced this content successfully.'}
        })

        # Check Generator A's retry logic - should not retry
        retry_decision_a = gen_a.should_retry(state)
        assert retry_decision_a == "end", f"Generator A should not retry after success, got '{retry_decision_a}'"

        # Generator B execution (should fail first attempt)
        gen_b_state = await gen_b.get_llm_prompt_node()(state)
        gen_b_state = await gen_b.get_llm_call_node()(gen_b_state)

        # Should fail due to empty response
        assert gen_b_state.completion is None
        assert gen_b_state.explanation == "No completion received from LLM"

        # The llm_call_node automatically adds trace results, so we don't need to manually add them
        # Instead, we need to use the gen_b_state that has the trace results from the actual execution

        # CRITICAL TEST: Generator B's retry logic with Generator A's success in combined state
        # Before fix: would see Generator A's success and skip retry
        # After fix: should only consider its own results and retry
        retry_decision_b = gen_b.should_retry(gen_b_state)
        assert retry_decision_b == "retry", f"Generator B should retry despite Generator A's success, got '{retry_decision_b}'"

        # Generator B retry and success
        gen_b_state = await gen_b.get_retry_node()(gen_b_state)
        assert gen_b_state.retry_count == 1

        gen_b_state = await gen_b.get_llm_prompt_node()(gen_b_state)
        gen_b_state = await gen_b.get_llm_call_node()(gen_b_state)

        assert gen_b_state.completion == "Generator B finally produced this content."

        # Check retry logic - should not retry after success
        # Use gen_b_state which has the updated trace results from the actual execution
        retry_decision_b2 = gen_b.should_retry(gen_b_state)
        assert retry_decision_b2 == "end", f"Generator B should not retry after success, got '{retry_decision_b2}'"

        # === Test Scenario 2: Generator B fails with whitespace ===
        initial_state_2 = gen_a.GraphState(
            text="Generate content about machine learning",
            metadata={'trace': {'node_results': []}},
            results={},
            retry_count=0,
            completion=None,
            explanation=None
        )

        # Generator A execution (should succeed)
        state_2 = await gen_a.get_llm_prompt_node()(initial_state_2)
        state_2 = await gen_a.get_llm_call_node()(state_2)

        assert state_2.completion == "Generator A second success."

        # Add Generator A result to trace
        state_2.metadata['trace']['node_results'].append({
            'node_name': 'content_generator',
            'input': {},
            'output': {'explanation': 'Generator A second success.'}
        })

        # Generator B execution with whitespace response
        gen_b_state_2 = await gen_b.get_llm_prompt_node()(state_2)
        gen_b_state_2 = await gen_b.get_llm_call_node()(gen_b_state_2)

        # Should fail due to whitespace response
        assert gen_b_state_2.completion is None
        assert gen_b_state_2.explanation == "No completion received from LLM"

        # Test retry logic with whitespace response
        # Use gen_b_state_2 which has the trace results from the actual execution
        retry_decision_whitespace = gen_b.should_retry(gen_b_state_2)
        assert retry_decision_whitespace == "retry", f"Generator B should retry with whitespace response, got '{retry_decision_whitespace}'"

        # Complete retry and verify success
        gen_b_state_2 = await gen_b.get_retry_node()(gen_b_state_2)
        gen_b_state_2 = await gen_b.get_llm_prompt_node()(gen_b_state_2)
        gen_b_state_2 = await gen_b.get_llm_call_node()(gen_b_state_2)

        assert gen_b_state_2.completion == "Generator B second success."

        # Verify total LLM calls
        # Scenario 1: Gen A (1) + Gen B (2 attempts) = 3
        # Scenario 2: Gen A (1) + Gen B (2 attempts) = 3
        # Total: 6 calls
        total_expected_calls = 6
        actual_calls = mock_model.ainvoke.call_count
        assert actual_calls == total_expected_calls, f"Expected {total_expected_calls} total LLM calls, got {actual_calls}"

@pytest.mark.asyncio
async def test_generator_handles_dict_messages(basic_generator_config):
    """Test that Generator handles messages in dictionary format correctly."""
    mock_model = AsyncMock()
    mock_response = AIMessage(content="Generated content from dict messages")
    mock_model.ainvoke = AsyncMock(return_value=mock_response)

    with patch('plexus.LangChainUser.LangChainUser._initialize_model',
               return_value=mock_model):
        generator = Generator(**basic_generator_config)
        generator.model = mock_model

        # Create state with messages in dict format
        state = generator.GraphState(
            text="Generate content for this",
            metadata={},
            results={},
            retry_count=0,
            completion=None,
            explanation=None,
            messages=[
                {
                    'type': 'system',
                    'content': 'You are a helpful content generator.',
                    '_type': 'SystemMessage'
                },
                {
                    'type': 'human',
                    'content': 'Generate content for: {text}',
                    '_type': 'HumanMessage'
                }
            ]
        )

        llm_prompt_node = generator.get_llm_prompt_node()
        llm_call_node = generator.get_llm_call_node()

        # Run through nodes
        state = await llm_prompt_node(state)
        final_state = await llm_call_node(state)

        assert final_state.completion == "Generated content from dict messages"

        # Verify messages were handled correctly
        assert len(mock_model.ainvoke.call_args_list) == 1
        call_messages = mock_model.ainvoke.call_args_list[0][0][0]
        assert len(call_messages) == 2
        assert isinstance(call_messages[0], SystemMessage)
        assert isinstance(call_messages[1], HumanMessage)

@pytest.mark.asyncio
async def test_generator_batch_mode(basic_generator_config):
    """Test Generator batch mode functionality."""
    mock_model = AsyncMock()
    mock_response = AIMessage(content="Generated content")
    mock_model.ainvoke = AsyncMock(return_value=mock_response)

    with patch('plexus.LangChainUser.LangChainUser._initialize_model',
               return_value=mock_model):
        # Enable batch mode
        basic_generator_config['batch'] = True
        generator = Generator(**basic_generator_config)
        generator.model = mock_model

        state = generator.GraphState(
            text="Generate content for batch processing",
            metadata={
                'account_key': 'test_account',
                'scorecard_key': 'test_scorecard',
                'score_name': 'test_generator',
                'content_id': 'test_content'
            },
            results={},
            retry_count=0,
            completion=None,
            explanation=None
        )

        llm_prompt_node = generator.get_llm_prompt_node()
        llm_call_node = generator.get_llm_call_node()

        # Mock PlexusDashboardClient methods
        mock_client = MagicMock()
        mock_client._resolve_score_id.return_value = 'test_score_id'
        mock_client._resolve_scorecard_id.return_value = 'test_scorecard_id'
        mock_client._resolve_account_id.return_value = 'test_account_id'
        mock_client.batch_scoring_job.return_value = (
            MagicMock(id='test_scoring_job_id'),
            MagicMock(id='test_batch_job_id')
        )

        with patch('plexus.dashboard.api.client.PlexusDashboardClient.for_scorecard',
                  return_value=mock_client):
            # Run prompt node
            state_after_prompt = await llm_prompt_node(state)

            # Run LLM call node - should raise BatchProcessingPause
            with pytest.raises(BatchProcessingPause) as exc_info:
                await llm_call_node(state_after_prompt)

            # Verify BatchProcessingPause contains correct data
            assert exc_info.value.thread_id == 'test_content'
            assert exc_info.value.batch_job_id == 'test_batch_job_id'
            assert 'Execution paused for batch processing' in exc_info.value.message

@pytest.mark.asyncio
async def test_generator_retry_message_sequence(summary_generator_config):
    """Test the complete message sequence during retries."""
    mock_model = AsyncMock()
    responses = [
        AIMessage(content=""),  # First attempt: empty
        AIMessage(content="Finally, here's the summary.")  # Retry: success
    ]
    mock_model.ainvoke = AsyncMock(side_effect=responses)

    with patch('plexus.LangChainUser.LangChainUser._initialize_model',
               return_value=mock_model):
        generator = Generator(**summary_generator_config)
        generator.model = mock_model

        state = generator.GraphState(
            text="Summarize this long document about technology trends.",
            metadata={},
            results={},
            retry_count=0,
            completion=None,
            explanation=None
        )

        llm_prompt_node = generator.get_llm_prompt_node()
        llm_call_node = generator.get_llm_call_node()
        retry_node = generator.get_retry_node()

        # First attempt
        state = await llm_prompt_node(state)
        state = await llm_call_node(state)
        assert state.completion is None

        # Retry preparation
        state = await retry_node(state)
        assert state.retry_count == 1

        # Verify retry message was added to chat history
        assert len(state.chat_history) > 0
        retry_message = state.chat_history[-1]
        assert retry_message['type'] == 'human'
        assert "Please try generating a response again" in retry_message['content']
        assert "attempt 1 of" in retry_message['content']

        # Second attempt
        state = await llm_prompt_node(state)

        # Verify message sequence includes retry context
        assert len(state.messages) >= 2
        found_retry_message = any(
            msg.get('type') == 'human' and
            "Please try generating a response again" in msg.get('content', '')
            for msg in state.messages
        )
        assert found_retry_message, "Retry message should be in message sequence"

        final_state = await llm_call_node(state)
        assert final_state.completion == "Finally, here's the summary."
        assert final_state.retry_count == 1

def test_generator_should_retry_logic():
    """Test the should_retry logic without async components."""
    config = {
        "name": "test_generator",
        "system_message": "Test system message",
        "user_message": "Test user message: {text}",
        "model_provider": "AzureChatOpenAI",
        "model_name": "gpt-4",
        "maximum_retry_count": 3
    }

    generator = Generator(**config)

    # Test successful completion - with trace metadata
    success_state = generator.GraphState(
        text="test",
        completion="Generated content",
        explanation="Generated content",
        retry_count=0,
        metadata={
            'trace': {
                'node_results': [{
                    'node_name': 'test_generator',
                    'input': {},
                    'output': {'explanation': 'Generated content'}
                }]
            }
        }
    )

    assert generator.should_retry(success_state) == "end"

    # Test empty completion - with trace metadata showing failure
    empty_state = generator.GraphState(
        text="test",
        completion=None,
        explanation=None,
        retry_count=0,
        metadata={
            'trace': {
                'node_results': [{
                    'node_name': 'test_generator',
                    'input': {},
                    'output': {'explanation': 'No completion received from LLM'}
                }]
            }
        }
    )

    assert generator.should_retry(empty_state) == "retry"

    # Test max retries reached
    max_retry_state = generator.GraphState(
        text="test",
        completion=None,
        explanation=None,
        retry_count=3,
        metadata={
            'trace': {
                'node_results': [{
                    'node_name': 'test_generator',
                    'input': {},
                    'output': {'explanation': 'No completion received from LLM'}
                }]
            }
        }
    )

    assert generator.should_retry(max_retry_state) == "max_retries"

    # Test with explanation but no completion - with trace metadata
    partial_state = generator.GraphState(
        text="test",
        completion=None,
        explanation="Some explanation",
        retry_count=1,
        metadata={
            'trace': {
                'node_results': [{
                    'node_name': 'test_generator',
                    'input': {},
                    'output': {'explanation': 'Some explanation'}
                }]
            }
        }
    )

    assert generator.should_retry(partial_state) == "end"  # Has explanation, should end