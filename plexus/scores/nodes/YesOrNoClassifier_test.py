import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from plexus.scores.nodes.YesOrNoClassifier import YesOrNoClassifier
from typing import Optional
from pydantic import BaseModel, Field
from langchain_core.prompts import ChatPromptTemplate

pytest.asyncio_fixture_scope = "function"
pytest_plugins = ('pytest_asyncio',)

@pytest.fixture
def basic_classifier_config():
    return {
        "name": "test_classifier",
        "prompt_template": "Is this text positive? {text}",
        "model_provider": "AzureChatOpenAI",
        "model_name": "gpt-4",
        "temperature": 0.0,
        "parse_from_start": True,
        "maximum_retry_count": 2,
        "azure_deployment": "test-deployment",
        "openai_api_version": "2023-05-15",
        "azure_endpoint": "https://test.openai.azure.com"
    }

@pytest.fixture
def mock_model():
    mock = MagicMock()
    mock.invoke = MagicMock()
    return mock

@pytest.fixture
def mock_prompt():
    return ChatPromptTemplate.from_template("Is this text positive? {text}")

def test_output_parser_yes():
    parser = YesOrNoClassifier.ClassificationOutputParser(parse_from_start=True)
    result = parser.parse("Yes, this is positive")
    assert result["classification"] == "yes"
    assert result["explanation"] == "Yes, this is positive"

def test_output_parser_no():
    parser = YesOrNoClassifier.ClassificationOutputParser(parse_from_start=True)
    result = parser.parse("No, this is negative")
    assert result["classification"] == "no"
    assert result["explanation"] == "No, this is negative"

def test_output_parser_unclear():
    parser = YesOrNoClassifier.ClassificationOutputParser(parse_from_start=True)
    result = parser.parse("This is unclear")
    assert result["classification"] == "unknown"
    assert result["explanation"] == "This is unclear"

def test_output_parser_parse_from_end():
    parser = YesOrNoClassifier.ClassificationOutputParser(parse_from_start=False)
    result = parser.parse("The answer to this question is yes")
    assert result["classification"] == "yes"

def test_output_parser_with_punctuation():
    parser = YesOrNoClassifier.ClassificationOutputParser(parse_from_start=True)
    result = parser.parse("Yes! This is definitely positive.")
    assert result["classification"] == "yes"

@pytest.mark.xfail(reason="Chain validation issues need to be resolved")
@pytest.mark.asyncio
async def test_classifier_basic_flow(basic_classifier_config, mock_model, mock_prompt):
    with patch('plexus.LangChainUser.LangChainUser._initialize_model', return_value=mock_model):
        classifier = YesOrNoClassifier(**basic_classifier_config)
        
        # Mock the get_prompt_templates method
        with patch.object(classifier, 'get_prompt_templates', return_value=[mock_prompt]) as mock_get_prompts:
            # Create a mock response object
            mock_response = MagicMock()
            mock_response.content = "Yes, this is positive"
            
            # Mock the chain's invoke method
            mock_chain = MagicMock()
            mock_chain.invoke = MagicMock(return_value=mock_response.content)
            mock_model.invoke = mock_chain.invoke

            state = classifier.GraphState(
                text="This is a test",
                metadata={},
                results={},
                classification=None,
                explanation=None,
                retry_count=0,
                is_not_empty=True,
                value="",
                reasoning=""
            )

            classifier_node = classifier.get_classifier_node()
            result = classifier_node(state)

            assert result["classification"] == "yes"
            assert "Yes, this is positive" in result["explanation"]

@pytest.mark.xfail(reason="Chain validation issues need to be resolved")
@pytest.mark.asyncio
async def test_classifier_with_retries(basic_classifier_config, mock_model, mock_prompt):
    with patch('plexus.LangChainUser.LangChainUser._initialize_model', return_value=mock_model):
        classifier = YesOrNoClassifier(**basic_classifier_config)
        
        # Mock the get_prompt_templates method
        with patch.object(classifier, 'get_prompt_templates', return_value=[mock_prompt]) as mock_get_prompts:
            # Create mock responses
            maybe_response = MagicMock()
            maybe_response.content = "Maybe"
            yes_response = MagicMock()
            yes_response.content = "Yes"
            
            # Mock the chain's invoke method
            mock_chain = MagicMock()
            mock_chain.invoke = MagicMock(side_effect=[maybe_response.content, yes_response.content])
            mock_model.invoke = mock_chain.invoke

            state = classifier.GraphState(
                text="This is a test",
                metadata={},
                results={},
                classification=None,
                explanation=None,
                retry_count=0,
                is_not_empty=True,
                value="",
                reasoning=""
            )

            classifier_node = classifier.get_classifier_node()
            result = classifier_node(state)

            assert result["classification"] == "yes"
            assert result["retry_count"] == 1

@pytest.mark.xfail(reason="Chain validation issues need to be resolved")
@pytest.mark.asyncio
async def test_classifier_max_retries(basic_classifier_config, mock_model, mock_prompt):
    with patch('plexus.LangChainUser.LangChainUser._initialize_model', return_value=mock_model):
        classifier = YesOrNoClassifier(**basic_classifier_config)
        
        # Mock the get_prompt_templates method
        with patch.object(classifier, 'get_prompt_templates', return_value=[mock_prompt]) as mock_get_prompts:
            # Mock the model to always give unclear responses
            fake_unclear_response = MagicMock()
            fake_unclear_response.content = "Maybe"
            mock_model.invoke.return_value = fake_unclear_response

            state = classifier.GraphState(
                text="This is a test",
                metadata={},
                results={},
                classification=None,
                explanation=None,
                retry_count=0,
                is_not_empty=True,
                value="",
                reasoning=""
            )

            classifier_node = classifier.get_classifier_node()
            result = classifier_node(state)

            assert result["classification"] == "unknown"
            assert result["retry_count"] == basic_classifier_config["maximum_retry_count"]

@pytest.mark.xfail(reason="Chain validation issues need to be resolved")
@pytest.mark.asyncio
async def test_classifier_with_explanation_message(basic_classifier_config, mock_model, mock_prompt):
    config = basic_classifier_config.copy()
    config["explanation_message"] = "Please explain your classification"

    with patch('plexus.LangChainUser.LangChainUser._initialize_model', return_value=mock_model):
        classifier = YesOrNoClassifier(**config)
        
        # Mock the get_prompt_templates method
        with patch.object(classifier, 'get_prompt_templates', return_value=[mock_prompt]) as mock_get_prompts:
            # Create mock responses
            yes_response = MagicMock()
            yes_response.content = "Yes"
            explanation_response = MagicMock()
            explanation_response.content = "This is positive because..."
            
            # Mock the chain's invoke method
            mock_chain = MagicMock()
            mock_chain.invoke = MagicMock(side_effect=[yes_response.content, explanation_response.content])
            mock_model.invoke = mock_chain.invoke

            state = classifier.GraphState(
                text="This is a test",
                metadata={},
                results={},
                classification=None,
                explanation=None,
                retry_count=0,
                is_not_empty=True,
                value="",
                reasoning=""
            )

            classifier_node = classifier.get_classifier_node()
            result = classifier_node(state)

            assert result["classification"] == "yes"
            assert result["explanation"] == "This is positive because..."

def test_classifier_parameters():
    config = {
        "name": "test",
        "prompt_template": "test {text}",
        "parse_from_start": True,
        "maximum_retry_count": 5,
        "explanation_message": "Explain",
        "model_provider": "AzureChatOpenAI",
        "model_name": "gpt-4",
        "azure_deployment": "test-deployment",
        "api_version": "2023-05-15",
        "azure_endpoint": "https://test.openai.azure.com"
    }
    
    with patch('plexus.LangChainUser.LangChainUser._initialize_model') as mock_init:
        classifier = YesOrNoClassifier(**config)
        assert classifier.parameters.parse_from_start == True
        assert classifier.parameters.maximum_retry_count == 5
        assert classifier.parameters.explanation_message == "Explain"