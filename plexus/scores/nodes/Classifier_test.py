import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from plexus.scores.nodes.Classifier import Classifier
from langchain_core.messages import AIMessage

pytest.asyncio_fixture_scope = "function"
pytest_plugins = ('pytest_asyncio',)

@pytest.fixture(autouse=True)
def disable_batch_mode(monkeypatch):
    monkeypatch.setenv('PLEXUS_ENABLE_BATCH_MODE', 'false')
    monkeypatch.setenv('PLEXUS_ENABLE_LLM_BREAKPOINTS', 'false')

@pytest.fixture
def basic_config():
    return {
        "name": "test_classifier",
        "positive_class": "positive",
        "negative_class": "negative",
        "system_message": "You are a binary classifier.",
        "user_message": "Classify the following text: {text}",
        "model_provider": "AzureChatOpenAI",
        "model_name": "gpt-40-mini",
        "temperature": 0.0
    }

@pytest.fixture
def turnip_classifier_config():
    return {
        "name": "turnip_detector",
        "positive_class": "yes",
        "negative_class": "no",
        "system_message": "You are a classifier that detects if the word 'turnip' appears in text.",
        "user_message": "Does this text contain the word 'turnip'? Answer only yes or no: {text}",
        "model_provider": "AzureChatOpenAI",
        "model_name": "gpt-4",
        "temperature": 0.0
    }

@pytest.mark.asyncio
async def test_classifier_detects_turnip_present(turnip_classifier_config):
    mock_model = AsyncMock()
    mock_response = AIMessage(content="yes")
    mock_model.ainvoke = AsyncMock(return_value=mock_response)
    
    with patch('plexus.LangChainUser.LangChainUser._initialize_model', 
               return_value=mock_model):
        classifier = Classifier(**turnip_classifier_config)
        classifier.model = mock_model
        
        state = classifier.GraphState(
            text="I love eating turnip soup.",
            metadata={},
            results={},
            retry_count=0,
            is_not_empty=True,
            value=None,
            reasoning=None,
            classification=None,
            chat_history=[],
            completion=None
        )
        
        llm_prompt_node = classifier.get_llm_prompt_node()
        llm_call_node = classifier.get_llm_call_node()
        parse_node = classifier.get_parser_node()
        
        # Run prompt node
        state_after_prompt = await llm_prompt_node(state)
        # Run LLM call node
        state_after_llm = await llm_call_node(state_after_prompt)
        # Run parser node
        final_state = await parse_node(state_after_llm)
        
        assert final_state["classification"] == "yes"

@pytest.mark.asyncio
async def test_classifier_detects_turnip_absent(turnip_classifier_config):
    mock_model = AsyncMock()
    mock_response = AIMessage(content="no")
    mock_model.ainvoke = AsyncMock(return_value=mock_response)
    
    with patch('plexus.LangChainUser.LangChainUser._initialize_model', 
               return_value=mock_model):
        classifier = Classifier(**turnip_classifier_config)
        classifier.model = mock_model
        
        state = classifier.GraphState(
            text="I love eating potato soup.",
            metadata={},
            results={},
            retry_count=0,
            is_not_empty=True,
            value=None,
            reasoning=None,
            classification=None,
            chat_history=[],
            completion=None
        )
        
        llm_prompt_node = classifier.get_llm_prompt_node()
        llm_call_node = classifier.get_llm_call_node()
        parse_node = classifier.get_parser_node()
        
        # Run prompt node
        state_after_prompt = await llm_prompt_node(state)
        # Run LLM call node
        state_after_llm = await llm_call_node(state_after_prompt)
        # Run parser node
        final_state = await parse_node(state_after_llm)
        
        assert final_state["classification"] == "no"

@pytest.mark.asyncio
async def test_classifier_succeeds_after_retry(turnip_classifier_config):
    mock_model = AsyncMock()
    responses = [
        AIMessage(content="Well, let me analyze this carefully..."),
        AIMessage(content="yes")
    ]
    mock_model.ainvoke = AsyncMock(side_effect=responses)
    
    with patch('plexus.LangChainUser.LangChainUser._initialize_model', 
               return_value=mock_model):
        classifier = Classifier(**turnip_classifier_config)
        classifier.model = mock_model
        
        state = classifier.GraphState(
            text="I love eating turnip soup.",
            metadata={},
            results={},
            retry_count=0,
            is_not_empty=True,
            value=None,
            reasoning=None,
            classification=None,
            chat_history=[],
            completion=None
        )
        
        llm_prompt_node = classifier.get_llm_prompt_node()
        llm_call_node = classifier.get_llm_call_node()
        parse_node = classifier.get_parser_node()
        retry_node = classifier.get_retry_node()
        
        # First attempt
        state_after_prompt = await llm_prompt_node(state)
        state_after_llm = await llm_call_node(state_after_prompt)
        state_after_parse = await parse_node(state_after_llm)
        
        # Should need retry
        assert state_after_parse["classification"] is None
        
        # Retry attempt - clear completion to force new LLM call
        state_after_retry = await retry_node(state_after_parse)
        state_after_retry["completion"] = None
        state_after_prompt2 = await llm_prompt_node(state_after_retry)
        state_after_llm2 = await llm_call_node(state_after_prompt2)
        final_state = await parse_node(state_after_llm2)
        
        assert final_state["classification"] == "yes"
        assert final_state["retry_count"] == 1

@pytest.mark.asyncio
async def test_classifier_maximum_retries(turnip_classifier_config):
    mock_model = AsyncMock()
    responses = [
        AIMessage(content="Let me think about it..."),
        AIMessage(content="I need to analyze this further..."),
        AIMessage(content="Well, considering the text...")
    ]
    mock_model.ainvoke = AsyncMock(side_effect=responses)
    
    with patch('plexus.LangChainUser.LangChainUser._initialize_model', 
               return_value=mock_model):
        classifier = Classifier(**turnip_classifier_config)
        classifier.model = mock_model
        classifier.parameters.maximum_retry_count = 3
        
        initial_state = classifier.GraphState(
            text="I love eating turnip soup.",
            metadata={},
            results={},
            retry_count=0,
            is_not_empty=True,
            value=None,
            reasoning=None,
            classification=None,
            chat_history=[],
            completion=None
        )
        
        llm_prompt_node = classifier.get_llm_prompt_node()
        llm_call_node = classifier.get_llm_call_node()
        parse_node = classifier.get_parser_node()
        retry_node = classifier.get_retry_node()
        max_retries_node = classifier.get_max_retries_node()
        
        current_state = initial_state.model_dump()
        for _ in range(3):
            # Clear chat history and completion before each attempt
            current_state["chat_history"] = []
            current_state["completion"] = None
            
            current_state = await llm_prompt_node(current_state)
            current_state = await llm_call_node(current_state)
            current_state = await parse_node(current_state)
            if current_state["classification"] is None:
                current_state = await retry_node(current_state)
        
        final_state = await max_retries_node(current_state)
        
        assert final_state["classification"] == "unknown"
        assert final_state["explanation"] == "Maximum retries reached"
        assert final_state["retry_count"] == 3
        assert mock_model.ainvoke.call_count == 3

@pytest.mark.asyncio
async def test_classifier_parse_from_end_default(turnip_classifier_config):
    mock_model = AsyncMock()
    mock_response = AIMessage(
        content="Yes I see it here, but no is my final answer"
    )
    mock_model.ainvoke = AsyncMock(return_value=mock_response)
    
    with patch('plexus.LangChainUser.LangChainUser._initialize_model', 
               return_value=mock_model):
        classifier = Classifier(**turnip_classifier_config)
        classifier.model = mock_model

        state = classifier.GraphState(
            text="Does this contain a turnip?",
            metadata={},
            results={},
            retry_count=0,
            is_not_empty=True,
            value=None,
            reasoning=None,
            classification=None,
            chat_history=[],
            completion=None
        )

        llm_prompt_node = classifier.get_llm_prompt_node()
        llm_call_node = classifier.get_llm_call_node()
        parse_node = classifier.get_parser_node()

        state_after_prompt = await llm_prompt_node(state)
        state_after_llm = await llm_call_node(state_after_prompt)
        final_state = await parse_node(state_after_llm)

        assert final_state["classification"] == "no"
        # Ensures that when parse_from_start=False, it picks 'no'

@pytest.mark.asyncio
async def test_classifier_parse_from_start_explicit(turnip_classifier_config):
    mock_model = AsyncMock()
    mock_response = AIMessage(
        content="Yes is my answer, even though you might think no when you first look"
    )
    mock_model.ainvoke = AsyncMock(return_value=mock_response)

    with patch('plexus.LangChainUser.LangChainUser._initialize_model',
               return_value=mock_model):
        # Explicitly set parse_from_start to True
        turnip_classifier_config["parse_from_start"] = True
        classifier = Classifier(**turnip_classifier_config)
        classifier.model = mock_model

        state = classifier.GraphState(
            text="Does this contain a turnip?",
            metadata={},
            results={},
            retry_count=0,
            is_not_empty=True,
            value=None,
            reasoning=None,
            classification=None,
            chat_history=[],
            completion=None
        )

        llm_prompt_node = classifier.get_llm_prompt_node()
        llm_call_node = classifier.get_llm_call_node()
        parse_node = classifier.get_parser_node()

        state_after_prompt = await llm_prompt_node(state)
        state_after_llm = await llm_call_node(state_after_prompt)
        final_state = await parse_node(state_after_llm)

        assert final_state["classification"] == "yes"
        # Ensures that when parse_from_start=True, it picks 'yes'