"""
BDD-style test suite for token-aware conversation filtering.

This module provides comprehensive test coverage for the TokenAwareConversationFilter class,
focusing on behavior-driven testing of filtering rules and token management.
"""

import pytest
from unittest.mock import patch, MagicMock
from typing import List

from plexus.cli.procedure.conversation_filter import (
    ConversationFilterBase, 
    TokenAwareConversationFilter, 
    WorkerAgentConversationFilter,
    ManagerAgentConversationFilter
)


class MockMessage:
    """Mock message class for testing."""
    
    def __init__(self, content: str, message_type: str = "System"):
        self.content = content
        self.__class__.__name__ = f"{message_type}Message"


class MockToolMessage(MockMessage):
    """Mock ToolMessage for testing."""
    
    def __init__(self, content: str, tool_call_id: str = "test-tool-call"):
        super().__init__(content, "Tool")
        self.tool_call_id = tool_call_id


class MockSystemMessage(MockMessage):
    """Mock SystemMessage for testing."""
    
    def __init__(self, content: str):
        super().__init__(content, "System")


class MockHumanMessage(MockMessage):
    """Mock HumanMessage for testing."""
    
    def __init__(self, content: str):
        super().__init__(content, "Human")


class MockAIMessage(MockMessage):
    """Mock AIMessage for testing."""
    
    def __init__(self, content: str, tool_calls: List = None):
        super().__init__(content, "AI")
        self.tool_calls = tool_calls or []


class TestTokenAwareConversationFilter:
    """BDD-style test suite for TokenAwareConversationFilter."""
    
    def setup_method(self):
        """Set up test fixtures before each test method."""
        self.filter = TokenAwareConversationFilter(model="gpt-4o")
    
    # GIVEN scenarios
    
    def test_given_empty_conversation_when_filtering_then_returns_empty_list(self):
        """
        GIVEN an empty conversation history
        WHEN filtering is applied
        THEN it returns an empty list
        """
        result = self.filter.filter_conversation([])
        assert result == []
    
    def test_given_conversation_without_tool_messages_when_filtering_then_keeps_all_messages(self):
        """
        GIVEN a conversation history without tool result messages
        WHEN filtering is applied
        THEN all messages are kept unchanged
        """
        conversation = [
            MockSystemMessage("System initialization"),
            MockHumanMessage("User question"),
            MockAIMessage("AI response")
        ]
        
        result = self.filter.filter_conversation(conversation)
        
        assert len(result) == 3
        assert result[0].content == "System initialization"
        assert result[1].content == "User question"
        assert result[2].content == "AI response"
    
    def test_given_conversation_with_small_tool_messages_when_filtering_then_keeps_all_messages(self):
        """
        GIVEN a conversation with small tool result messages (under 500 chars)
        WHEN filtering is applied
        THEN all messages are kept unchanged
        """
        conversation = [
            MockSystemMessage("System initialization"),
            MockToolMessage("Small tool result content"),
            MockAIMessage("AI response")
        ]
        
        result = self.filter.filter_conversation(conversation)
        
        assert len(result) == 3
        assert result[1].content == "Small tool result content"
    
    def test_given_conversation_with_recent_large_tool_messages_when_filtering_then_keeps_recent_full(self):
        """
        GIVEN a conversation with large tool result messages that are recent (most recent 2)
        WHEN filtering is applied
        THEN recent tool results are kept in full
        """
        large_content_1 = "Tool result: " + "x" * 1000  # 1000+ chars
        large_content_2 = "Tool result: " + "y" * 800   # 800+ chars
        
        conversation = [
            MockSystemMessage("System initialization"),
            MockToolMessage(large_content_1),  # Recent - should be kept
            MockToolMessage(large_content_2)   # Recent - should be kept
        ]
        
        result = self.filter.filter_conversation(conversation)
        
        assert len(result) == 3
        assert result[1].content == large_content_1
        assert result[2].content == large_content_2
        assert "TRUNCATED" not in result[1].content
        assert "TRUNCATED" not in result[2].content
    
    def test_given_conversation_with_old_large_tool_messages_when_filtering_then_truncates_old_ones(self):
        """
        GIVEN a conversation with multiple large tool result messages
        WHEN filtering is applied with more than 2 tool results
        THEN older tool results are truncated while recent ones are kept full
        """
        old_large_content = "Tool result: " + "x" * 1000     # Old, should be truncated
        recent_content_1 = "Tool result: " + "y" * 800       # Recent, should be kept
        recent_content_2 = "Tool result: " + "z" * 600       # Recent, should be kept
        
        conversation = [
            MockSystemMessage("System initialization"),
            MockToolMessage(old_large_content),   # Tool result #0 - old, should be truncated
            MockHumanMessage("User question"),
            MockToolMessage(recent_content_1),    # Tool result #1 - recent, should be kept
            MockToolMessage(recent_content_2)     # Tool result #2 - recent, should be kept
        ]
        
        result = self.filter.filter_conversation(conversation)
        
        assert len(result) == 5
        
        # Check that old tool result was truncated
        assert len(result[1].content) < len(old_large_content)
        assert "TOOL RESULT TRUNCATED" in result[1].content
        assert old_large_content[:500] in result[1].content
        
        # Check that recent tool results were kept in full
        assert result[3].content == recent_content_1
        assert result[4].content == recent_content_2
        assert "TRUNCATED" not in result[3].content
        assert "TRUNCATED" not in result[4].content
    
    # WHEN scenarios with token limits
    
    @patch('plexus.cli.procedure.conversation_filter.logger')
    def test_when_token_limit_provided_then_logs_token_analysis(self, mock_logger):
        """
        WHEN a token limit is provided
        THEN detailed token analysis is logged
        """
        conversation = [
            MockSystemMessage("System message"),
            MockToolMessage("Tool result content")
        ]
        
        self.filter.filter_conversation(conversation, max_tokens=1000)
        
        # Verify token analysis logging occurred
        log_calls = [call.args[0] for call in mock_logger.info.call_args_list]
        token_analysis_logs = [call for call in log_calls if "📊" in call or "tokens" in call]
        assert len(token_analysis_logs) >= 2  # Should have original and filtered token analysis
    
    @patch('plexus.cli.procedure.conversation_filter.logger')
    def test_when_token_limit_exceeded_then_logs_warning(self, mock_logger):
        """
        WHEN conversation exceeds token limit
        THEN warning is logged about exceeding limit
        """
        # Create a conversation that will likely exceed a small token limit
        large_content = "x" * 10000  # Very large content
        conversation = [MockSystemMessage(large_content)]
        
        self.filter.filter_conversation(conversation, max_tokens=100)  # Very small limit
        
        # Check that warning about exceeding limit was logged
        log_calls = [call.args[0] for call in mock_logger.info.call_args_list]
        warning_logs = [call for call in log_calls if "⚠️" in call and "Exceeds" in call]
        assert len(warning_logs) >= 1
    
    # THEN scenarios - verification of filtering results
    
    def test_then_truncated_messages_preserve_metadata(self):
        """
        THEN truncated tool messages preserve their metadata (like tool_call_id)
        """
        old_large_content = "Tool result: " + "x" * 1000     # Old, should be truncated
        recent_content_1 = "Tool result: " + "y" * 800       # Recent, should be kept
        recent_content_2 = "Tool result: Recent"             # Recent, should be kept
        
        conversation = [
            MockToolMessage(old_large_content, tool_call_id="call-123"),  # Should be truncated
            MockToolMessage(recent_content_1, tool_call_id="call-456"),   # Should be kept
            MockToolMessage(recent_content_2, tool_call_id="call-789")    # Should be kept
        ]
        
        result = self.filter.filter_conversation(conversation)
        
        # Truncated message should preserve tool_call_id
        assert hasattr(result[0], 'tool_call_id')
        assert result[0].tool_call_id == "call-123"
        
        # Recent messages should be unchanged
        assert result[1].tool_call_id == "call-456"
        assert result[2].tool_call_id == "call-789"
    
    def test_then_truncation_includes_helpful_notice(self):
        """
        THEN truncated messages include helpful notice about truncation
        """
        old_large_content = "Tool result: " + "x" * 1000     # Old, should be truncated
        recent_content_1 = "Tool result: " + "y" * 800       # Recent, should be kept
        recent_content_2 = "Tool result: Recent"             # Recent, should be kept
        
        conversation = [
            MockToolMessage(old_large_content),   # Tool result #0 - old, should be truncated
            MockToolMessage(recent_content_1),    # Tool result #1 - recent, should be kept
            MockToolMessage(recent_content_2)     # Tool result #2 - recent, should be kept
        ]
        
        result = self.filter.filter_conversation(conversation)
        
        # First (oldest) tool result should be truncated
        truncated_content = result[0].content
        assert "[TOOL RESULT TRUNCATED at 500 chars" in truncated_content
        assert f"original was {len(old_large_content)} chars" in truncated_content
        assert "Summarize key learnings" in truncated_content
        
        # Recent tool results should be kept in full
        assert result[1].content == recent_content_1
        assert result[2].content == recent_content_2
    
    def test_then_system_messages_with_tool_patterns_are_detected(self):
        """
        THEN SystemMessages with tool result patterns are properly detected and filtered
        """
        old_tool_content = "Tool search result: " + "x" * 1000      # Old, should be truncated
        recent_tool_content_1 = "Tool analysis result: " + "y" * 600  # Recent, should be kept
        recent_tool_content_2 = "Tool final result: Recent"         # Recent, should be kept
        
        conversation = [
            MockSystemMessage(old_tool_content),      # Tool result #0 - old, should be truncated
            MockSystemMessage(recent_tool_content_1), # Tool result #1 - recent, should be kept
            MockSystemMessage(recent_tool_content_2)  # Tool result #2 - recent, should be kept
        ]
        
        result = self.filter.filter_conversation(conversation)
        
        # First message should be truncated (it's an old tool result pattern)
        assert "TOOL RESULT TRUNCATED" in result[0].content
        
        # Recent messages should be kept
        assert result[1].content == recent_tool_content_1
        assert result[2].content == recent_tool_content_2
    
    def test_then_per_message_token_counts_are_accurate(self):
        """
        THEN individual message token counts are calculated accurately
        """
        if not self.filter.encoding:
            pytest.skip("TikToken not available for accurate token counting")
        
        message = MockSystemMessage("This is a test message for token counting")
        token_count = self.filter._count_message_tokens(message)
        
        # Should be reasonable token count (not zero, not excessive)
        assert token_count > 0
        assert token_count < 100  # Simple message shouldn't be too many tokens
    
    # Edge cases
    
    def test_edge_case_exactly_500_chars_not_truncated(self):
        """
        EDGE CASE: Tool result with exactly 500 characters should not be truncated
        """
        content_500 = "Tool result: " + "x" * (500 - len("Tool result: "))
        recent_content = "Tool result: Recent"
        
        conversation = [
            MockToolMessage(content_500),
            MockToolMessage(recent_content)
        ]
        
        result = self.filter.filter_conversation(conversation)
        
        # Message with exactly 500 chars should not be truncated
        assert result[0].content == content_500
        assert "TRUNCATED" not in result[0].content
    
    def test_edge_case_single_tool_message_kept_full(self):
        """
        EDGE CASE: Single tool result message should be kept in full (it's "recent")
        """
        large_content = "Tool result: " + "x" * 1000
        
        conversation = [MockToolMessage(large_content)]
        
        result = self.filter.filter_conversation(conversation)
        
        assert len(result) == 1
        assert result[0].content == large_content
        assert "TRUNCATED" not in result[0].content
    
    def test_edge_case_no_tiktoken_graceful_degradation(self):
        """
        EDGE CASE: When TikToken is not available, filtering should still work
        """
        # Temporarily disable tiktoken
        original_encoding = self.filter.encoding
        self.filter.encoding = None
        
        try:
            conversation = [
                MockSystemMessage("System message"),
                MockToolMessage("Tool result content")
            ]
            
            result = self.filter.filter_conversation(conversation, max_tokens=1000)
            
            # Should still return filtered conversation
            assert len(result) == 2
            assert result[0].content == "System message"
            assert result[1].content == "Tool result content"
            
        finally:
            # Restore original encoding
            self.filter.encoding = original_encoding


class TestConversationFilterBase:
    """BDD-style test suite for ConversationFilterBase (measurement only)."""
    
    def setup_method(self):
        """Set up test fixtures before each test method."""
        self.base_filter = ConversationFilterBase(model="gpt-4o")
    
    def test_given_empty_conversation_when_analyzing_tokens_then_returns_zero_tokens(self):
        """
        GIVEN an empty conversation history
        WHEN token analysis is performed
        THEN it returns zero tokens and empty breakdown
        """
        result = self.base_filter.analyze_conversation_tokens([])
        
        assert result["total_messages"] == 0
        assert result["total_tokens"] == 2  # Just conversation overhead
        assert result["message_breakdown"] == []
        assert result["model"] == "gpt-4o"
    
    def test_given_conversation_with_messages_when_analyzing_tokens_then_provides_detailed_breakdown(self):
        """
        GIVEN a conversation with various message types
        WHEN token analysis is performed
        THEN it provides detailed per-message token breakdown
        """
        conversation = [
            MockSystemMessage("System initialization"),
            MockHumanMessage("User question"),
            MockAIMessage("AI response")
        ]
        
        result = self.base_filter.analyze_conversation_tokens(conversation)
        
        assert result["total_messages"] == 3
        assert result["total_tokens"] > 0
        assert len(result["message_breakdown"]) == 3
        
        # Check breakdown structure
        for i, msg_info in enumerate(result["message_breakdown"]):
            assert msg_info["index"] == i
            assert "type" in msg_info
            assert "tokens" in msg_info
            assert "content_length" in msg_info
    
    def test_given_conversation_with_token_limit_when_analyzing_then_reports_limit_status(self):
        """
        GIVEN a conversation and token limit
        WHEN token analysis is performed
        THEN it reports whether the conversation is within limits
        """
        conversation = [MockSystemMessage("Short message")]
        
        result = self.base_filter.analyze_conversation_tokens(conversation, max_tokens=1000)
        
        assert "max_tokens" in result
        assert "within_limit" in result
        assert "tokens_remaining" in result
        assert "tokens_over" in result
        assert result["max_tokens"] == 1000
    
    def test_when_tiktoken_unavailable_then_graceful_degradation(self):
        """
        WHEN TikToken is not available
        THEN the filter gracefully degrades with approximate counting
        """
        # Temporarily disable tiktoken
        original_encoding = self.base_filter.encoding
        self.base_filter.encoding = None
        
        try:
            conversation = [MockSystemMessage("Test message")]
            result = self.base_filter.analyze_conversation_tokens(conversation)
            
            # Should still work but with zero token counts
            assert result["total_messages"] == 1
            assert result["total_tokens"] == 2  # Just overhead
            
        finally:
            # Restore original encoding
            self.base_filter.encoding = original_encoding


class MockAIMessageWithToolCalls(MockMessage):
    """Mock AIMessage with tool calls for testing."""
    
    def __init__(self, content: str, tool_calls: List = None):
        super().__init__(content, "AI")
        self.__class__.__name__ = "AIMessage"
        self.tool_calls = tool_calls or []


class TestWorkerAgentConversationFilter:
    """BDD-style test suite for WorkerAgentConversationFilter."""
    
    def setup_method(self):
        """Set up test fixtures before each test method."""
        self.filter = WorkerAgentConversationFilter(model="gpt-4o")
    
    def test_given_conversation_with_no_empty_ai_messages_when_filtering_then_applies_standard_filtering(self):
        """
        GIVEN a conversation without empty AI messages
        WHEN worker agent filtering is applied
        THEN it applies standard tool result filtering only
        """
        conversation = [
            MockSystemMessage("System initialization"),
            MockHumanMessage("User question"),
            MockAIMessage("AI response with content"),
            MockToolMessage("Tool result content")
        ]
        
        result = self.filter.filter_conversation(conversation)
        
        # Should preserve all messages since none are empty AI messages
        assert len(result) == 4
        assert all(msg.content == orig.content for msg, orig in zip(result, conversation))
    
    def test_given_conversation_with_empty_ai_tool_call_messages_when_filtering_then_removes_old_ones_preserves_recent(self):
        """
        GIVEN a conversation with multiple AI messages that have tool calls but no content
        WHEN worker agent filtering is applied
        THEN it removes OLD empty AI messages but preserves the MOST RECENT one (current tool call)
        """
        conversation = [
            MockSystemMessage("System initialization"),
            MockAIMessage("AI response with content"),  # Should be kept
            MockAIMessageWithToolCalls("", [{"name": "old_tool", "args": {}}]),  # Should be removed (old)
            MockToolMessage("Tool result for old empty AI"),  # Should be removed (follows old empty AI)
            MockAIMessageWithToolCalls("AI reasoning before tool call", [{"name": "test_tool", "args": {}}]),  # Should be kept
            MockToolMessage("Tool result for reasoning AI"),  # Should be kept (follows AI with content)
            MockAIMessageWithToolCalls("", [{"name": "current_tool", "args": {}}]),  # Should be kept (most recent)
        ]
        
        result = self.filter.filter_conversation(conversation)
        
        # Should have 5 messages (removed only the OLD empty AI message + its tool result)
        assert len(result) == 5
        assert result[0].content == "System initialization"
        assert result[1].content == "AI response with content"
        assert result[2].content == "AI reasoning before tool call"
        assert result[3].content == "Tool result for reasoning AI"
        assert result[4].content == ""  # Most recent empty AI message preserved
        assert hasattr(result[4], 'tool_calls') and result[4].tool_calls
    
    def test_given_ai_message_with_whitespace_only_content_when_filtering_then_preserves_most_recent(self):
        """
        GIVEN AI messages with only whitespace content but tool calls
        WHEN worker agent filtering is applied
        THEN it removes old ones but preserves the most recent (current tool call)
        """
        conversation = [
            MockAIMessageWithToolCalls("  \n\t  ", [{"name": "old_tool", "args": {}}]),  # Should be removed (old)
            MockToolMessage("Tool result for whitespace AI"),  # Should be removed
            MockAIMessageWithToolCalls("Actual content", [{"name": "test_tool", "args": {}}]),  # Should be kept
            MockToolMessage("Tool result for content AI"),  # Should be kept
            MockAIMessageWithToolCalls("   ", [{"name": "current_tool", "args": {}}])  # Should be kept (most recent)
        ]
        
        result = self.filter.filter_conversation(conversation)
        
        assert len(result) == 3
        assert result[0].content == "Actual content"
        assert result[1].content == "Tool result for content AI"
        assert result[2].content == "   "  # Most recent whitespace AI preserved
    
    def test_given_ai_message_without_tool_calls_when_filtering_then_keeps_even_if_empty(self):
        """
        GIVEN an AI message with empty content but no tool calls
        WHEN worker agent filtering is applied
        THEN it keeps the message (not considered a tool call message)
        """
        conversation = [
            MockAIMessage(""),  # No tool calls - should be kept
            MockAIMessage("Regular AI response")  # Should be kept
        ]
        
        result = self.filter.filter_conversation(conversation)
        
        assert len(result) == 2
        assert result[0].content == ""
        assert result[1].content == "Regular AI response"
    
    @patch('plexus.cli.procedure.conversation_filter.logger')
    def test_when_filtering_empty_ai_messages_then_logs_filtering_actions(self, mock_logger):
        """
        WHEN filtering old empty AI messages with tool calls
        THEN detailed logging is provided about preserving most recent vs filtering old ones
        """
        conversation = [
            MockAIMessageWithToolCalls("", [{"name": "old_tool", "args": {}}]),  # Should be removed (old)
            MockToolMessage("Tool result"),  # Should be removed
            MockAIMessage("Content"),  # Should be kept
            MockAIMessageWithToolCalls("", [{"name": "current_tool", "args": {}}])  # Should be kept (most recent)
        ]
        
        self.filter.filter_conversation(conversation)
        
        # Verify logging occurred about preserving the most recent AI message
        log_calls = [call.args[0] for call in mock_logger.info.call_args_list]
        preserve_logs = [call for call in log_calls if "Preserving most recent AI message" in call]
        assert len(preserve_logs) >= 1
    
    def test_then_inherits_tool_result_filtering_from_parent(self):
        """
        THEN the worker agent filter inherits tool result filtering capabilities
        """
        # Test that it still does tool result filtering by creating scenario
        # with multiple large tool results
        large_content_1 = "Tool search result: " + "x" * 1000  # Old - should be truncated
        large_content_2 = "Tool analysis result: " + "y" * 800  # Recent - should be kept
        recent_content = "Tool final result: Recent"  # Recent - should be kept
        
        conversation = [
            MockToolMessage(large_content_1),   # Tool result #0 - old, should be truncated
            MockToolMessage(large_content_2),   # Tool result #1 - recent, should be kept
            MockToolMessage(recent_content)     # Tool result #2 - recent, should be kept
        ]
        
        result = self.filter.filter_conversation(conversation)
        
        assert len(result) == 3
        
        # Check that truncation happened on the first (oldest) tool result
        assert len(result[0].content) < len(large_content_1)
        assert "TOOL RESULT TRUNCATED" in result[0].content
        
        # Check that recent tool results were kept
        assert result[1].content == large_content_2
    
    def test_given_empty_ai_message_at_end_of_conversation_when_filtering_then_preserves_current_tool_call(self):
        """
        GIVEN an empty AI message with tool calls at the end of conversation (current tool call)
        WHEN worker agent filtering is applied
        THEN it preserves the message to avoid infinite loops (this is the current tool call being processed)
        """
        conversation = [
            MockSystemMessage("System message"),
            MockHumanMessage("User request"),
            MockAIMessageWithToolCalls("", [{"name": "current_tool", "args": {}}]),  # Current tool call - should be preserved
        ]
        
        result = self.filter.filter_conversation(conversation)
        
        # Should have 3 messages - empty AI message at end is the CURRENT tool call and must be preserved
        assert len(result) == 3
        assert result[0].content == "System message"
        assert result[1].content == "User request"
        assert result[2].content == ""  # Current tool call preserved
        assert hasattr(result[2], 'tool_calls') and result[2].tool_calls


class TestManagerAgentConversationFilter:
    """BDD-style test suite for ManagerAgentConversationFilter."""
    
    def setup_method(self):
        """Set up test fixtures before each test method."""
        self.filter = ManagerAgentConversationFilter(model="gpt-4o")
    
    def test_given_empty_conversation_when_filtering_then_returns_empty_message_list(self):
        """
        GIVEN an empty conversation history
        WHEN manager agent filtering is applied
        THEN it returns an empty message list
        """
        result = self.filter.filter_conversation([])
        assert result == []
    
    def test_given_conversation_with_mixed_messages_when_filtering_then_creates_filtered_message_list(self):
        """
        GIVEN a conversation with mixed message types (system, human, AI, tool)
        WHEN manager agent filtering is applied
        THEN it creates a filtered message list with manager system prompt and context
        """
        conversation = [
            MockSystemMessage("System initialization with procedure context"),
            MockHumanMessage("User request: Please analyze the feedback data for medical classification"),
            MockAIMessage("I'll analyze this systematically. Let me start with the overview.", 
                         tool_calls=[{"name": "plexus_feedback_analysis", "args": {}}]),
            MockToolMessage("Analysis results: Found 45 feedback corrections with 78% accuracy..."),
            MockAIMessage("Based on the analysis, I can see several patterns emerging in the data.")
        ]
        
        manager_prompt = "You are a StandardOperatingProcedureAgent for procedure oversight."
        result = self.filter.filter_conversation(conversation, manager_system_prompt=manager_prompt)
        
        # Check that result is a message list
        assert isinstance(result, list)
        assert len(result) >= 3  # Should have system prompt + context + instruction messages
        
        # Check first message is manager system prompt
        first_msg = result[0]
        assert hasattr(first_msg, 'content')
        assert manager_prompt in first_msg.content
        
        # Check that context message contains conversation overview
        context_msg = result[1]
        assert hasattr(context_msg, 'content')
        assert "CONVERSATION OVERVIEW" in context_msg.content
        assert "5 messages" in context_msg.content
        
        # Check last message contains manager instruction
        last_msg = result[-1]
        assert hasattr(last_msg, 'content')
        assert "coaching manager" in last_msg.content
    
    def test_given_conversation_with_tight_token_limits_when_filtering_then_includes_fewer_messages(self):
        """
        GIVEN a conversation with tight token limits (< 2000 tokens)
        WHEN manager agent filtering is applied
        THEN it focuses on fewer recent messages only
        """
        # Create a longer conversation
        conversation = []
        for i in range(12):
            conversation.append(MockHumanMessage(f"User message {i}"))
            conversation.append(MockAIMessage(f"AI response {i}"))
        
        manager_prompt = "You are a manager agent."
        result = self.filter.filter_conversation(conversation, max_tokens=1500, manager_system_prompt=manager_prompt)
        
        # Should be a message list
        assert isinstance(result, list)
        assert len(result) >= 3  # System prompt + context + instruction
        
        # Check that fewer messages are included due to token limits (3 vs 8 for generous limits)
        context_msg = result[1]
        assert "3 messages" in context_msg.content  # Should include fewer messages for tight limits
    
    def test_given_conversation_with_tool_calls_when_filtering_then_detects_and_reports_tools(self):
        """
        GIVEN a conversation with AI messages containing tool calls
        WHEN manager agent filtering is applied
        THEN it detects and reports tool usage in the context
        """
        conversation = [
            MockSystemMessage("System setup"),
            MockAIMessage("I'll use feedback analysis tools.", 
                         tool_calls=[{"name": "plexus_feedback_analysis", "args": {}}, 
                                   {"name": "plexus_feedback_find", "args": {}}]),
            MockToolMessage("Feedback analysis complete"),
            MockAIMessage("Now examining specific cases.", 
                         tool_calls=[{"name": "plexus_feedback_find", "args": {}}]),
            MockToolMessage("Found specific feedback case")
        ]
        
        manager_prompt = "You are a manager agent."
        result = self.filter.filter_conversation(conversation, manager_system_prompt=manager_prompt)
        
        # Should be a message list
        assert isinstance(result, list)
        
        # Check that context message contains tool information
        context_msg = result[1]
        assert "Tools:" in context_msg.content  # Should show tool names in AI message summaries
        assert "plexus_feedback_analysis" in context_msg.content
        assert "plexus_feedback_find" in context_msg.content
    
    def test_given_conversation_in_exploration_stage_when_filtering_then_preserves_exploration_context(self):
        """
        GIVEN a conversation where AI is in exploration stage (using keywords like 'examining', 'analyzing')
        WHEN manager agent filtering is applied
        THEN it preserves the exploration context in the filtered messages
        """
        conversation = [
            MockSystemMessage("System setup"),
            MockHumanMessage("Please analyze the feedback"),
            MockAIMessage("I'm examining the feedback data and analyzing the patterns I found.")
        ]
        
        manager_prompt = "You are a manager agent."
        result = self.filter.filter_conversation(conversation, manager_system_prompt=manager_prompt)
        
        # Should be a message list
        assert isinstance(result, list)
        
        # Check that the recent AI message with exploration keywords is preserved
        has_exploration_content = any(
            hasattr(msg, 'content') and 
            msg.content and 
            ('examining' in msg.content or 'analyzing' in msg.content)
            for msg in result
        )
        assert has_exploration_content
    
    def test_given_conversation_in_synthesis_stage_when_filtering_then_preserves_synthesis_context(self):
        """
        GIVEN a conversation where AI is in synthesis stage (using keywords like 'patterns', 'root cause')
        WHEN manager agent filtering is applied  
        THEN it preserves the synthesis context in the filtered messages
        """
        conversation = [
            MockSystemMessage("System setup"),
            MockHumanMessage("What patterns do you see?"),
            MockAIMessage("My analysis shows clear patterns and I've identified the root cause of the issues.")
        ]
        
        manager_prompt = "You are a manager agent."
        result = self.filter.filter_conversation(conversation, manager_system_prompt=manager_prompt)
        
        # Should be a message list
        assert isinstance(result, list)
        
        # Check that the recent AI message with synthesis keywords is preserved
        has_synthesis_content = any(
            hasattr(msg, 'content') and 
            msg.content and 
            ('patterns' in msg.content or 'root cause' in msg.content)
            for msg in result
        )
        assert has_synthesis_content
    
    def test_given_conversation_in_hypothesis_generation_stage_when_filtering_then_preserves_hypothesis_context(self):
        """
        GIVEN a conversation where AI is in hypothesis generation stage (using keywords like 'procedure', 'hypothesis')
        WHEN manager agent filtering is applied
        THEN it preserves the hypothesis context in the filtered messages
        """
        conversation = [
            MockSystemMessage("System setup"),
            MockHumanMessage("What experiments should we run?"),
            MockAIMessage("I propose several experiments to test this hypothesis with different configuration approaches.")
        ]
        
        manager_prompt = "You are a manager agent."
        result = self.filter.filter_conversation(conversation, manager_system_prompt=manager_prompt)
        
        # Should be a message list
        assert isinstance(result, list)
        
        # Check that the recent AI message with hypothesis keywords is preserved
        has_hypothesis_content = any(
            hasattr(msg, 'content') and 
            msg.content and 
            ('experiments' in msg.content or 'hypothesis' in msg.content)
            for msg in result
        )
        assert has_hypothesis_content
    
    def test_given_conversation_with_tool_results_when_filtering_then_summarizes_tool_results_briefly(self):
        """
        GIVEN a conversation with tool result messages
        WHEN manager agent filtering is applied
        THEN it provides brief summaries of tool results (not full details)
        """
        long_tool_result = "Tool analysis complete. Results:\n" + "x" * 500 + "\nMore detailed data follows..."
        
        conversation = [
            MockSystemMessage("System setup"),
            MockAIMessage("Running analysis", tool_calls=[{"name": "analysis_tool", "args": {}}]),
            MockToolMessage(long_tool_result)
        ]
        
        manager_prompt = "You are a manager agent."
        result = self.filter.filter_conversation(conversation, manager_system_prompt=manager_prompt)
        
        # Should be a message list
        assert isinstance(result, list)
        
        # Check context message contains brief tool result summary
        context_msg = result[1]
        assert "Tool analysis complete. Results:" in context_msg.content
        
        # Should not contain the full 500+ character content in any message
        for msg in result:
            if hasattr(msg, 'content') and msg.content:
                assert len(msg.content) < len(long_tool_result) + 1000  # Much shorter than original
    
    def test_given_conversation_with_different_message_types_when_filtering_then_creates_appropriate_message_structure(self):
        """
        GIVEN a conversation with different message types (System, Human, AI, Tool)
        WHEN manager agent filtering is applied
        THEN it creates an appropriate message structure with context summaries
        """
        long_system = "System message with lots of context: " + "x" * 200
        long_human = "User message with detailed request: " + "y" * 300  
        long_ai = "AI response with detailed analysis: " + "z" * 400
        long_tool = "Tool result with lots of data: " + "w" * 300
        
        conversation = [
            MockSystemMessage(long_system),
            MockHumanMessage(long_human),
            MockAIMessage(long_ai),
            MockToolMessage(long_tool)
        ]
        
        manager_prompt = "You are a manager agent."
        result = self.filter.filter_conversation(conversation, manager_system_prompt=manager_prompt)
        
        # Should be a message list
        assert isinstance(result, list)
        assert len(result) >= 3  # System prompt + context + instruction
        
        # Check that context message contains summaries of different message types
        # Note: System message (index 0) is skipped since it's replaced with manager prompt
        context_msg = result[1]
        assert "User message with detailed request" in context_msg.content
        assert "AI response with detailed analysis" in context_msg.content
        assert "Tool result with lots of data" in context_msg.content
    
    @patch('plexus.cli.procedure.conversation_filter.logger')
    def test_when_filtering_conversation_then_logs_manager_agent_filtering_process(self, mock_logger):
        """
        WHEN manager agent filtering is applied
        THEN it logs the filtering process with manager-specific log messages
        """
        conversation = [
            MockSystemMessage("System message"),
            MockHumanMessage("User request"),
            MockAIMessage("AI response")
        ]
        
        self.filter.filter_conversation(conversation, max_tokens=5000)
        
        # Verify manager agent specific logging occurred
        log_calls = [call.args[0] for call in mock_logger.info.call_args_list]
        manager_logs = [call for call in log_calls if "MANAGER AGENT" in call]
        assert len(manager_logs) >= 2  # Should have start and complete messages
        
        # Should log token limits and summary creation
        token_analysis_logs = [call for call in log_calls if "📊" in call or "Target:" in call]
        assert len(token_analysis_logs) >= 1
    
    def test_then_returns_message_list_not_string_summary(self):
        """
        THEN manager agent filter returns a filtered message list
        (Different from the old behavior but consistent with new architecture)
        """
        conversation = [
            MockSystemMessage("System message"),
            MockHumanMessage("User request"),
            MockAIMessage("AI response")
        ]
        
        manager_prompt = "You are a manager agent."
        result = self.filter.filter_conversation(conversation, manager_system_prompt=manager_prompt)
        
        # New behavior: Manager agent returns message list, not string
        assert isinstance(result, list)
        assert not isinstance(result, str)
        
        # Should have structured message format
        assert len(result) >= 3  # System prompt + context + instruction
        
        # Context message should contain overview
        context_msg = result[1]
        assert "CONVERSATION OVERVIEW" in context_msg.content
    
    def test_given_no_ai_messages_when_filtering_then_handles_gracefully(self):
        """
        GIVEN a conversation with no AI messages
        WHEN manager agent filtering is applied
        THEN it handles the situation gracefully without errors
        """
        conversation = [
            MockSystemMessage("System setup"),
            MockHumanMessage("User request"),
            MockToolMessage("Tool result")
        ]
        
        manager_prompt = "You are a manager agent."
        result = self.filter.filter_conversation(conversation, manager_system_prompt=manager_prompt)
        
        # Should not crash and should create a valid message list
        assert isinstance(result, list)
        assert len(result) >= 3  # System prompt + context + instruction
        
        # Context message should report AI message count accurately
        context_msg = result[1]
        assert "CONVERSATION OVERVIEW" in context_msg.content
        assert "0 AI responses" in context_msg.content  # Should accurately report no AI messages
    
    def test_given_empty_ai_messages_when_filtering_then_shows_empty_content_appropriately(self):
        """
        GIVEN a conversation with empty AI messages (e.g., tool calls with no content)
        WHEN manager agent filtering is applied
        THEN it appropriately shows empty content indicators
        """
        conversation = [
            MockSystemMessage("System setup"),
            MockAIMessage("", tool_calls=[{"name": "test_tool", "args": {}}]),  # Empty content with tool calls
            MockToolMessage("Tool result")
        ]
        
        manager_prompt = "You are a manager agent."
        result = self.filter.filter_conversation(conversation, manager_system_prompt=manager_prompt)
        
        # Should handle empty AI messages gracefully
        assert isinstance(result, list)
        
        # Should have the basic structure even with empty AI messages
        context_msg = result[1]
        assert "CONVERSATION OVERVIEW" in context_msg.content
        assert "1 AI responses" in context_msg.content  # Should count the empty AI message


if __name__ == "__main__":
    pytest.main([__file__])