"""
Test suite for conversation utilities.

This module provides comprehensive test coverage for the ConversationUtils class,
focusing on conversation history filtering and processing functionality.
"""

import pytest
from unittest.mock import patch, MagicMock
from typing import List

from plexus.cli.procedure.conversation_utils import ConversationUtils


class MockMessage:
    """Mock message class for testing."""
    
    def __init__(self, content: str, message_type: str = "system"):
        self.content = content
        self.message_type = message_type


class MockSystemMessage(MockMessage):
    """Mock SystemMessage for testing."""
    
    def __init__(self, content: str):
        super().__init__(content, "system")


class MockHumanMessage(MockMessage):
    """Mock HumanMessage for testing."""
    
    def __init__(self, content: str):
        super().__init__(content, "human")


class MockAIMessage(MockMessage):
    """Mock AIMessage for testing."""
    
    def __init__(self, content: str):
        super().__init__(content, "ai")


class TestConversationUtils:
    """Test suite for ConversationUtils class."""
    
    def setup_method(self):
        """Set up test fixtures before each test method."""
        self.utils = ConversationUtils()
    
    @patch('plexus.cli.procedure.conversation_utils.logger')
    def test_filter_conversation_history_empty_list(self, mock_logger):
        """Test filtering with an empty conversation history."""
        result = ConversationUtils.filter_conversation_history_for_model([])
        
        assert result == []
        mock_logger.info.assert_called()
        
        # Verify logging calls
        log_calls = [call.args[0] for call in mock_logger.info.call_args_list]
        assert any("Original history: 0 messages" in call for call in log_calls)
        assert any("Filtered history: 0 messages" in call for call in log_calls)
    
    @patch('plexus.cli.procedure.conversation_utils.logger')
    def test_filter_conversation_history_no_tool_messages(self, mock_logger):
        """Test filtering with no tool result messages."""
        # Mock the langchain imports inside the function
        with patch('langchain_core.messages.SystemMessage', MockSystemMessage), \
             patch('langchain_core.messages.HumanMessage', MockHumanMessage), \
             patch('langchain_core.messages.AIMessage', MockAIMessage):
            
            conversation = [
                MockSystemMessage("System initialization message"),
                MockHumanMessage("User question"),
                MockAIMessage("AI response"),
                MockSystemMessage("Another system message")
            ]
            
            result = ConversationUtils.filter_conversation_history_for_model(conversation)
            
            assert len(result) == 4
            assert all(msg.content == orig.content for msg, orig in zip(result, conversation))
            
            # Verify no tool result messages were detected
            log_calls = [call.args[0] for call in mock_logger.info.call_args_list]
            assert any("Found 0 tool result messages" in call for call in log_calls)
    
    @patch('plexus.cli.procedure.conversation_utils.logger')
    def test_filter_conversation_history_with_tool_messages_under_limit(self, mock_logger):
        """Test filtering with tool result messages under the truncation limit."""
        with patch('langchain_core.messages.SystemMessage', MockSystemMessage), \
             patch('langchain_core.messages.HumanMessage', MockHumanMessage), \
             patch('langchain_core.messages.AIMessage', MockAIMessage):
            
            conversation = [
                MockSystemMessage("System initialization"),
                MockHumanMessage("User question"),
                MockSystemMessage("Tool search result: Small result content"),
                MockAIMessage("AI response"),
                MockSystemMessage("Tool analysis result: Another small result")
            ]
            
            result = ConversationUtils.filter_conversation_history_for_model(conversation)
            
            assert len(result) == 5
            # All messages should be kept as-is since tool results are small
            assert all(msg.content == orig.content for msg, orig in zip(result, conversation))
            
            # Verify tool result messages were detected
            log_calls = [call.args[0] for call in mock_logger.info.call_args_list]
            assert any("Found 2 tool result messages" in call for call in log_calls)
    
    @patch('plexus.cli.procedure.conversation_utils.logger')
    def test_filter_conversation_history_with_large_tool_messages_recent(self, mock_logger):
        """Test filtering with large tool result messages that are recent (should be kept in full)."""
        with patch('langchain_core.messages.SystemMessage', MockSystemMessage), \
             patch('langchain_core.messages.HumanMessage', MockHumanMessage), \
             patch('langchain_core.messages.AIMessage', MockAIMessage):
            
            large_content = "Tool search result: " + "x" * 1000  # Large content > 500 chars
            conversation = [
                MockSystemMessage("System initialization"),
                MockHumanMessage("User question"),
                MockSystemMessage(large_content),
                MockAIMessage("AI response"),
                MockSystemMessage("Tool analysis result: Recent small result")
            ]
            
            result = ConversationUtils.filter_conversation_history_for_model(conversation)
            
            assert len(result) == 5
            # The large tool message should be kept in full since it's one of the most recent 2
            assert result[2].content == large_content
            
            # Verify logging
            log_calls = [call.args[0] for call in mock_logger.info.call_args_list]
            assert any("Found 2 tool result messages" in call for call in log_calls)
            assert any("Keeping recent tool result" in call for call in log_calls)
    
    @patch('plexus.cli.procedure.conversation_utils.logger')
    def test_filter_conversation_history_with_old_large_tool_messages(self, mock_logger):
        """Test filtering with old large tool result messages (should be truncated)."""
        with patch('langchain_core.messages.SystemMessage', MockSystemMessage), \
             patch('langchain_core.messages.HumanMessage', MockHumanMessage), \
             patch('langchain_core.messages.AIMessage', MockAIMessage):
            
            # Need more than 2 tool results for truncation to happen
            large_content_1 = "Tool search result: " + "x" * 1000  # Old large content - should be truncated
            large_content_2 = "Tool analysis result: " + "y" * 800  # Old large content - should be truncated  
            recent_content_1 = "Tool intermediate result: Recent 1"  # Recent - should be kept
            recent_content_2 = "Tool final result: Recent 2"  # Recent - should be kept
            
            conversation = [
                MockSystemMessage("System initialization"),
                MockSystemMessage(large_content_1),   # Tool result #0 - old, should be truncated
                MockHumanMessage("User question"),
                MockSystemMessage(large_content_2),   # Tool result #1 - old, should be truncated
                MockAIMessage("AI response"),
                MockSystemMessage(recent_content_1),  # Tool result #2 - recent, should be kept
                MockSystemMessage(recent_content_2)   # Tool result #3 - recent, should be kept
            ]
            
            result = ConversationUtils.filter_conversation_history_for_model(conversation)
            
            assert len(result) == 7
            
            # With 4 tool results, only the first 2 (indexes 0,1) should be truncated
            # Most recent 2 (indexes 2,3) should be kept: tool_result_index >= (4-2) = 2
            
            # Check that old tool results were truncated (tool results 0 and 1)
            assert len(result[1].content) < len(large_content_1)
            assert "TOOL RESULT TRUNCATED" in result[1].content
            assert len(result[3].content) < len(large_content_2)
            assert "TOOL RESULT TRUNCATED" in result[3].content
            
            # Check that recent tool results were kept in full (tool results 2 and 3)
            assert result[5].content == recent_content_1
            assert result[6].content == recent_content_2
            
            # Verify logging
            log_calls = [call.args[0] for call in mock_logger.info.call_args_list]
            assert any("Found 4 tool result messages" in call for call in log_calls)
            assert any("Truncated older tool result" in call for call in log_calls)
    
    @patch('plexus.cli.procedure.conversation_utils.logger')
    def test_filter_conversation_history_truncation_details(self, mock_logger):
        """Test that truncation preserves exactly 500 characters plus notice."""
        with patch('langchain_core.messages.SystemMessage', MockSystemMessage), \
             patch('langchain_core.messages.HumanMessage', MockHumanMessage), \
             patch('langchain_core.messages.AIMessage', MockAIMessage):
            
            large_content = "Tool search result: " + "x" * 1000
            medium_content = "Tool analysis result: " + "y" * 600  
            recent_content = "Tool final result: Recent"
            
            conversation = [
                MockSystemMessage(large_content),   # Tool result #0 - old, should be truncated
                MockSystemMessage(medium_content),  # Tool result #1 - old, should be truncated
                MockSystemMessage(recent_content)   # Tool result #2 - recent, should be kept
            ]
            
            result = ConversationUtils.filter_conversation_history_for_model(conversation)
            
            # Check truncation details on first (oldest) tool result - only this one should be truncated
            truncated_msg = result[0]
            assert large_content[:500] in truncated_msg.content
            assert "[TOOL RESULT TRUNCATED at 500 chars" in truncated_msg.content
            assert f"original was {len(large_content)} chars" in truncated_msg.content
            
            # Check that second tool result was kept (it's one of the most recent 2)
            assert result[1].content == medium_content
            assert "TOOL RESULT TRUNCATED" not in result[1].content
            
            # Recent message should be unchanged
            assert result[2].content == recent_content
    
    def test_filter_conversation_history_mixed_message_types(self):
        """Test filtering with a mix of different message types."""
        with patch('langchain_core.messages.SystemMessage', MockSystemMessage), \
             patch('langchain_core.messages.HumanMessage', MockHumanMessage), \
             patch('langchain_core.messages.AIMessage', MockAIMessage):
            
            conversation = [
                MockSystemMessage("System initialization"),
                MockHumanMessage("User question 1"),
                MockSystemMessage("Tool search result: Tool output 1"),
                MockAIMessage("AI response 1"),
                MockHumanMessage("User question 2"),
                MockSystemMessage("Tool analysis result: Tool output 2"),
                MockAIMessage("AI response 2"),
                MockSystemMessage("Non-tool system message")
            ]
            
            result = ConversationUtils.filter_conversation_history_for_model(conversation)
            
            assert len(result) == 8
            # All messages should be preserved since tool results are small and recent
            assert all(msg.content == orig.content for msg, orig in zip(result, conversation))
    
    def test_filter_conversation_history_edge_case_exactly_500_chars(self):
        """Test filtering with tool result exactly at 500 character limit."""
        with patch('langchain_core.messages.SystemMessage', MockSystemMessage), \
             patch('langchain_core.messages.HumanMessage', MockHumanMessage), \
             patch('langchain_core.messages.AIMessage', MockAIMessage):
            
            content_500 = "Tool search result: " + "x" * (500 - len("Tool search result: "))
            recent_content = "Tool final result: Recent"
            
            conversation = [
                MockSystemMessage(content_500),    # Exactly 500 chars - should not be truncated
                MockSystemMessage(recent_content)  # Recent
            ]
            
            result = ConversationUtils.filter_conversation_history_for_model(conversation)
            
            # Message with exactly 500 chars should not be truncated
            assert result[0].content == content_500
            assert "TOOL RESULT TRUNCATED" not in result[0].content
            assert result[1].content == recent_content
    
    def test_filter_conversation_history_single_tool_message(self):
        """Test filtering with only one tool result message."""
        with patch('langchain_core.messages.SystemMessage', MockSystemMessage):
            
            conversation = [
                MockSystemMessage("Tool search result: Single tool result")
            ]
            
            result = ConversationUtils.filter_conversation_history_for_model(conversation)
            
            assert len(result) == 1
            # Single tool result should be kept in full (it's among the most recent 2)
            assert result[0].content == conversation[0].content
    
    def test_filter_conversation_history_langchain_import_fallback(self):
        """Test that the function handles langchain import fallback correctly."""
        # This test verifies that the function can handle different langchain import paths
        # We'll simulate an ImportError for langchain_core and ensure it falls back to langchain.schema
        
        with patch('langchain_core.messages.SystemMessage', side_effect=ImportError), \
             patch('langchain.schema.SystemMessage', MockSystemMessage), \
             patch('langchain.schema.HumanMessage', MockHumanMessage), \
             patch('langchain.schema.AIMessage', MockAIMessage), \
             patch('plexus.cli.procedure.conversation_utils.logger') as mock_logger:
            
            # Test should not raise an exception and should work with fallback imports
            result = ConversationUtils.filter_conversation_history_for_model([])
            assert result == []
    
    def test_filter_conversation_history_non_tool_system_messages(self):
        """Test that non-tool SystemMessages are preserved correctly."""
        with patch('langchain_core.messages.SystemMessage', MockSystemMessage):
            
            conversation = [
                MockSystemMessage("System initialization - no tool content"),
                MockSystemMessage("Another system message without tool keyword"),
                MockSystemMessage("Tool search result: This is a tool message"),
                MockSystemMessage("System message with Tool in text but no result:")
            ]
            
            result = ConversationUtils.filter_conversation_history_for_model(conversation)
            
            assert len(result) == 4
            # Only one message should be identified as a tool result
            # (the one with both "Tool" and "result:" in content)
            assert all(msg.content == orig.content for msg, orig in zip(result, conversation))
    
    @patch('plexus.cli.procedure.conversation_utils.logger')
    def test_filter_conversation_history_multiple_recent_large_tools(self, mock_logger):
        """Test that multiple recent large tool results are both kept in full."""
        with patch('langchain_core.messages.SystemMessage', MockSystemMessage):
            
            large_content_1 = "Tool search result: " + "x" * 1000
            large_content_2 = "Tool analysis result: " + "y" * 800
            
            conversation = [
                MockSystemMessage(large_content_1),  # Recent - should be kept in full
                MockSystemMessage(large_content_2)   # Recent - should be kept in full
            ]
            
            result = ConversationUtils.filter_conversation_history_for_model(conversation)
            
            assert len(result) == 2
            # Both should be kept in full since they're the most recent 2
            assert result[0].content == large_content_1
            assert result[1].content == large_content_2
            assert "TOOL RESULT TRUNCATED" not in result[0].content
            assert "TOOL RESULT TRUNCATED" not in result[1].content
    
    def test_filter_conversation_history_tool_detection_patterns(self):
        """Test various patterns for tool result detection."""
        with patch('langchain_core.messages.SystemMessage', MockSystemMessage):
            
            conversation = [
                MockSystemMessage("Tool search result: Valid tool message"),
                MockSystemMessage("Tool analysis result: Another valid tool message"),
                MockSystemMessage("Tool but no result: keyword"),  # Invalid - no "result:"
                MockSystemMessage("No tool keyword result: here"),  # Invalid - no "Tool"
                MockSystemMessage("Contains Tool and result: but mixed case"),  # Valid
                MockSystemMessage("TOOL UPPER CASE result: testing"),  # Valid - case sensitive
                MockSystemMessage("Random message with no keywords"),  # Invalid
                MockSystemMessage("Tool with result: at end"),  # Valid
            ]
            
            result = ConversationUtils.filter_conversation_history_for_model(conversation)
            
            assert len(result) == 8
            # All messages should be preserved since we're not truncating in this test
            assert all(msg.content == orig.content for msg, orig in zip(result, conversation))
    
    def test_filter_conversation_history_edge_case_empty_content(self):
        """Test filtering with messages that have empty content."""
        with patch('langchain_core.messages.SystemMessage', MockSystemMessage):
            
            conversation = [
                MockSystemMessage(""),  # Empty content
                MockSystemMessage("Tool search result: Valid content"),
                MockSystemMessage(""),  # Another empty content
            ]
            
            result = ConversationUtils.filter_conversation_history_for_model(conversation)
            
            assert len(result) == 3
            # Empty messages should be preserved as-is
            assert result[0].content == ""
            assert result[1].content == "Tool search result: Valid content"
            assert result[2].content == ""
    
    def test_filter_conversation_history_very_large_truncation(self):
        """Test truncation with very large content."""
        with patch('langchain_core.messages.SystemMessage', MockSystemMessage), \
             patch('plexus.cli.procedure.conversation_utils.logger'):
            
            # Create a very large tool result (10KB) - need 3+ tool results for truncation
            large_content = "Tool search result: " + "x" * 10000
            medium_content = "Tool analysis result: " + "y" * 5000
            recent_content = "Tool final result: Recent"
            
            conversation = [
                MockSystemMessage(large_content),   # Tool result #0 - should be truncated
                MockSystemMessage(medium_content),  # Tool result #1 - should be truncated 
                MockSystemMessage(recent_content)   # Tool result #2 - should be kept
            ]
            
            result = ConversationUtils.filter_conversation_history_for_model(conversation)
            
            assert len(result) == 3
            
            # With 3 tool results, only the first one (index 0) should be truncated
            # Most recent 2 (indexes 1,2) should be kept: tool_result_index >= (3-2) = 1
            
            # Check that truncation happened correctly on the first (largest) message
            truncated_msg = result[0]
            assert len(truncated_msg.content) < len(large_content)
            assert large_content[:500] in truncated_msg.content
            assert "[TOOL RESULT TRUNCATED at 500 chars" in truncated_msg.content
            assert f"original was {len(large_content)} chars" in truncated_msg.content
            
            # Check that second message was kept (it's one of the most recent 2)
            assert result[1].content == medium_content
            assert "TOOL RESULT TRUNCATED" not in result[1].content
            
            # Recent message should be unchanged
            assert result[2].content == recent_content


if __name__ == "__main__":
    pytest.main([__file__])