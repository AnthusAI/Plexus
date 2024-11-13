import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from plexus.scores.nodes.Classifier import Classifier
from langchain_core.messages import AIMessage

pytest.asyncio_fixture_scope = "function"
pytest_plugins = ('pytest_asyncio',)

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
    mock_model.invoke = AsyncMock(return_value=AIMessage(content="yes"))
    
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
            explanation=None,
            reasoning=None,
            classification=None,
            chat_history=[],
            completion=None
        )
        
        llm_node = classifier.get_llm_node()
        parse_node = classifier.get_parser_node()
        
        # Run LLM node
        state_after_llm = await llm_node(state)
        # Run parser node
        final_state = await parse_node(state_after_llm)
        
        assert final_state["classification"] == "yes"

@pytest.mark.asyncio
async def test_classifier_detects_turnip_absent(turnip_classifier_config):
    mock_model = AsyncMock()
    mock_model.invoke = AsyncMock(return_value=AIMessage(content="no"))
    
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
            explanation=None,
            reasoning=None,
            classification=None,
            chat_history=[],
            completion=None
        )
        
        llm_node = classifier.get_llm_node()
        parse_node = classifier.get_parser_node()
        
        # Run LLM node
        state_after_llm = await llm_node(state)
        # Run parser node
        final_state = await parse_node(state_after_llm)
        
        assert final_state["classification"] == "no"

@pytest.mark.asyncio
async def test_classifier_succeeds_after_retry(turnip_classifier_config):
    mock_model = AsyncMock()
    mock_model.invoke = AsyncMock()
    mock_model.invoke.side_effect = [
        AIMessage(content="Well, let me analyze this carefully..."),
        AIMessage(content="yes")
    ]
    
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
            explanation=None,
            reasoning=None,
            classification=None,
            chat_history=[],
            completion=None
        )
        
        llm_node = classifier.get_llm_node()
        parse_node = classifier.get_parser_node()
        retry_node = classifier.get_retry_node()
        
        # First attempt
        state_after_llm = await llm_node(state)
        state_after_parse = await parse_node(state_after_llm)
        
        # Should need retry
        assert state_after_parse["classification"] is None
        
        # Retry attempt
        state_after_retry = await retry_node(state_after_parse)
        state_after_llm2 = await llm_node(state_after_retry)
        final_state = await parse_node(state_after_llm2)
        
        assert final_state["classification"] == "yes"
        assert final_state["retry_count"] == 1

@pytest.mark.asyncio
async def test_classifier_maximum_retries(turnip_classifier_config):
    mock_model = AsyncMock()
    mock_model.invoke = AsyncMock()
    mock_model.invoke.side_effect = [
        AIMessage(content="Let me think about it..."),
        AIMessage(content="I need to analyze this further..."),
        AIMessage(content="Well, considering the text...")
    ]
    
    with patch('plexus.LangChainUser.LangChainUser._initialize_model', 
               return_value=mock_model):
        classifier = Classifier(**turnip_classifier_config)
        classifier.model = mock_model
        classifier.parameters.maximum_retry_count = 3
        
        state = classifier.GraphState(
            text="I love eating turnip soup.",
            metadata={},
            results={},
            retry_count=0,
            is_not_empty=True,
            value=None,
            explanation=None,
            reasoning=None,
            classification=None,
            chat_history=[],
            completion=None
        )
        
        llm_node = classifier.get_llm_node()
        parse_node = classifier.get_parser_node()
        retry_node = classifier.get_retry_node()
        max_retries_node = classifier.get_max_retries_node()
        
        current_state = state
        for _ in range(3):
            current_state = await llm_node(current_state)
            current_state = await parse_node(current_state)
            if current_state["classification"] is None:
                current_state = await retry_node(current_state)
        
        final_state = await max_retries_node(current_state)
        
        assert final_state["classification"] == "unknown"
        assert final_state["explanation"] == "Maximum retries reached"
        assert final_state["retry_count"] == 3
        assert mock_model.invoke.call_count == 3

@pytest.mark.asyncio
async def test_classifier_parse_from_end_default(turnip_classifier_config):
    mock_model = AsyncMock()
    # Response contains both 'yes' and 'no', with 'no' at the end
    mock_model.invoke = AsyncMock(return_value=AIMessage(content="Yes I see it here, but no is my final answer"))
    
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
            explanation=None,
            reasoning=None,
            classification=None,
            chat_history=[],
            completion=None
        )

        llm_node = classifier.get_llm_node()
        parse_node = classifier.get_parser_node()

        state_after_llm = await llm_node(state)
        final_state = await parse_node(state_after_llm)

        assert final_state["classification"] == "no"
        # Ensures that when parse_from_start=False, it picks 'no'

@pytest.mark.asyncio
async def test_classifier_parse_from_start_explicit(turnip_classifier_config):
    mock_model = AsyncMock()
    # Response contains both 'yes' and 'no', with 'yes' at the start
    mock_model.invoke = AsyncMock(return_value=AIMessage(
        content="Yes is my answer, even though you might think no when you first look"
    ))

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
            explanation=None,
            reasoning=None,
            classification=None,
            chat_history=[],
            completion=None
        )

        llm_node = classifier.get_llm_node()
        parse_node = classifier.get_parser_node()

        state_after_llm = await llm_node(state)
        final_state = await parse_node(state_after_llm)

        assert final_state["classification"] == "yes"
        # Ensures that when parse_from_start=True, it picks 'yes'