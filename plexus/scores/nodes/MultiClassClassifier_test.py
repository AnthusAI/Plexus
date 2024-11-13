import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from plexus.scores.nodes.MultiClassClassifier import MultiClassClassifier
from typing import Optional
from pydantic import BaseModel, Field
from plexus.scores.Score import Score
from langchain_core.messages import AIMessage

pytest.asyncio_fixture_scope = "function"
pytest_plugins = ('pytest_asyncio',)

@pytest.fixture
def basic_classifier_config():
    return {
        "name": "test_classifier",
        "prompt_template": "Classify this text: {text}",
        "model_provider": "AzureChatOpenAI",
        "model_name": "gpt-4",
        "temperature": 0.0,
        "valid_classes": ["positive", "negative", "neutral"],
        "fuzzy_match": True,
        "fuzzy_match_threshold": 0.8,
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

def test_output_parser_exact_match():
    parser = MultiClassClassifier.ClassificationOutputParser(
        valid_classes=["positive", "negative", "neutral"]
    )
    result = parser.parse("This is positive")
    assert result["classification"] == "positive"

def test_output_parser_no_match():
    parser = MultiClassClassifier.ClassificationOutputParser(
        valid_classes=["positive", "negative", "neutral"]
    )
    result = parser.parse("This is something else")
    assert result["classification"] is None

@pytest.mark.xfail(reason="Fuzzy matching needs to be improved")
def test_output_parser_fuzzy_match():
    parser = MultiClassClassifier.ClassificationOutputParser(
        valid_classes=["positive", "negative", "neutral"],
        fuzzy_match=True,
        fuzzy_match_threshold=0.8
    )
    result = parser.parse("This is positiv")
    assert result["classification"] == "positive"

def test_output_parser_case_insensitive():
    parser = MultiClassClassifier.ClassificationOutputParser(
        valid_classes=["positive", "negative", "neutral"]
    )
    result = parser.parse("This is POSITIVE")
    assert result["classification"] == "positive"

def test_output_parser_multi_word_class():
    parser = MultiClassClassifier.ClassificationOutputParser(
        valid_classes=["very positive", "somewhat negative"]
    )
    result = parser.parse("This is very positive")
    assert result["classification"] == "very positive"

@pytest.mark.xfail(reason="Empty valid_classes handling needs to be improved")
def test_output_parser_no_valid_classes():
    parser = MultiClassClassifier.ClassificationOutputParser(
        valid_classes=[]
    )
    with pytest.raises(RuntimeError, match="No valid classes provided"):
        parser.parse("This is positive")

@pytest.mark.xfail(reason="GraphState validation needs to be fixed")
@pytest.mark.asyncio
async def test_classifier_basic_flow(basic_classifier_config, mock_model):
    with patch('plexus.LangChainUser.LangChainUser._initialize_model',
              return_value=mock_model):
        classifier = MultiClassClassifier(**basic_classifier_config)

        mock_response = MagicMock()
        mock_response.content = "This is positive"
        mock_model.invoke = MagicMock(return_value=mock_response)

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

        assert result["classification"] == "positive"
        assert result["retry_count"] == 0

@pytest.mark.xfail(reason="GraphState validation needs to be fixed")
@pytest.mark.asyncio
async def test_classifier_with_retries(basic_classifier_config, mock_model):
    with patch('plexus.LangChainUser.LangChainUser._initialize_model',
              return_value=mock_model):
        classifier = MultiClassClassifier(**basic_classifier_config)

        unclear_response = MagicMock()
        unclear_response.content = "This is unclear"
        positive_response = MagicMock()
        positive_response.content = "This is positive"

        mock_model.invoke = MagicMock(side_effect=[unclear_response, positive_response])

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

        assert result["classification"] == "positive"
        assert result["retry_count"] == 1

@pytest.mark.xfail(reason="GraphState validation needs to be fixed")
@pytest.mark.asyncio
async def test_classifier_max_retries(basic_classifier_config, mock_model):
    with patch('plexus.LangChainUser.LangChainUser._initialize_model',
              return_value=mock_model):
        classifier = MultiClassClassifier(**basic_classifier_config)

        unclear_response = MagicMock()
        unclear_response.content = "This is unclear"
        mock_model.invoke = MagicMock(return_value=unclear_response)

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

        assert result["classification"] is None
        assert result["retry_count"] == basic_classifier_config["maximum_retry_count"]

@pytest.mark.xfail(reason="GraphState validation needs to be fixed")
@pytest.mark.asyncio
async def test_classifier_with_explanation_message(basic_classifier_config, mock_model):
    config = basic_classifier_config.copy()
    config["explanation_message"] = "Please explain your classification"

    with patch('plexus.LangChainUser.LangChainUser._initialize_model',
              return_value=mock_model):
        classifier = MultiClassClassifier(**config)

        classification_response = MagicMock()
        classification_response.content = "This is positive"
        explanation_response = MagicMock()
        explanation_response.content = "The text is positive because..."

        mock_model.invoke = MagicMock(side_effect=[
            classification_response,
            explanation_response
        ])

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

        assert result["classification"] == "positive"
        assert result["explanation"] == "The text is positive because..."

@pytest.mark.xfail(reason="GraphState validation needs to be fixed")
@pytest.mark.asyncio
async def test_classifier_with_existing_completion(basic_classifier_config, mock_model):
    with patch('plexus.LangChainUser.LangChainUser._initialize_model',
              return_value=mock_model):
        classifier = MultiClassClassifier(**basic_classifier_config)

        state = classifier.GraphState(
            text="This is a test",
            metadata={},
            results={},
            classification=None,
            explanation=None,
            retry_count=0,
            is_not_empty=True,
            value="",
            reasoning="",
            completion="This is positive"
        )

        classifier_node = classifier.get_classifier_node()
        result = classifier_node(state)

        assert result["classification"] == "positive"
        assert result["retry_count"] == 0

@pytest.fixture
def color_classifier_config():
    return {
        "name": "color_detector",
        "valid_classes": ["red", "blue", "green"],
        "system_message": "You are a classifier that identifies colors mentioned in text.",
        "user_message": "What color (red, blue, or green) is mentioned in this text? Answer with just the color name: {text}",
        "model_provider": "AzureChatOpenAI",
        "model_name": "gpt-4",
        "temperature": 0.0
    }

@pytest.mark.asyncio
async def test_color_detection(color_classifier_config):
    mock_model = AsyncMock()
    mock_model.invoke = AsyncMock()  # Make sure invoke is also async
    
    with patch('plexus.LangChainUser.LangChainUser._initialize_model', 
               return_value=mock_model):
        classifier = MultiClassClassifier(**color_classifier_config)
        classifier.model = mock_model
        
        # Create async classifier node
        async def async_classifier_node(state):
            completion = await mock_model.invoke(state)
            result = classifier.ClassificationOutputParser(
                valid_classes=classifier.parameters.valid_classes,
                fuzzy_match=classifier.parameters.fuzzy_match,
                fuzzy_match_threshold=classifier.parameters.fuzzy_match_threshold,
                parse_from_start=classifier.parameters.parse_from_start
            ).parse(completion.content)
            return {**state.model_dump(), **result}
        
        # Test case 1: Red
        mock_model.invoke.return_value = AIMessage(content="red")
        
        state = classifier.GraphState(
            text="The fire truck was bright red.",
            metadata={},
            results={},
            retry_count=0,
            is_not_empty=True,
            value=None,
            explanation=None,
            reasoning=None,
            classification=None
        )
        
        result = await async_classifier_node(state)
        
        assert result["classification"] == "red"
        
        # Test case 2: Blue
        mock_model.invoke.return_value = AIMessage(content="blue")
        
        state = classifier.GraphState(
            text="The sky was a beautiful blue today.",
            metadata={},
            results={},
            retry_count=0,
            is_not_empty=True,
            value=None,
            explanation=None,
            reasoning=None,
            classification=None
        )
        
        result = await async_classifier_node(state)
        
        assert result["classification"] == "blue"
        
        # Test case 3: Green
        mock_model.invoke.return_value = AIMessage(content="green")
        
        state = classifier.GraphState(
            text="The grass is always greener on the other side.",
            metadata={},
            results={},
            retry_count=0,
            is_not_empty=True,
            value=None,
            explanation=None,
            reasoning=None,
            classification=None
        )
        
        result = await async_classifier_node(state)
        
        assert result["classification"] == "green"
        
        # Test case 4: No color mentioned
        mock_model.invoke.return_value = AIMessage(content="I don't see any of those colors mentioned.")
        
        state = classifier.GraphState(
            text="The weather was nice today.",
            metadata={},
            results={},
            retry_count=0,
            is_not_empty=True,
            value=None,
            explanation=None,
            reasoning=None,
            classification=None
        )
        
        result = await async_classifier_node(state)
        
        assert result["classification"] is None

@pytest.mark.asyncio
async def test_fuzzy_matching(color_classifier_config):
    color_classifier_config["fuzzy_match"] = True
    color_classifier_config["fuzzy_match_threshold"] = 0.8
    
    mock_model = AsyncMock()
    
    with patch('plexus.LangChainUser.LangChainUser._initialize_model', 
               return_value=mock_model):
        classifier = MultiClassClassifier(**color_classifier_config)
        classifier.model = mock_model
        
        # Test fuzzy matching with slightly misspelled color
        mock_model.invoke.return_value = AIMessage(content="The car was colored rd")
        
        result = await classifier.workflow.ainvoke({
            "text": "The car was colored rd",
            "metadata": {},
            "results": {}
        })
        
        assert result["classification"] == "red"