import pytest
from unittest.mock import Mock, patch, MagicMock
from plexus.scores.AgenticValidator import AgenticValidator, ValidationState
from langchain_core.messages import AIMessage
from langchain_core.language_models import BaseLanguageModel
from langchain_core.runnables import RunnableLambda

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
    
    with patch('plexus.scores.AgenticValidator.ChatBedrock'):
        return AgenticValidator(**parameters)

def test_initialization(validator):
    assert validator.llm is not None
    assert validator.workflow is not None
    assert validator.react_agent is not None

@pytest.mark.parametrize("provider,mock_class", [
    ("AzureChatOpenAI", "plexus.scores.AgenticValidator.AzureChatOpenAI"),
    ("BedrockChat", "plexus.scores.AgenticValidator.ChatBedrock"),
    ("ChatVertexAI", "plexus.scores.AgenticValidator.ChatVertexAI"),
])
def test_initialize_model(validator, provider, mock_class):
    with patch(mock_class) as mock_model:
        validator.parameters.model_provider = provider
        model = validator._initialize_model()
        mock_model.assert_called_once()
        # Instead of checking isinstance, we'll check if the mock was called
        assert mock_model.call_count == 1

def test_create_workflow(validator):
    workflow = validator._create_workflow()
    assert workflow is not None

def test_validate_step(validator):
    state = ValidationState(
        transcript=SAMPLE_TRANSCRIPT,
        metadata=SAMPLE_METADATA,
        current_step=""
    ).__dict__

    with patch.object(validator, 'react_agent') as mock_agent:
        mock_agent.invoke.return_value = {
            'messages': [AIMessage(content="Yes, the school is mentioned.")]
        }
        result = validator._validate_step(state, "school")

    assert "school" in result["validation_results"]
    assert result["validation_results"]["school"] in ["Valid", "Invalid", "Unclear"]
    assert "School:" in result["explanation"]

def test_determine_overall_validity(validator):
    assert validator._determine_overall_validity({"school": "Valid", "degree": "Valid", "modality": "Valid"}) == "Valid"
    assert validator._determine_overall_validity({"school": "Invalid", "degree": "Invalid", "modality": "Invalid"}) == "Invalid"
    assert validator._determine_overall_validity({"school": "Valid", "degree": "Invalid", "modality": "Valid"}) == "Partial"
    assert validator._determine_overall_validity({}) == "Unknown"

def test_parse_validation_result(validator):
    assert validator._parse_validation_result("Yes, the school is mentioned.") == ("Valid", "the school is mentioned.")
    assert validator._parse_validation_result("No, the degree is not mentioned.") == ("Invalid", "the degree is not mentioned.")
    # Check for the modified string without "It's" at the beginning
    result = validator._parse_validation_result("It's unclear from the transcript.")
    assert result[0] == "Unclear"
    assert result[1].strip() == "unclear from the transcript."

def test_predict(validator):
    with patch.object(validator, 'workflow') as mock_workflow:
        mock_workflow.invoke.return_value = {
            'validation_results': {
                'school': 'Valid',
                'degree': 'Valid',
                'modality': 'Valid'
            },
            'overall_validity': 'Valid',
            'explanation': 'Test explanation'
        }

        model_input = validator.ModelInput(transcript=SAMPLE_TRANSCRIPT, metadata=SAMPLE_METADATA)
        result = validator.predict(model_input)

    assert isinstance(result, validator.ModelOutput)
    assert result.score == "Valid"
    assert result.school_validation == "Valid"
    assert result.degree_validation == "Valid"
    assert result.modality_validation == "Valid"
    assert result.explanation == "Test explanation"

@pytest.mark.parametrize("overall_validity,expected_relevance", [
    ("Valid", True),
    ("Partial", True),
    ("Invalid", False),
])
def test_is_relevant(validator, overall_validity, expected_relevance):
    with patch.object(validator, 'predict') as mock_predict:
        mock_predict.return_value = validator.ModelOutput(
            score=overall_validity,
            school_validation="Valid",
            degree_validation="Valid",
            modality_validation="Valid",
            explanation="Test explanation"
        )
        assert validator.is_relevant("Sample transcript", {"school": "Sample School"}) == expected_relevance

# Integration Tests
@pytest.mark.integration
def test_validation_with_real_model(validator):
    input_data = validator.ModelInput(
        transcript=SAMPLE_TRANSCRIPT,
        metadata=SAMPLE_METADATA
    )
    
    result = validator.predict(input_data)
    
    assert result.score in ["Valid", "Invalid", "Partial", "Unknown"]
    assert result.school_validation in ["Valid", "Invalid", "Unclear"]
    assert result.degree_validation in ["Valid", "Invalid", "Unclear"]
    assert result.modality_validation in ["Valid", "Invalid", "Unclear"]
    assert isinstance(result.explanation, str)

@pytest.mark.integration
def test_validation_with_mismatched_data(validator):
    input_data = validator.ModelInput(
        transcript="I graduated from Harvard with a Master's in Biology.",
        metadata=SAMPLE_METADATA
    )
    
    result = validator.predict(input_data)
    
    assert result.score in ["Invalid", "Partial", "Unknown"]
    assert "Unclear" in [result.school_validation, 
                         result.degree_validation, 
                         result.modality_validation]
    assert not all(validation == "Valid" for validation in 
                   [result.school_validation, result.degree_validation, result.modality_validation])

@pytest.mark.integration
def test_retry_mechanism_integration(validator):
    call_count = 0
    original_invoke = RunnableLambda.invoke

    def mock_invoke(self, *args, **kwargs):
        nonlocal call_count
        call_count += 1
        if call_count < 3:
            raise Exception("Simulated error")
        return original_invoke(self, *args, **kwargs)

    with patch.object(RunnableLambda, 'invoke', side_effect=mock_invoke):
        input_data = validator.ModelInput(
            transcript=SAMPLE_TRANSCRIPT,
            metadata=SAMPLE_METADATA
        )
        
        result = validator.predict(input_data)
        
        assert result.score in ["Valid", "Invalid", "Partial", "Unknown"]
        assert call_count == 9
