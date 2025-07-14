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
    load_dotenv('.env', override=True)
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