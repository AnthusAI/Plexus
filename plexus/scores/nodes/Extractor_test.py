import pytest
from unittest.mock import Mock, patch
from plexus.scores.nodes.Extractor import Extractor
from plexus.scores.nodes.BaseNode import BaseNode
from langchain_core.prompts import ChatPromptTemplate
from langgraph.graph import StateGraph
import nltk

# Patch _initialize_model to bypass real API calls and credentials for tests
@pytest.fixture(autouse=True)
def patch_openai_credentials(monkeypatch):
    from plexus.scores.nodes.Extractor import Extractor
    monkeypatch.setattr(Extractor, "_initialize_model", lambda self: (lambda x: 'dummy output'))

@pytest.fixture
def basic_parameters():
    return {
        "fuzzy_match_score_cutoff": 50,
        "use_exact_matching": False,
        "trust_model_output": False,
        "prompt_templates": ["Extract the relevant quote: {text}"],
        "model_name": "gpt-4o-mini-2024-07-18"
    }

@pytest.fixture
def extractor(basic_parameters):
    return Extractor(**basic_parameters)

@pytest.fixture
def sample_state():
    return Extractor.GraphState(
        text="This is a sample text with some content. We need to extract specific parts from it.",
        extracted_text=None
    )

def test_extractor_initialization(basic_parameters):
    extractor = Extractor(**basic_parameters)
    assert extractor.parameters.fuzzy_match_score_cutoff == 50
    assert not extractor.parameters.use_exact_matching
    assert not extractor.parameters.trust_model_output

def test_extraction_output_parser_initialization():
    parser = Extractor.ExtractionOutputParser(
        FUZZY_MATCH_SCORE_CUTOFF=50,
        text="Sample text",
        use_exact_matching=False,
        trust_model_output=False
    )
    assert parser.FUZZY_MATCH_SCORE_CUTOFF == 50
    assert parser._type == "custom_output_parser"

def test_extraction_output_parser_exact_matching():
    text = "This is a test sentence. Another sentence here."
    parser = Extractor.ExtractionOutputParser(
        FUZZY_MATCH_SCORE_CUTOFF=50,
        text=text,
        use_exact_matching=True,
        trust_model_output=False
    )
    
    # Test exact match
    result = parser.parse("This is a test sentence")
    assert result["extracted_text"] == "This is a test sentence"

def test_extraction_output_parser_sliding_window():
    text = "This is a test sentence. Another sentence here."
    parser = Extractor.ExtractionOutputParser(
        FUZZY_MATCH_SCORE_CUTOFF=50,
        text=text,
        use_exact_matching=False,
        trust_model_output=False
    )
    
    # Test sliding window match
    result = parser.parse("test sentence")
    assert "test sentence" in result["extracted_text"]

def test_extraction_output_parser_trust_model_output():
    parser = Extractor.ExtractionOutputParser(
        FUZZY_MATCH_SCORE_CUTOFF=50,
        text="Sample text",
        use_exact_matching=False,
        trust_model_output=True
    )
    
    model_output = "This is the model's output"
    result = parser.parse(model_output)
    assert result["extracted_text"] == model_output

def test_extraction_output_parser_no_clear_example():
    parser = Extractor.ExtractionOutputParser(
        FUZZY_MATCH_SCORE_CUTOFF=50,
        text="Sample text",
        use_exact_matching=False,
        trust_model_output=False
    )
    
    result = parser.parse("No clear example found")
    assert "No clear example" in result["extracted_text"]

def test_get_extractor_node(extractor, sample_state):
    node_func = extractor.get_extractor_node()
    assert callable(node_func)

def test_add_core_nodes(extractor):
    workflow = StateGraph(
        state_schema=Extractor.GraphState
    )
    modified_workflow = extractor.add_core_nodes(workflow)
    assert "extractor" in modified_workflow.nodes

def test_tokenizer_initialization():
    parser = Extractor.ExtractionOutputParser(
        FUZZY_MATCH_SCORE_CUTOFF=50,
        text="Sample text",
        use_exact_matching=False,
        trust_model_output=False
    )
    
    sentences = parser.tokenize("This is a test. This is another test.")
    assert len(sentences) == 2
    assert sentences[0] == "This is a test."

def test_extraction_with_quote_prefix():
    parser = Extractor.ExtractionOutputParser(
        FUZZY_MATCH_SCORE_CUTOFF=50,
        text="Sample text with a quote",
        use_exact_matching=False,
        trust_model_output=False
    )
    
    result = parser.parse('Quote: "Sample text"')
    assert result["extracted_text"] == "Sample text"

def test_low_confidence_match():
    text = "This is a completely different text"
    parser = Extractor.ExtractionOutputParser(
        FUZZY_MATCH_SCORE_CUTOFF=90,  # High threshold
        text=text,
        use_exact_matching=True,
        trust_model_output=False
    )
    
    result = parser.parse("This is somewhat similar")
    assert result["extracted_text"] == "This is somewhat similar"  # Returns original when confidence is low 

def test_end_to_end_chain_integration_with_dummy_model(basic_parameters):
    # Create an extractor instance with basic parameters
    extractor_instance = Extractor(**basic_parameters)
    
    # Override the model with a dummy model that always returns a fixed output
    dummy_model = lambda x: 'Quote: "Extract the key sentence."'
    extractor_instance.model = dummy_model
    
    # Ensure get_prompt_templates returns a valid prompt template list to avoid index errors
    extractor_instance.get_prompt_templates = lambda: basic_parameters["prompt_templates"]
    
    # Define a sample state that contains the expected sentence
    state = Extractor.GraphState(
        text="This is a test. Extract the key sentence. That is it.",
        extracted_text=None
    )
    
    # Retrieve the extractor node (which builds the chain: prompt | model | parser)
    node_func = extractor_instance.get_extractor_node()
    
    # Invoke the chain with the test state
    result = node_func(state)
    
    # Validate that the chain returns the expected extracted text
    assert "extracted_text" in result
    assert result["extracted_text"] == "Extract the key sentence." 