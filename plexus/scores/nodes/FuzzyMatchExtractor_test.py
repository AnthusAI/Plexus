import pytest
from pydantic import ValidationError
from typing import Any # Added Any for MockGraphState typing clarity
from plexus.scores.nodes.FuzzyMatchExtractor import FuzzyMatchExtractor
from plexus.scores.shared.fuzzy_matching import FuzzyTarget, FuzzyTargetGroup
from plexus.scores.nodes.BaseNode import BaseNode # For GraphState inheritance
import unittest.mock as mock
import os

# Set environment variables for Azure OpenAI
os.environ["AZURE_OPENAI_API_KEY"] = "test_api_key"
os.environ["AZURE_OPENAI_ENDPOINT"] = "https://test-openai.openai.azure.com/"
os.environ["OPENAI_API_VERSION"] = "2023-03-15-preview"
os.environ["AZURE_OPENAI_DEPLOYMENT"] = "gpt-35-turbo"

# Mock OpenAI API to prevent credential errors
mock.patch('openai.OpenAI').start()
mock.patch('openai.AzureOpenAI').start()
mock.patch('langchain_community.chat_models.azure_openai.AzureChatOpenAI.__init__', return_value=None).start()

# Define a compatible GraphState for testing if not directly importable/usable
# Or ideally, import the actual GraphState if FuzzyMatchExtractor defines it
class MockGraphState(BaseNode.GraphState):
    text: str = ""
    match_found: bool = False
    matches: list = []

# --- Pydantic Model Tests ---

def test_fuzzy_target_creation():
    target = FuzzyTarget(target="test", threshold=80)
    assert target.target == "test"
    assert target.threshold == 80
    assert target.scorer == 'ratio' # Default
    assert target.preprocess == False # Default

def test_fuzzy_target_validation():
    with pytest.raises(ValidationError):
        FuzzyTarget(target="test", threshold=101) # Threshold > 100
    with pytest.raises(ValidationError):
        FuzzyTarget(target="test", threshold=-1) # Threshold < 0
    with pytest.raises(ValidationError):
        FuzzyTarget(target="test", threshold=80, scorer="invalid_scorer")

def test_fuzzy_target_group_creation():
    group = FuzzyTargetGroup(
        operator='or',
        items=[FuzzyTarget(target="t1", threshold=70)]
    )
    assert group.operator == 'or'
    assert len(group.items) == 1

def test_fuzzy_target_group_empty_items():
    with pytest.raises(ValidationError):
        FuzzyTargetGroup(operator='and', items=[])

def test_nested_group_creation():
    nested_group = FuzzyTargetGroup(
        operator='and',
        items=[
            FuzzyTarget(target="t1", threshold=90),
            FuzzyTargetGroup(
                operator='or',
                items=[
                    FuzzyTarget(target="t2", threshold=80),
                    FuzzyTarget(target="t3", threshold=70)
                ]
            )
        ]
    )
    assert nested_group.operator == 'and'
    assert len(nested_group.items) == 2
    assert isinstance(nested_group.items[1], FuzzyTargetGroup)

# --- Node Initialization Tests ---

def test_node_initialization_simple_target():
    params = {
        "name": "test_node",
        "targets": {
            "target": "find me",
            "threshold": 75
        }
    }
    node = FuzzyMatchExtractor(**params)
    assert node.node_name == "test_node"
    assert isinstance(node.parameters.targets, FuzzyTarget)
    assert node.parameters.targets.target == "find me"

def test_node_initialization_group():
    params = {
        "name": "test_group_node",
        "targets": {
            "operator": "or",
            "items": [
                {"target": "find me", "threshold": 75},
                {"target": "or me", "threshold": 80, "scorer": "partial_ratio"}
            ]
        }
    }
    node = FuzzyMatchExtractor(**params)
    assert node.node_name == "test_group_node"
    assert isinstance(node.parameters.targets, FuzzyTargetGroup)
    assert node.parameters.targets.operator == "or"
    assert len(node.parameters.targets.items) == 2
    assert node.parameters.targets.items[1].scorer == "partial_ratio"


# --- Basic Matching Logic Tests (will fail initially) ---

@pytest.mark.asyncio
async def test_simple_or_match_first():
    params = {
        "name": "simple_or_test",
        "targets": {
            "operator": "or",
            "items": [
                {"target": "hello world", "threshold": 90, "scorer": "partial_ratio"},
                {"target": "another thing", "threshold": 90, "scorer": "ratio"}
            ]
        }
    }
    node = FuzzyMatchExtractor(**params)
    initial_state = MockGraphState(text="This text contains hello world exactly.")

    # Get the node function (assuming it exists)
    matcher_node_func = node.get_matcher_node()
    final_state = await matcher_node_func(initial_state)

    assert final_state.match_found is True
    assert len(final_state.matches) == 1
    assert final_state.matches[0]['target'] == "hello world"
    assert final_state.matches[0]['score'] >= 90
    assert final_state.matches[0]['matched_text'] == "hello world" # Or similar depending on scorer/preprocessing

@pytest.mark.asyncio
async def test_simple_or_no_match():
    params = {
        "name": "simple_or_no_match_test",
        "targets": {
            "operator": "or",
            "items": [
                {"target": "target one", "threshold": 95, "scorer": "ratio"},
                {"target": "target two", "threshold": 95, "scorer": "ratio"}
            ]
        }
    }
    node = FuzzyMatchExtractor(**params)
    initial_state = MockGraphState(text="This text contains neither.")

    matcher_node_func = node.get_matcher_node()
    final_state = await matcher_node_func(initial_state)

    assert final_state.match_found is False
    assert len(final_state.matches) == 0

# --- Tests for Specific Scorers ---

@pytest.mark.asyncio
async def test_ratio_scorer_exact_match():
    params = {
        "name": "ratio_exact_test",
        "targets": {
            "target": "exact match",
            "threshold": 100,
            "scorer": "ratio"
        }
    }
    node = FuzzyMatchExtractor(**params)
    initial_state = MockGraphState(text="exact match")
    final_state = await node.get_matcher_node()(initial_state)
    assert final_state.match_found is True
    assert len(final_state.matches) == 1
    assert final_state.matches[0]['target'] == "exact match"
    assert final_state.matches[0]['score'] == 100
    # ratio compares full strings, so matched_text is the input text
    assert final_state.matches[0]['matched_text'] == "exact match"
    assert final_state.matches[0]['matched_indices'] is None # No alignment for ratio

@pytest.mark.asyncio
async def test_ratio_scorer_close_match():
    params = {
        "name": "ratio_close_test",
        "targets": {
            "target": "testing ratio", # Target
            "threshold": 90,
            "scorer": "ratio"
        }
    }
    node = FuzzyMatchExtractor(**params)
    initial_state = MockGraphState(text="testing rations") # Input (1 char diff)
    final_state = await node.get_matcher_node()(initial_state)
    assert final_state.match_found is True
    assert len(final_state.matches) == 1
    assert final_state.matches[0]['target'] == "testing ratio"
    assert final_state.matches[0]['score'] > 90 # Should be high, e.g. ~92.3
    assert final_state.matches[0]['matched_text'] == "testing rations" # Full text
    assert final_state.matches[0]['matched_indices'] is None

# test_partial_ratio_scorer (covered by test_simple_or_match_first, but explicit is good)
@pytest.mark.asyncio
async def test_partial_ratio_scorer():
    params = {
        "name": "partial_ratio_test",
        "targets": {
            "target": "partial match",
            "threshold": 100,
            "scorer": "partial_ratio"
        }
    }
    node = FuzzyMatchExtractor(**params)
    initial_state = MockGraphState(text="This text contains a partial match.")
    final_state = await node.get_matcher_node()(initial_state)
    assert final_state.match_found is True
    assert len(final_state.matches) == 1
    assert final_state.matches[0]['target'] == "partial match"
    assert final_state.matches[0]['score'] == 100
    assert final_state.matches[0]['matched_text'] == "partial match" # Extracted substring
    assert isinstance(final_state.matches[0]['matched_indices'], tuple) # Should have indices
    assert final_state.matches[0]['matched_indices'][0] == 21 # Approx start index

@pytest.mark.asyncio
async def test_token_sort_ratio_scorer():
    params = {
        "name": "token_sort_test",
        "targets": {
            "target": "world hello", # Out of order
            "threshold": 100,
            "scorer": "token_sort_ratio"
        }
    }
    node = FuzzyMatchExtractor(**params)
    # Use exact text but out of order for token sort
    initial_state = MockGraphState(text="hello world")
    final_state = await node.get_matcher_node()(initial_state)
    assert final_state.match_found is True
    assert len(final_state.matches) == 1
    assert final_state.matches[0]['target'] == "world hello"
    assert final_state.matches[0]['score'] == 100
    # No alignment for token_sort_ratio, expect full text
    assert final_state.matches[0]['matched_text'] == "hello world"
    assert final_state.matches[0]['matched_indices'] is None # No indices expected

@pytest.mark.asyncio
async def test_token_set_ratio_scorer():
    params = {
        "name": "token_set_test",
        "targets": {
            "target": "fuzzy fuzzy match", # Duplicate target words
            "threshold": 100,
            "scorer": "token_set_ratio"
        }
    }
    node = FuzzyMatchExtractor(**params)
    initial_state = MockGraphState(text="a fuzzy match test case")
    final_state = await node.get_matcher_node()(initial_state)
    assert final_state.match_found is True
    assert len(final_state.matches) == 1
    assert final_state.matches[0]['target'] == "fuzzy fuzzy match"
    assert final_state.matches[0]['score'] == 100
    # No alignment for token_set_ratio, expect full text
    assert final_state.matches[0]['matched_text'] == "a fuzzy match test case"
    assert final_state.matches[0]['matched_indices'] is None # No indices expected

@pytest.mark.asyncio
async def test_WRatio_scorer():
    params = {
        "name": "WRatio_test",
        "targets": {
            "target": "complex matching",
            "threshold": 90,
            "scorer": "WRatio" # Uses partial_ratio logic internally for substrings
        }
    }
    node = FuzzyMatchExtractor(**params)
    initial_state = MockGraphState(text="This is a test of complex matching capability")
    final_state = await node.get_matcher_node()(initial_state)
    assert final_state.match_found is True
    assert len(final_state.matches) == 1
    assert final_state.matches[0]['target'] == "complex matching"
    # WRatio score can vary, but should be high for partial matches
    assert final_state.matches[0]['score'] >= 90
    # No alignment function for WRatio, returns full text
    assert final_state.matches[0]['matched_text'] == "This is a test of complex matching capability"
    assert final_state.matches[0]['matched_indices'] is None

@pytest.mark.asyncio
async def test_QRatio_scorer():
    params = {
        "name": "QRatio_test",
        "targets": {
            "target": "test qratio!",
            "threshold": 95, # QRatio is strict, use exact match (including punctuation)
            "scorer": "QRatio"
        }
    }
    node = FuzzyMatchExtractor(**params)
    initial_state = MockGraphState(text="test qratio!")
    final_state = await node.get_matcher_node()(initial_state)
    assert final_state.match_found is True
    assert len(final_state.matches) == 1
    assert final_state.matches[0]['target'] == "test qratio!"
    assert final_state.matches[0]['score'] >= 95 # Should be 100 now
    # No alignment function for QRatio, returns full text
    assert final_state.matches[0]['matched_text'] == "test qratio!"
    assert final_state.matches[0]['matched_indices'] is None

@pytest.mark.asyncio
async def test_preprocess_option():
    params = {
        "name": "preprocess_test",
        "targets": {
            "target": "PreProcess Test", # Mixed case, should be lowercased
            "threshold": 100,
            "scorer": "ratio",
            "preprocess": True # Enable preprocessing
        }
    }
    node = FuzzyMatchExtractor(**params)
    # Input text has different casing and punctuation
    initial_state = MockGraphState(text="Preprocess test.")
    final_state = await node.get_matcher_node()(initial_state)
    assert final_state.match_found is True
    assert len(final_state.matches) == 1
    assert final_state.matches[0]['target'] == "PreProcess Test"
    assert final_state.matches[0]['score'] == 100 # Perfect match after preprocessing
    assert final_state.matches[0]['matched_text'] == "Preprocess test." # Still returns original text
    assert final_state.matches[0]['matched_indices'] is None 