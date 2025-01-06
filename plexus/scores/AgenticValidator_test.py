import os
from dotenv import load_dotenv
import pytest
import pytest_asyncio
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
    load_dotenv(override=True)
    yield
    # Restore original environment after tests
    os.environ.clear()
    os.environ.update(original_env)

@pytest_asyncio.fixture
async def validator():
    validator = AgenticValidator(
        name="TestScore",
        scorecard_name="TestScorecard",
        data={'percentage': 100.0},
        model_provider="BedrockChat",
        model_name="anthropic.claude-3-haiku-20240307-v1:0",
        temperature=0.3,
        max_tokens=500,
        graph=[
            {
                'name': 'chatbot',
                'class': 'AgenticValidator',
                'model_provider': 'BedrockChat',
                'model_name': 'anthropic.claude-3-haiku-20240307-v1:0'
            },
            {
                'name': 'tools',
                'class': 'AgenticValidator',
                'model_provider': 'BedrockChat',
                'model_name': 'anthropic.claude-3-haiku-20240307-v1:0'
            }
        ]
    )
    await validator.async_setup()
    return validator

@pytest.mark.skip(reason="Failing due to build_compiled_workflow argument mismatch")
@pytest.mark.asyncio
async def test_initialization(validator):
    assert validator.model is not None
    assert validator.workflow is not None
    assert validator.parameters is not None

@pytest.mark.skip(reason="Failing due to build_compiled_workflow argument mismatch")
@pytest.mark.asyncio
@pytest.mark.parametrize("provider,mock_class", [
    ("AzureChatOpenAI", "langchain_community.chat_models.azure_openai.AzureChatOpenAI"),
    ("BedrockChat", "langchain_aws.ChatBedrock"),
    ("ChatVertexAI", "langchain_community.chat_models.vertexai.ChatVertexAI"),
])
async def test_initialize_model(validator, provider, mock_class):
    with patch(mock_class) as mock_model:
        mock_instance = MagicMock()
        mock_model.return_value = mock_instance
        mock_instance.with_retry.return_value = mock_instance
        mock_instance.with_config.return_value = mock_instance
        mock_instance.agenerate = MagicMock()
        
        validator.parameters.model_provider = provider
        model = await validator._ainitialize_model()
        
        mock_model.assert_called_once()
        assert model == mock_instance

@pytest.mark.skip(reason="Failing due to build_compiled_workflow argument mismatch")
@pytest.mark.asyncio
async def test_create_workflow(validator):
    workflow = await validator.build_compiled_workflow()
    assert workflow is not None

@pytest.mark.skip(reason="Failing due to build_compiled_workflow argument mismatch")
@pytest.mark.asyncio
async def test_parse_validation_result(validator):
    assert await validator._parse_validation_result("Yes, the school is mentioned.") == ("Yes", "the school is mentioned.")
    assert await validator._parse_validation_result("No, the degree is not mentioned.") == ("No", "the degree is not mentioned.")
    result = await validator._parse_validation_result("It's unclear from the transcript.")
    assert result[0] == "Unclear"
    assert "unclear from the transcript" in result[1]

@pytest.mark.skip(reason="Failing due to build_compiled_workflow argument mismatch")
@pytest.mark.asyncio
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
async def test_predict(validator, agent_type, final_state, expected_result):
    validator.parameters.agent_type = agent_type

    with patch.object(validator, 'workflow') as mock_workflow, \
         patch.object(validator, 'get_token_usage') as mock_get_token_usage, \
         patch('openai_cost_calculator.openai_cost_calculator.calculate_cost') as mock_calculate_cost:

        async def mock_ainvoke(*args, **kwargs):
            return final_state
        
        mock_workflow.ainvoke = mock_ainvoke
        mock_get_token_usage.return_value = {
            'successful_requests': 1,
            'total_tokens': 100,
            'prompt_tokens': 50,
            'completion_tokens': 50
        }
        mock_calculate_cost.return_value = {'total_cost': 0.001}

        model_input = validator.Input(text=SAMPLE_TRANSCRIPT, metadata=SAMPLE_METADATA)
        context = {}
        result = await validator.predict(context, model_input)
        
        assert isinstance(result, list)
        assert len(result) == 1
        assert result[0].value == expected_result[0]
        assert result[0].explanation == expected_result[1]

# Integration Tests
@pytest.mark.integration
@pytest.mark.asyncio
async def test_validation_with_real_model(validator):
    input_data = validator.Input(
        text=SAMPLE_TRANSCRIPT,
        metadata=SAMPLE_METADATA
    )
    
    context = {}
    results = await validator.predict(context, model_input=input_data)
    
    assert isinstance(results, list)
    assert len(results) > 0
    result = results[0]
    
    assert result.value in ["Yes", "No", "Unclear"]
    assert isinstance(result.explanation, str)

@pytest.mark.integration
@pytest.mark.asyncio
async def test_validation_with_mismatched_data(validator):
    input_data = validator.Input(
        text="I graduated from Harvard with a Master's in Biology.",
        metadata=SAMPLE_METADATA
    )
    
    context = {}
    results = await validator.predict(context, model_input=input_data)
    
    assert isinstance(results, list)
    assert len(results) > 0
    result = results[0]
    
    assert result.value in ["No", "Unclear"]
    assert isinstance(result.explanation, str)