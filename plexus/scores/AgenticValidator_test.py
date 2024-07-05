import pytest
from unittest.mock import Mock, patch, MagicMock
from plexus.scores.AgenticValidator import AgenticValidator, ValidationState, StepOutput
from langchain_core.messages import AIMessage
from langchain_core.language_models import BaseLanguageModel

# Add the sample transcript and metadata here
SAMPLE_TRANSCRIPT = """
I completed my Bachelor's degree in Computer Science at MIT through their online program.
"""

SAMPLE_METADATA = {
    "school": "MIT",
    "degree": "Bachelor's in Computer Science",
    "modality": "Online"
}

class MockLLM(MagicMock):
    def __init__(self, *args, **kwargs):
        super().__init__(spec=BaseLanguageModel, *args, **kwargs)
        self.__or__ = self._mock_or
        self.invoke = self._mock_invoke
        self.bind_tools = self._mock_bind_tools

    def _mock_or(self, other):
        return self

    def _mock_invoke(self, *args, **kwargs):
        return AIMessage(content="Mocked response")

    def _mock_bind_tools(self, *args, **kwargs):
        return self

@pytest.fixture
def validator():
    parameters = {
        "scorecard_name": "TestScorecard",
        "score_name": "TestScore",
        "data": {"percentage": 100},
        "model_provider": "BedrockChat",
        "model_name": "anthropic.claude-3-haiku-20240307-v1:0",
        "temperature": 0.3,
        "max_tokens": 500
    }
    
    return AgenticValidator(**parameters)

def test_initialization(validator):
    assert validator.llm is None
    assert validator.workflow is None

@pytest.mark.parametrize("provider,mock_class", [
    ("AzureChatOpenAI", "plexus.scores.AgenticValidator.AzureChatOpenAI"),
    ("BedrockChat", "plexus.scores.AgenticValidator.ChatBedrock"),
    ("ChatVertexAI", "plexus.scores.AgenticValidator.ChatVertexAI"),
])
def test_initialize_model(validator, provider, mock_class):
    with patch(mock_class) as mock_model:
        validator.parameters.model_provider = provider
        validator._initialize_model()
        mock_model.assert_called_once()

def test_create_workflow(validator):
    mock_llm = MockLLM()
    validator.llm = mock_llm
    
    workflow = validator._create_workflow()
    assert workflow is not None

def test_validate_single_item(validator):
    mock_llm = Mock()
    mock_llm.invoke.side_effect = [
        AIMessage(content="I can confirm the content of the transcript."),
        AIMessage(content="Yes: The transcript clearly mentions 'MIT' as the school.")
    ]
    validator.llm = mock_llm
    validator._call_llm = mock_llm.invoke
    validator.current_state = ValidationState(transcript=SAMPLE_TRANSCRIPT, metadata=SAMPLE_METADATA, current_step="")

    result = validator._validate_single_item("school", "MIT")

    assert result["school_validation"] == "Yes"
    assert "school_explanation" in result

def test_parse_llm_response(validator):
    response = AIMessage(content="Yes: The transcript clearly mentions MIT.")
    result = validator.parse_llm_response(response)

    assert result.result == "Yes"
    assert result.explanation == "The transcript clearly mentions MIT."

def test_validate_with_sample_transcript(validator):
    validator.llm = Mock()
    validator._validate_single_item = Mock(side_effect=[
        {"school_validation": "Yes", "school_explanation": "Found in transcript"},
        {"degree_validation": "Yes", "degree_explanation": "Found in transcript"},
        {"modality_validation": "Yes", "modality_explanation": "Found in transcript"}
    ])

    model_input = validator.ModelInput(transcript=SAMPLE_TRANSCRIPT, metadata=SAMPLE_METADATA)
    result = validator.predict(model_input)

    assert result.classification["school_validation"] == "Yes"
    assert result.classification["degree_validation"] == "Yes"
    assert result.classification["modality_validation"] == "Yes"
    assert result.classification["overall_validity"] == "Valid"
    assert isinstance(result.classification["explanation"], str)

    assert validator._validate_single_item.call_count == 3

@pytest.mark.parametrize("overall_validity,expected_relevance", [
    ("Valid", True),
    ("Partial", True),
    ("Invalid", False),
])
def test_is_relevant(validator, overall_validity, expected_relevance):
    validator.predict = Mock(return_value=validator.ModelOutput(
        classification={"overall_validity": overall_validity}
    ))
    assert validator.is_relevant("Sample transcript", {"school": "Sample School"}) == expected_relevance
