#!/usr/bin/env python3
"""
Test the harmonized confidence calculation that uses string-based parsing
to find the classification, then finds the corresponding token position,
and calculates confidence from that token's logprobs.

Tests both parse_from_start=True and parse_from_start=False scenarios.
"""

import pytest
import asyncio
from unittest.mock import AsyncMock, patch
from plexus.scores.nodes.Classifier import Classifier
from langchain_core.messages import AIMessage

pytest.asyncio_fixture_scope = "function"
pytest_plugins = ('pytest_asyncio',)


def create_mock_logprobs_response(tokens_and_alternatives):
    """
    Create a mock logprobs response structure.

    Args:
        tokens_and_alternatives: List of tuples (actual_token, [(alt_token, logprob), ...])
    """
    content = []

    for actual_token, alternatives in tokens_and_alternatives:
        # Build top_logprobs - first entry should be the actual token chosen
        top_logprobs = []

        # Add the actual token as first entry (highest probability)
        actual_logprob = alternatives[0][1] if alternatives else -0.0001
        top_logprobs.append({
            'token': actual_token,
            'logprob': actual_logprob
        })

        # Add alternative tokens
        for alt_token, logprob in alternatives[1:] if len(alternatives) > 1 else []:
            top_logprobs.append({
                'token': alt_token,
                'logprob': logprob
            })

        # Build token data
        token_data = {
            'token': actual_token,
            'logprob': actual_logprob,
            'top_logprobs': top_logprobs
        }

        content.append(token_data)

    return {'content': content}


@pytest.mark.asyncio
async def test_confidence_parse_from_start_true():
    """Test confidence calculation with parse_from_start=True (first occurrence)."""

    # Mock response: "yes, but actually no"
    # String parser with parse_from_start=True should find "yes" first
    # Confidence should be calculated from token 0 ("yes")

    mock_logprobs = create_mock_logprobs_response([
        ("yes", [
            ("yes", -0.1000),    # 90.48% - actual token chosen
            ("no", -2.3000),     # 10.03% - alternative
            ("maybe", -4.6000)   # 1.00% - another alternative
        ]),
        (",", [
            (",", -0.0001),
            (".", -3.0000)
        ]),
        (" but", [
            (" but", -0.0001),
            (" and", -2.0000)
        ]),
        (" actually", [
            (" actually", -0.0001),
            (" really", -1.5000)
        ]),
        (" no", [
            (" no", -0.0001),
            (" yes", -3.0000)
        ])
    ])

    mock_model = AsyncMock()
    mock_response = AIMessage(content="yes, but actually no")
    mock_response.response_metadata = {'logprobs': mock_logprobs}
    mock_model.ainvoke = AsyncMock(return_value=mock_response)

    with patch('plexus.LangChainUser.LangChainUser._initialize_model', return_value=mock_model):
        config = {
            "name": "test_confidence_parse_start",
            "valid_classes": ["yes", "no"],
            "system_message": "You are a classifier.",
            "user_message": "Classify this: {text}",
            "model_provider": "ChatOpenAI",
            "model_name": "gpt-4o-mini",
            "temperature": 0.0,
            "confidence": True,
            "parse_from_start": True  # Should find FIRST "yes"
        }

        classifier = Classifier(**config)
        classifier.model = mock_model

        # Create state
        state = classifier.GraphState(
            text="Test input",
            metadata={},
            results={},
            retry_count=0,
            is_not_empty=True,
            value=None,
            reasoning=None,
            classification=None,
            chat_history=[],
            completion=None,
            confidence=None,
            raw_logprobs=None
        )

        # Run through the nodes
        llm_prompt_node = classifier.get_llm_prompt_node()
        llm_call_node = classifier.get_llm_call_node()
        parse_node = classifier.get_parser_node()
        confidence_node = classifier.get_confidence_node()

        # Execute pipeline
        state = await llm_prompt_node(state)
        state = await llm_call_node(state)
        state = await parse_node(state)

        # Verify parsing found "yes" (first occurrence)
        assert state.classification == "yes"
        assert state.completion == "yes, but actually no"

        # Calculate confidence
        final_state = await confidence_node(state)

        # Should use token 0 ("yes") logprobs
        # Confidence = P("yes") = exp(-0.1000) = ~0.9048
        expected_confidence = 0.9048  # approximately

        if isinstance(final_state, dict):
            confidence = final_state.get('confidence')
        else:
            confidence = final_state.confidence

        assert confidence is not None
        assert abs(confidence - expected_confidence) < 0.01  # Allow small floating point differences


@pytest.mark.asyncio
async def test_confidence_parse_from_start_false():
    """Test confidence calculation with parse_from_start=False (last occurrence)."""

    # Mock response: "yes, but actually no"
    # String parser with parse_from_start=False should find "no" last
    # Confidence should be calculated from token 4 (" no")

    mock_logprobs = create_mock_logprobs_response([
        ("yes", [
            ("yes", -0.1000),    # 90.48%
            ("no", -2.3000),     # 10.03%
            ("maybe", -4.6000)   # 1.00%
        ]),
        (",", [
            (",", -0.0001),
            (".", -3.0000)
        ]),
        (" but", [
            (" but", -0.0001),
            (" and", -2.0000)
        ]),
        (" actually", [
            (" actually", -0.0001),
            (" really", -1.5000)
        ]),
        (" no", [
            (" no", -0.5000),    # 60.65% - actual token chosen
            (" yes", -1.2000),   # 30.12% - alternative
            (" maybe", -3.0000)  # 4.98% - another alternative
        ])
    ])

    mock_model = AsyncMock()
    mock_response = AIMessage(content="yes, but actually no")
    mock_response.response_metadata = {'logprobs': mock_logprobs}
    mock_model.ainvoke = AsyncMock(return_value=mock_response)

    with patch('plexus.LangChainUser.LangChainUser._initialize_model', return_value=mock_model):
        config = {
            "name": "test_confidence_parse_end",
            "valid_classes": ["yes", "no"],
            "system_message": "You are a classifier.",
            "user_message": "Classify this: {text}",
            "model_provider": "ChatOpenAI",
            "model_name": "gpt-4o-mini",
            "temperature": 0.0,
            "confidence": True,
            "parse_from_start": False  # Should find LAST "no"
        }

        classifier = Classifier(**config)
        classifier.model = mock_model

        # Create state
        state = classifier.GraphState(
            text="Test input",
            metadata={},
            results={},
            retry_count=0,
            is_not_empty=True,
            value=None,
            reasoning=None,
            classification=None,
            chat_history=[],
            completion=None,
            confidence=None,
            raw_logprobs=None
        )

        # Run through the nodes
        llm_prompt_node = classifier.get_llm_prompt_node()
        llm_call_node = classifier.get_llm_call_node()
        parse_node = classifier.get_parser_node()
        confidence_node = classifier.get_confidence_node()

        # Execute pipeline
        state = await llm_prompt_node(state)
        state = await llm_call_node(state)
        state = await parse_node(state)

        # Verify parsing found "no" (last occurrence)
        assert state.classification == "no"
        assert state.completion == "yes, but actually no"

        # Calculate confidence
        final_state = await confidence_node(state)

        # Should use token 4 (" no") logprobs
        # Confidence = P("no") = exp(-0.5000) = ~0.6065
        expected_confidence = 0.6065  # approximately

        if isinstance(final_state, dict):
            confidence = final_state.get('confidence')
        else:
            confidence = final_state.confidence

        assert confidence is not None
        assert abs(confidence - expected_confidence) < 0.01  # Allow small floating point differences


@pytest.mark.asyncio
async def test_confidence_single_token_response():
    """Test confidence calculation for single-token responses."""

    # Mock response: just "yes"
    # Should work for both parse_from_start=True and False

    mock_logprobs = create_mock_logprobs_response([
        ("yes", [
            ("yes", -0.2000),    # 81.87% - actual token chosen
            ("no", -1.5000),     # 22.31% - alternative
            ("maybe", -3.0000)   # 4.98% - another alternative
        ])
    ])

    mock_model = AsyncMock()
    mock_response = AIMessage(content="yes")
    mock_response.response_metadata = {'logprobs': mock_logprobs}
    mock_model.ainvoke = AsyncMock(return_value=mock_response)

    with patch('plexus.LangChainUser.LangChainUser._initialize_model', return_value=mock_model):
        config = {
            "name": "test_confidence_single_token",
            "valid_classes": ["yes", "no"],
            "system_message": "You are a classifier.",
            "user_message": "Classify this: {text}",
            "model_provider": "ChatOpenAI",
            "model_name": "gpt-4o-mini",
            "temperature": 0.0,
            "confidence": True,
            "parse_from_start": True  # Doesn't matter for single token
        }

        classifier = Classifier(**config)
        classifier.model = mock_model

        # Create state
        state = classifier.GraphState(
            text="Test input",
            metadata={},
            results={},
            retry_count=0,
            is_not_empty=True,
            value=None,
            reasoning=None,
            classification=None,
            chat_history=[],
            completion=None,
            confidence=None,
            raw_logprobs=None
        )

        # Run through the nodes
        llm_prompt_node = classifier.get_llm_prompt_node()
        llm_call_node = classifier.get_llm_call_node()
        parse_node = classifier.get_parser_node()
        confidence_node = classifier.get_confidence_node()

        # Execute pipeline
        state = await llm_prompt_node(state)
        state = await llm_call_node(state)
        state = await parse_node(state)

        # Verify parsing
        assert state.classification == "yes"
        assert state.completion == "yes"

        # Calculate confidence
        final_state = await confidence_node(state)

        # Should use token 0 ("yes") logprobs
        # Confidence = P("yes") = exp(-0.2000) = ~0.8187
        expected_confidence = 0.8187  # approximately

        if isinstance(final_state, dict):
            confidence = final_state.get('confidence')
        else:
            confidence = final_state.confidence

        assert confidence is not None
        assert abs(confidence - expected_confidence) < 0.01  # Allow small floating point differences


@pytest.mark.asyncio
async def test_confidence_no_matching_tokens():
    """Test confidence calculation when no token alternatives match the classification."""

    # Mock response where string parsing finds "positive" but no tokens match it
    mock_logprobs = create_mock_logprobs_response([
        ("The", [
            ("The", -0.0001),
            ("This", -2.0000)
        ]),
        (" answer", [
            (" answer", -0.0001),
            (" result", -1.5000)
        ]),
        (" is", [
            (" is", -0.0001),
            (" was", -2.0000)
        ]),
        (" positive", [
            (" positive", -0.1000),   # This is the actual token
            (" negative", -2.0000),   # But suppose "positive" isn't in valid_classes
            (" neutral", -3.0000)
        ])
    ])

    mock_model = AsyncMock()
    mock_response = AIMessage(content="The answer is positive")
    mock_response.response_metadata = {'logprobs': mock_logprobs}
    mock_model.ainvoke = AsyncMock(return_value=mock_response)

    with patch('plexus.LangChainUser.LangChainUser._initialize_model', return_value=mock_model):
        config = {
            "name": "test_confidence_no_match",
            "valid_classes": ["good", "bad"],  # Note: "positive" not in valid classes
            "system_message": "You are a classifier.",
            "user_message": "Classify this: {text}",
            "model_provider": "ChatOpenAI",
            "model_name": "gpt-4o-mini",
            "temperature": 0.0,
            "confidence": True,
            "parse_from_start": False
        }

        classifier = Classifier(**config)
        classifier.model = mock_model

        # Create state
        state = classifier.GraphState(
            text="Test input",
            metadata={},
            results={},
            retry_count=0,
            is_not_empty=True,
            value=None,
            reasoning=None,
            classification=None,
            chat_history=[],
            completion=None,
            confidence=None,
            raw_logprobs=None
        )

        # Run through the nodes
        llm_prompt_node = classifier.get_llm_prompt_node()
        llm_call_node = classifier.get_llm_call_node()
        parse_node = classifier.get_parser_node()
        confidence_node = classifier.get_confidence_node()

        # Execute pipeline
        state = await llm_prompt_node(state)
        state = await llm_call_node(state)
        state = await parse_node(state)

        # String parsing should fail to find valid classification
        assert state.classification is None

        # Confidence calculation should handle this gracefully
        final_state = await confidence_node(state)

        if isinstance(final_state, dict):
            confidence = final_state.get('confidence')
        else:
            confidence = final_state.confidence

        # Should be None because no classification was found
        assert confidence is None


@pytest.mark.asyncio
async def test_confidence_multiple_matches_same_class():
    """Test confidence calculation when multiple tokens map to the same classification."""

    # Mock response: "yes indeed yes"
    # Both "yes" tokens should contribute to confidence

    mock_logprobs = create_mock_logprobs_response([
        ("yes", [
            ("yes", -0.3000),    # 74.08% - first "yes"
            ("no", -1.2000),     # 30.12%
            ("maybe", -2.5000)   # 8.21%
        ]),
        (" indeed", [
            (" indeed", -0.0001),
            (" certainly", -2.0000)
        ]),
        (" yes", [
            (" yes", -0.1000),   # 90.48% - second "yes"
            (" no", -2.0000),    # 13.53%
            (" absolutely", -3.0000)  # 4.98%
        ])
    ])

    mock_model = AsyncMock()
    mock_response = AIMessage(content="yes indeed yes")
    mock_response.response_metadata = {'logprobs': mock_logprobs}
    mock_model.ainvoke = AsyncMock(return_value=mock_response)

    with patch('plexus.LangChainUser.LangChainUser._initialize_model', return_value=mock_model):
        # Test parse_from_start=True (should use first "yes")
        config = {
            "name": "test_confidence_multiple_matches",
            "valid_classes": ["yes", "no"],
            "system_message": "You are a classifier.",
            "user_message": "Classify this: {text}",
            "model_provider": "ChatOpenAI",
            "model_name": "gpt-4o-mini",
            "temperature": 0.0,
            "confidence": True,
            "parse_from_start": True  # Should use FIRST "yes" at position 0
        }

        classifier = Classifier(**config)
        classifier.model = mock_model

        # Create state
        state = classifier.GraphState(
            text="Test input",
            metadata={},
            results={},
            retry_count=0,
            is_not_empty=True,
            value=None,
            reasoning=None,
            classification=None,
            chat_history=[],
            completion=None,
            confidence=None,
            raw_logprobs=None
        )

        # Run through the nodes
        llm_prompt_node = classifier.get_llm_prompt_node()
        llm_call_node = classifier.get_llm_call_node()
        parse_node = classifier.get_parser_node()
        confidence_node = classifier.get_confidence_node()

        # Execute pipeline
        state = await llm_prompt_node(state)
        state = await llm_call_node(state)
        state = await parse_node(state)

        # Verify parsing found "yes"
        assert state.classification == "yes"

        # Calculate confidence - should use token 0
        final_state = await confidence_node(state)

        # Should use first "yes" token (position 0)
        # Confidence = P("yes") at position 0 = exp(-0.3000) = ~0.7408
        expected_confidence = 0.7408  # approximately

        if isinstance(final_state, dict):
            confidence = final_state.get('confidence')
        else:
            confidence = final_state.confidence

        assert confidence is not None
        assert abs(confidence - expected_confidence) < 0.01


if __name__ == "__main__":
    # Run the tests
    import sys
    import subprocess

    # Run with pytest
    result = subprocess.run([
        sys.executable, "-m", "pytest",
        __file__,
        "-v",
        "--tb=short"
    ], capture_output=True, text=True)

    print(result.stdout)
    if result.stderr:
        print("STDERR:", result.stderr)

    sys.exit(result.returncode)