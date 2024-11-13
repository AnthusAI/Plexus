import os
from dotenv import load_dotenv
import pytest
from unittest.mock import patch, MagicMock
from plexus.scores.AgenticValidator import AgenticValidator, ValidationState, SchoolInfo
from langchain_core.messages import AIMessage
from langchain_core.language_models import BaseLanguageModel

# Load environment variables
load_dotenv("../../../Call-Criteria-Python/.env")

# Set up LangSmith API key
if os.getenv("LANGCHAIN_API_KEY"):
    os.environ["LANGCHAIN_API_KEY"] = os.getenv("LANGCHAIN_API_KEY")

# Add the sample transcript and metadata here
SAMPLE_TRANSCRIPT = """
I completed my Bachelor's degree in Computer Science at MIT through their online program.
"""

SAMPLE_METADATA = {
    "school": "MIT",
    "degree": "Bachelor's in Computer Science",
    "modality": "Online",
    "test_label": "Sample test label value"
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

@pytest.fixture(scope="module", autouse=True)
def setup_environment():
    # This fixture will run once for the module and set up the environment
    original_env = dict(os.environ)
    load_dotenv()
    yield
    # Restore original environment after tests
    os.environ.clear()
    os.environ.update(original_env)

@pytest.fixture
def validator():
    parameters = {
        "scorecard_name": "TestScorecard",
        "score_name": "TestScore",
        "data": {"percentage": 100},
        "model_provider": "BedrockChat",
        "model_name": "anthropic.claude-3-haiku-20240307-v1:0",
        "temperature": 0.3,
        "max_tokens": 500,
        "label": "test_label",
        "prompt": "Test prompt {label_value}",
        "agent_type": "react",
        "graph": [
            {
                "name": "chatbot",
                "class": "plexus.scores.AgenticValidator.AgenticValidator",
                "model_provider": "BedrockChat",
                "model_name": "anthropic.claude-3-haiku-20240307-v1:0"
            },
            {
                "name": "tools",
                "class": "plexus.scores.AgenticValidator.AgenticValidator",
                "model_provider": "BedrockChat",
                "model_name": "anthropic.claude-3-haiku-20240307-v1:0"
            }
        ]
    }
    
    with patch('langchain_community.chat_models.bedrock.BedrockChat', MagicMock()):
        return AgenticValidator(**parameters)

def test_initialization(validator):
    assert validator.llm is not None
    assert validator.workflow is not None
    assert validator.agent_executor is not None  # Changed from react_agent to agent_executor

@pytest.mark.parametrize("provider,mock_class", [
    ("AzureChatOpenAI", "langchain_community.chat_models.azure_openai.AzureChatOpenAI"),
    ("BedrockChat", "langchain_community.chat_models.bedrock.BedrockChat"),
    ("ChatVertexAI", "langchain_community.chat_models.vertexai.ChatVertexAI"),
])
def test_initialize_model(validator, provider, mock_class):
    with patch(mock_class) as mock_model:
        validator.parameters.model_provider = provider
        model = validator._initialize_model()
        mock_model.assert_called_once()
        assert mock_model.call_count == 1

def test_create_workflow(validator):
    if validator.parameters.agent_type == "react":
        workflow = validator._create_react_workflow()
    else:
        workflow = validator._create_langgraph_workflow()
    assert workflow is not None

def test_validate_step(validator):
    state = ValidationState(
        text=SAMPLE_TRANSCRIPT,
        metadata=SAMPLE_METADATA,
        current_step=""
    )

    with patch.object(validator, 'agent_executor') as mock_agent:
        mock_agent.invoke.return_value = {
            'output': "Yes, the school is mentioned."
        }
        result = validator._validate_step(state)

    assert result.validation_result in ["Yes", "No", "Unclear"]
    assert "Validation failed due to technical issues" in result.explanation

def test_parse_validation_result(validator):
    assert validator._parse_validation_result("Yes, the school is mentioned.") == ("Yes", "the school is mentioned.")
    assert validator._parse_validation_result("No, the degree is not mentioned.") == ("No", "the degree is not mentioned.")
    result = validator._parse_validation_result("It's unclear from the transcript.")
    assert result[0] == "Unclear"
    assert result[1].strip() == "unclear from the transcript."

@pytest.mark.parametrize("agent_type,final_state,expected_result", [
    (
        "react",
        ValidationState(
            text=SAMPLE_TRANSCRIPT,
            metadata=SAMPLE_METADATA,
            validation_result='Yes',
            explanation='The transcript confirms the degree.',
            current_step='main_validation'
        ),
        ("Yes", "The transcript confirms the degree.")
    ),
    (
        "langgraph",
        {
            'all_information_provided': True,
            'parsed_schools': [
                SchoolInfo(school_name="MIT", modality="Online", program="Computer Science", level="Bachelor's")
            ]
        },
        ("Yes", "All required information was provided.")
    ),
    (
        "langgraph",
        {
            'all_information_provided': False,
            'parsed_schools': []
        },
        ("No", "Some information was missing or unclear.")
    )
])
def test_predict(validator, agent_type, final_state, expected_result):
    validator.parameters.agent_type = agent_type
    
    with patch.object(validator, 'workflow') as mock_workflow, \
         patch.object(validator, 'get_token_usage') as mock_get_token_usage, \
         patch('openai_cost_calculator.openai_cost_calculator.calculate_cost') as mock_calculate_cost:
        
        mock_workflow.invoke.return_value = final_state
        mock_get_token_usage.return_value = {
            'successful_requests': 1,
            'total_tokens': 100,
            'prompt_tokens': 50,
            'completion_tokens': 50
        }
        mock_calculate_cost.return_value = {'total_cost': 0.001}

        model_input = validator.Input(text=SAMPLE_TRANSCRIPT, metadata=SAMPLE_METADATA)
        context = {}
        result = validator.predict(context, model_input)

    assert isinstance(result, list)
    assert len(result) == 1
    assert isinstance(result[0], validator.Result)
    assert result[0].value == expected_result[0]
    assert expected_result[1] in result[0].explanation

# Integration Tests
@pytest.mark.integration
def test_validation_with_real_model(validator):
    input_data = validator.Input(
        text=SAMPLE_TRANSCRIPT,
        metadata=SAMPLE_METADATA
    )
    
    context = {}
    results = validator.predict(context, model_input=input_data)
    
    assert isinstance(results, list)
    assert len(results) > 0
    result = results[0]
    
    assert result.score in ["Yes", "No", "Unclear"]
    assert isinstance(result.explanation, str)

@pytest.mark.integration
def test_validation_with_mismatched_data(validator):
    input_data = validator.Input(
        text="I graduated from Harvard with a Master's in Biology.",
        metadata=SAMPLE_METADATA
    )
    
    context = {}
    results = validator.predict(context, model_input=input_data)
    
    assert isinstance(results, list)
    assert len(results) > 0
    result = results[0]
    
    assert result.score in ["No", "Unclear"]
    assert isinstance(result.explanation, str)