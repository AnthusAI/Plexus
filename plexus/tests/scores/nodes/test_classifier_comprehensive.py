"""
Comprehensive tests for Classifier functionality.

This test suite extends the existing Classifier tests to cover critical functionality
that represents significant risk areas. It focuses on edge cases, error handling,
and complex scenarios that aren't covered by the basic functionality tests.

Key areas tested:
- Output parser edge cases and complex parsing scenarios
- Advanced retry logic and state management
- Error handling and recovery scenarios
- Batch processing edge cases
- Integration with BaseNode functionality
- Complex message handling scenarios
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
import sys

# Mock problematic dependencies upfront
class MockModule:
    def __getattr__(self, name):
        return MockModule()
    def __call__(self, *args, **kwargs):
        return MockModule()

sys.modules['mlflow'] = MockModule()
sys.modules['pandas'] = MockModule()
sys.modules['graphviz'] = MockModule()

pytest.asyncio_fixture_scope = "function"
pytest_plugins = ('pytest_asyncio',)


class TestClassifierOutputParserEdgeCases:
    """Test edge cases in the ClassificationOutputParser"""
    
    def test_parser_complex_substring_matching(self):
        """Test parser handling of complex substring scenarios"""
        try:
            from plexus.scores.nodes.Classifier import Classifier
        except ImportError:
            pytest.skip("Classifier dependencies not available")
            
        # Create parser with overlapping valid classes
        parser = Classifier.ClassificationOutputParser(
            valid_classes=["yes", "yes indeed", "absolutely yes", "no", "no way"]
        )
        
        test_cases = [
            # Test longest match preference
            ("The answer is absolutely yes indeed", "absolutely yes"),
            ("I would say yes indeed", "yes indeed"),
            ("The response is no way", "no way"),
            ("Simply yes", "yes"),
            ("Simply no", "no"),
            
            # Test word boundary detection
            ("The word 'yessir' appears", None),  # Should not match 'yes'
            ("The answer is 'yes'", "yes"),  # Should match despite quotes
            ("I say yes!", "yes"),  # Should match despite punctuation
            
            # Test case insensitivity
            ("The answer is YES", "yes"),
            ("Absolutely YES indeed", "absolutely yes"),
            ("NO WAY would I agree", "no way"),
        ]
        
        for text, expected in test_cases:
            result = parser.parse(text)
            assert result["classification"] == expected, f"Failed for text: '{text}'"

    def test_parser_multiline_complex_scenarios(self):
        """Test parser with complex multiline responses"""
        try:
            from plexus.scores.nodes.Classifier import Classifier
        except ImportError:
            pytest.skip("Classifier dependencies not available")
            
        parser = Classifier.ClassificationOutputParser(
            valid_classes=["positive", "negative", "neutral"]
        )
        
        complex_multiline = """
        After careful consideration of all the factors involved,
        including the context, the sentiment, and the overall tone,
        I believe the most appropriate classification would be:
        
        **positive**
        
        This is because the text demonstrates clear positive sentiment
        with encouraging language and optimistic outlook.
        """
        
        result = parser.parse(complex_multiline)
        assert result["classification"] == "positive"

    def test_parser_parse_from_start_with_conflicts(self):
        """Test parse_from_start with conflicting terms"""
        try:
            from plexus.scores.nodes.Classifier import Classifier
        except ImportError:
            pytest.skip("Classifier dependencies not available")
            
        # Test parse_from_start=True
        parser_start = Classifier.ClassificationOutputParser(
            valid_classes=["positive", "negative"],
            parse_from_start=True
        )
        
        # Test parse_from_start=False (default)
        parser_end = Classifier.ClassificationOutputParser(
            valid_classes=["positive", "negative"],
            parse_from_start=False
        )
        
        conflict_text = "Initially I thought positive, but upon reflection, negative"
        
        result_start = parser_start.parse(conflict_text)
        result_end = parser_end.parse(conflict_text)
        
        assert result_start["classification"] == "positive"
        assert result_end["classification"] == "negative"

    def test_parser_normalization_edge_cases(self):
        """Test text normalization in complex scenarios"""
        try:
            from plexus.scores.nodes.Classifier import Classifier
        except ImportError:
            pytest.skip("Classifier dependencies not available")
            
        parser = Classifier.ClassificationOutputParser(
            valid_classes=["multi_word_class", "another-class", "CamelCase"]
        )
        
        test_cases = [
            # Test underscore handling
            ("The result is multi_word_class", "multi_word_class"),
            ("The result is multi word class", "multi_word_class"),
            
            # Test hyphen handling
            ("Classification: another-class", "another-class"),
            ("Classification: another class", "another-class"),
            
            # Test case sensitivity
            ("Result: camelcase", "CamelCase"),
            ("Result: CAMELCASE", "CamelCase"),
        ]
        
        for text, expected in test_cases:
            result = parser.parse(text)
            assert result["classification"] == expected, f"Failed for text: '{text}'"

    def test_parser_with_empty_valid_classes(self):
        """Test parser behavior with empty valid classes list"""
        try:
            from plexus.scores.nodes.Classifier import Classifier
        except ImportError:
            pytest.skip("Classifier dependencies not available")
            
        # Should default to ["Yes", "No"]
        parser = Classifier.ClassificationOutputParser(valid_classes=[])
        
        assert parser.valid_classes == ["Yes", "No"]
        
        result = parser.parse("The answer is yes")
        assert result["classification"] == "Yes"


class TestClassifierRetryLogicAdvanced:
    """Test advanced retry logic and state management"""
    
    @pytest.mark.asyncio
    async def test_retry_with_complex_chat_history(self):
        """Test retry logic with complex existing chat history"""
        try:
            from plexus.scores.nodes.Classifier import Classifier
            from langchain_core.messages import AIMessage, HumanMessage, SystemMessage
        except ImportError:
            pytest.skip("Classifier dependencies not available")
            
        mock_model = AsyncMock()
        responses = [
            AIMessage(content="I need to think about this..."),  # Invalid
            AIMessage(content="After consideration, yes")        # Valid
        ]
        mock_model.ainvoke = AsyncMock(side_effect=responses)
        
        with patch('plexus.LangChainUser.LangChainUser._initialize_model', return_value=mock_model):
            classifier = Classifier(
                name="test_classifier",
                valid_classes=["yes", "no"],
                system_message="You are a classifier.",
                user_message="Classify this: {text}",
                model_provider="test",
                model_name="test",
                temperature=0.0
            )
            classifier.model = mock_model
            
            # Create state with existing chat history
            existing_chat_history = [
                {
                    'type': 'human',
                    'content': 'Previous question',
                    '_type': 'HumanMessage'
                },
                {
                    'type': 'ai', 
                    'content': 'Previous response',
                    '_type': 'AIMessage'
                }
            ]
            
            state = classifier.GraphState(
                text="Test text for classification",
                metadata={},
                results={},
                retry_count=0,
                is_not_empty=True,
                value=None,
                reasoning=None,
                classification=None,
                chat_history=existing_chat_history,
                completion=None
            )
            
            # Run through first attempt and retry
            llm_prompt_node = classifier.get_llm_prompt_node()
            llm_call_node = classifier.get_llm_call_node()
            parse_node = classifier.get_parser_node()
            retry_node = classifier.get_retry_node()
            
            # First attempt
            state = await llm_prompt_node(state)
            state = await llm_call_node(state)
            state = await parse_node(state)
            
            # Should need retry
            assert state.classification is None
            
            # Execute retry
            state = await retry_node(state)
            
            # Verify chat history preserved and extended
            assert len(state.chat_history) > len(existing_chat_history)
            
            # Second attempt
            state = await llm_prompt_node(state)
            state = await llm_call_node(state)
            final_state = await parse_node(state)
            
            assert final_state.classification == "yes"

    @pytest.mark.asyncio
    async def test_retry_count_persistence_across_nodes(self):
        """Test that retry count is properly maintained across node executions"""
        try:
            from plexus.scores.nodes.Classifier import Classifier
            from langchain_core.messages import AIMessage
        except ImportError:
            pytest.skip("Classifier dependencies not available")
            
        mock_model = AsyncMock()
        # Return invalid responses to force multiple retries
        responses = [
            AIMessage(content="unclear response 1"),
            AIMessage(content="unclear response 2"),
            AIMessage(content="unclear response 3"),
            AIMessage(content="yes")  # Finally valid
        ]
        mock_model.ainvoke = AsyncMock(side_effect=responses)
        
        with patch('plexus.LangChainUser.LangChainUser._initialize_model', return_value=mock_model):
            classifier = Classifier(
                name="test_classifier",
                valid_classes=["yes", "no"],
                system_message="You are a classifier.",
                user_message="Classify this: {text}",
                model_provider="test",
                model_name="test",
                temperature=0.0,
                maximum_retry_count=5
            )
            classifier.model = mock_model
            
            state = classifier.GraphState(
                text="Test text",
                metadata={},
                results={},
                retry_count=0,
                is_not_empty=True,
                value=None,
                reasoning=None,
                classification=None,
                chat_history=[],
                completion=None
            )
            
            # Simulate multiple retry cycles
            for expected_retry_count in range(4):  # 0, 1, 2, 3
                # Execute LLM nodes
                state = await classifier.get_llm_prompt_node()(state)
                state = await classifier.get_llm_call_node()(state)
                state = await classifier.get_parser_node()(state)
                
                if state.classification is None:
                    # Execute retry
                    state = await classifier.get_retry_node()(state)
                    assert state.retry_count == expected_retry_count + 1
                else:
                    # Successfully classified
                    assert state.classification == "yes"
                    break

    @pytest.mark.asyncio 
    async def test_should_retry_decision_logic(self):
        """Test the should_retry decision logic with various state conditions"""
        try:
            from plexus.scores.nodes.Classifier import Classifier
        except ImportError:
            pytest.skip("Classifier dependencies not available")
            
        classifier = Classifier(
            name="test_classifier",
            valid_classes=["yes", "no"],
            system_message="Test",
            user_message="Test {text}",
            model_provider="test",
            model_name="test",
            maximum_retry_count=3
        )
        
        # Test case 1: Valid classification - should end
        state_with_classification = classifier.GraphState(
            text="test",
            classification="yes",
            retry_count=1
        )
        result = classifier.should_retry(state_with_classification)
        assert result == "end"
        
        # Test case 2: Max retries reached - should go to max_retries
        state_max_retries = classifier.GraphState(
            text="test",
            classification=None,
            retry_count=3
        )
        result = classifier.should_retry(state_max_retries)
        assert result == "max_retries"
        
        # Test case 3: No classification, retries available - should retry
        state_needs_retry = classifier.GraphState(
            text="test",
            classification=None,
            retry_count=1
        )
        result = classifier.should_retry(state_needs_retry)
        assert result == "retry"


class TestClassifierErrorHandling:
    """Test error handling and recovery scenarios"""
    
    @pytest.mark.asyncio
    async def test_llm_call_with_missing_messages(self):
        """Test LLM call error handling when messages are missing"""
        try:
            from plexus.scores.nodes.Classifier import Classifier
        except ImportError:
            pytest.skip("Classifier dependencies not available")
            
        mock_model = AsyncMock()
        
        with patch('plexus.LangChainUser.LangChainUser._initialize_model', return_value=mock_model):
            classifier = Classifier(
                name="test_classifier",
                valid_classes=["yes", "no"],
                system_message="Test",
                user_message="Test {text}",
                model_provider="test",
                model_name="test"
            )
            classifier.model = mock_model
            
            # Create state without messages
            state_no_messages = classifier.GraphState(
                text="test",
                messages=[],  # Empty messages
                metadata={},
                retry_count=0
            )
            
            llm_call_node = classifier.get_llm_call_node()
            
            # Should handle missing messages gracefully
            with pytest.raises(ValueError, match="No messages found in state"):
                await llm_call_node(state_no_messages)

    @pytest.mark.asyncio
    async def test_parser_with_malformed_completion(self):
        """Test parser handling of malformed or unexpected completions"""
        try:
            from plexus.scores.nodes.Classifier import Classifier
        except ImportError:
            pytest.skip("Classifier dependencies not available")
            
        classifier = Classifier(
            name="test_classifier",
            valid_classes=["positive", "negative"],
            system_message="Test",
            user_message="Test {text}",
            model_provider="test",
            model_name="test"
        )
        
        parse_node = classifier.get_parser_node()
        
        malformed_responses = [
            "",  # Empty response
            "   ",  # Whitespace only
            "This response contains no valid classifications at all",
            "positiveeeee",  # Close but not exact
            "The classification is: unknown_class",  # Invalid class
            "\n\n\n",  # Newlines only
            "🤖 AI response with emojis but no classification 🤖",
        ]
        
        for completion in malformed_responses:
            state = classifier.GraphState(
                text="test",
                completion=completion,
                metadata={},
                retry_count=0
            )
            
            result = await parse_node(state)
            
            # All malformed responses should result in None classification
            assert result.classification is None

    @pytest.mark.asyncio
    async def test_max_retries_handling_with_state_preservation(self):
        """Test that max retries handler preserves important state information"""
        try:
            from plexus.scores.nodes.Classifier import Classifier
        except ImportError:
            pytest.skip("Classifier dependencies not available")
            
        classifier = Classifier(
            name="test_classifier",
            valid_classes=["yes", "no"],
            system_message="Test",
            user_message="Test {text}",
            model_provider="test",
            model_name="test",
            maximum_retry_count=2
        )
        
        original_metadata = {
            "important_field": "important_value",
            "trace": {"existing_data": "preserved"}
        }
        
        state_at_max_retries = classifier.GraphState(
            text="original text",
            metadata=original_metadata,
            results={"previous": "results"},
            retry_count=2,
            classification=None,
            chat_history=[{"type": "human", "content": "previous chat"}]
        )
        
        max_retries_node = classifier.get_max_retries_node()
        result = await max_retries_node(state_at_max_retries)
        
        # Verify state preservation
        assert result.text == "original text"
        assert result.metadata == original_metadata
        assert result.results == {"previous": "results"}
        assert result.retry_count == 2
        assert result.chat_history == [{"type": "human", "content": "previous chat"}]
        
        # Verify max retries handling
        assert result.classification == "unknown"
        assert result.explanation == "Maximum retries reached"


class TestClassifierComplexIntegrationScenarios:
    """Test complex integration scenarios and real-world edge cases"""
    
    @pytest.mark.asyncio
    async def test_classification_with_input_output_aliasing(self):
        """Test classifier with BaseNode input/output aliasing functionality"""
        try:
            from plexus.scores.nodes.Classifier import Classifier
            from langchain_core.messages import AIMessage
        except ImportError:
            pytest.skip("Classifier dependencies not available")
            
        mock_model = AsyncMock()
        mock_model.ainvoke = AsyncMock(return_value=AIMessage(content="positive"))
        
        with patch('plexus.LangChainUser.LangChainUser._initialize_model', return_value=mock_model):
            classifier = Classifier(
                name="test_classifier",
                valid_classes=["positive", "negative"],
                system_message="Classify the sentiment",
                user_message="Classify: {input_text}",
                model_provider="test",
                model_name="test",
                input={"input_text": "original_text_field"},
                output={"sentiment": "classification"}
            )
            classifier.model = mock_model
            
            # Test that the classifier handles aliasing properly
            # This would normally be tested through the full workflow execution
            assert classifier.parameters.input == {"input_text": "original_text_field"}
            assert classifier.parameters.output == {"sentiment": "classification"}

    @pytest.mark.asyncio
    async def test_message_serialization_and_deserialization(self):
        """Test complex message serialization/deserialization scenarios"""
        try:
            from plexus.scores.nodes.Classifier import Classifier
            from langchain_core.messages import AIMessage, HumanMessage, SystemMessage
        except ImportError:
            pytest.skip("Classifier dependencies not available")
            
        mock_model = AsyncMock()
        mock_model.ainvoke = AsyncMock(return_value=AIMessage(content="yes"))
        
        with patch('plexus.LangChainUser.LangChainUser._initialize_model', return_value=mock_model):
            classifier = Classifier(
                name="test_classifier",
                valid_classes=["yes", "no"],
                system_message="Classify this",
                user_message="Is this positive? {text}",
                model_provider="test",
                model_name="test"
            )
            classifier.model = mock_model
            
            # Create state with mixed message types (dict and objects)
            mixed_messages = [
                SystemMessage(content="System message"),
                {
                    'type': 'human',
                    'content': 'Human message from dict',
                    '_type': 'HumanMessage'
                },
                AIMessage(content="AI message object")
            ]
            
            state = classifier.GraphState(
                text="Test text",
                messages=mixed_messages,
                metadata={},
                retry_count=0
            )
            
            llm_prompt_node = classifier.get_llm_prompt_node()
            result_state = await llm_prompt_node(state)
            
            # Verify that messages were properly serialized
            assert result_state.messages is not None
            assert len(result_state.messages) > 0
            
            # All messages should now be in dict format
            for msg in result_state.messages:
                assert isinstance(msg, dict)
                assert 'type' in msg
                assert 'content' in msg

    @pytest.mark.asyncio
    async def test_state_management_across_workflow_nodes(self):
        """Test that state is properly managed across all workflow nodes"""
        try:
            from plexus.scores.nodes.Classifier import Classifier
            from langchain_core.messages import AIMessage
        except ImportError:
            pytest.skip("Classifier dependencies not available")
            
        mock_model = AsyncMock()
        mock_model.ainvoke = AsyncMock(return_value=AIMessage(content="positive"))
        
        with patch('plexus.LangChainUser.LangChainUser._initialize_model', return_value=mock_model):
            classifier = Classifier(
                name="sentiment_classifier",
                valid_classes=["positive", "negative", "neutral"],
                system_message="You are a sentiment classifier",
                user_message="Classify sentiment: {text}",
                model_provider="test",
                model_name="test"
            )
            classifier.model = mock_model
            
            initial_metadata = {
                "trace": {"node_results": []},
                "account_key": "test_account",
                "scorecard_key": "test_scorecard"
            }
            
            initial_state = classifier.GraphState(
                text="This is a wonderful day!",
                metadata=initial_metadata,
                results={"previous_scores": [0.8, 0.9]},
                retry_count=0,
                is_not_empty=True,
                value="initial_value",
                reasoning="initial_reasoning",
                classification=None,
                chat_history=[],
                completion=None
            )
            
            # Execute full node sequence
            llm_prompt_node = classifier.get_llm_prompt_node()
            llm_call_node = classifier.get_llm_call_node()
            parse_node = classifier.get_parser_node()
            
            state_after_prompt = await llm_prompt_node(initial_state)
            state_after_llm = await llm_call_node(state_after_prompt)
            final_state = await parse_node(state_after_llm)
            
            # Verify state preservation through all nodes
            assert final_state.text == initial_state.text
            assert final_state.metadata["account_key"] == "test_account"
            assert final_state.metadata["scorecard_key"] == "test_scorecard"
            assert final_state.results == {"previous_scores": [0.8, 0.9]}
            assert final_state.value == "initial_value"
            assert final_state.reasoning == "initial_reasoning"
            
            # Verify classification was added
            assert final_state.classification == "positive"

    @pytest.mark.asyncio
    async def test_concurrent_classification_scenarios(self):
        """Test scenarios that might occur under concurrent execution"""
        try:
            from plexus.scores.nodes.Classifier import Classifier
            from langchain_core.messages import AIMessage
        except ImportError:
            pytest.skip("Classifier dependencies not available")
            
        mock_model = AsyncMock()
        mock_model.ainvoke = AsyncMock(return_value=AIMessage(content="yes"))
        
        with patch('plexus.LangChainUser.LangChainUser._initialize_model', return_value=mock_model):
            classifier = Classifier(
                name="concurrent_classifier",
                valid_classes=["yes", "no"],
                system_message="Classify this",
                user_message="Answer yes or no: {text}",
                model_provider="test",
                model_name="test"
            )
            classifier.model = mock_model
            
            # Create multiple similar states (simulating concurrent execution)
            states = []
            for i in range(5):
                state = classifier.GraphState(
                    text=f"Test text {i}",
                    metadata={"thread_id": f"thread_{i}"},
                    retry_count=0,
                    classification=None,
                    chat_history=[],
                    completion=None
                )
                states.append(state)
            
            # Execute nodes on all states
            llm_prompt_node = classifier.get_llm_prompt_node()
            llm_call_node = classifier.get_llm_call_node()
            parse_node = classifier.get_parser_node()
            
            results = []
            for state in states:
                state = await llm_prompt_node(state)
                state = await llm_call_node(state)
                final_state = await parse_node(state)
                results.append(final_state)
            
            # Verify each state maintained its identity
            for i, result in enumerate(results):
                assert result.text == f"Test text {i}"
                assert result.metadata["thread_id"] == f"thread_{i}"
                assert result.classification == "yes"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])