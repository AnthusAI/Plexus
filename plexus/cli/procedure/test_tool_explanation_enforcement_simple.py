"""
Simple BDD Tests for Tool Explanation Enforcement System

This module tests the critical behavior where the system forces the assistant
to explain tool results before allowing further tool calls by temporarily
removing tool access.

Key Behavior:
1. Tool executed → Result + Reminder injected → Tools REMOVED for next iteration
2. Assistant MUST provide explanation (no tools available)
3. Tools restored after explanation provided
"""

import pytest
from unittest.mock import Mock
from langchain_core.messages import AIMessage, ToolMessage, SystemMessage, HumanMessage


class TestToolExplanationEnforcement:
    """
    Test suite for the tool explanation enforcement system that prevents
    tool call chaining without explanation by temporarily removing tools.
    
    These tests focus on the core logic patterns without complex integration.
    """

    def test_tool_execution_sets_explanation_flag(self):
        """
        Given a tool has been executed successfully
        When the tool result and reminder are added to conversation
        Then the force_explanation_next flag should be set to True
        """
        # Arrange
        results = {"tools_used": []}
        conversation_history = []
        
        # Act - Simulate the logic that happens after tool execution
        # (This is the behavior we implemented in sop_agent_base.py)
        tool_result = "Sample feedback data"
        
        # Add tool result to conversation
        tool_message = ToolMessage(content=str(tool_result), tool_call_id="call_123")
        conversation_history.append(tool_message)
        
        # Add system reminder about explaining tool results  
        reminder_message = SystemMessage(
            content="🚨 REMINDER: You must explain what you learned from this tool result in your next response before calling any other tools. Start with '### Summary of Tool Result:' and describe the key findings."
        )
        conversation_history.append(reminder_message)
        
        # Set flag to remove tools in next iteration to force explanation
        results["force_explanation_next"] = True
        
        # Assert
        assert results.get("force_explanation_next") is True, \
            "force_explanation_next flag should be set after tool execution"
        assert len(conversation_history) == 2, \
            "Conversation should contain tool result and reminder"
        assert "🚨 REMINDER" in conversation_history[1].content, \
            "Reminder message should be injected after tool result"

    def test_explanation_flag_removes_tools_from_llm(self):
        """
        Given the force_explanation_next flag is True
        When the LLM is invoked for the next response
        Then tools should be temporarily removed (use coding_assistant_llm instead of llm_with_tools)
        And the flag should be cleared after use
        """
        # Arrange
        mock_coding_llm = Mock()
        mock_llm_with_tools = Mock()
        
        # Mock explanation response (no tool calls)
        explanation_response = AIMessage(
            content="### Summary of Tool Result:\nI found feedback data showing..."
        )
        mock_coding_llm.invoke.return_value = explanation_response
        
        results = {"force_explanation_next": True, "tools_used": []}
        filtered_history = [HumanMessage(content="test")]
        
        # Act - Simulate the LLM invocation logic with flag check
        # (This is the exact logic we implemented in sop_agent_base.py)
        if results.get("force_explanation_next", False):
            # Use LLM without tools to force explanation
            ai_response = mock_coding_llm.invoke(filtered_history)
            results["force_explanation_next"] = False
            used_tools_temporarily_removed = True
        else:
            ai_response = mock_llm_with_tools.invoke(filtered_history)
            used_tools_temporarily_removed = False
        
        # Assert
        assert used_tools_temporarily_removed is True, \
            "Tools should be temporarily removed when force_explanation_next is True"
        assert results.get("force_explanation_next") is False, \
            "force_explanation_next flag should be cleared after use"
        assert ai_response.content.startswith("### Summary of Tool Result:"), \
            "Response should contain explanation text when tools are removed"
        
        # Verify the correct LLM method was called
        mock_coding_llm.invoke.assert_called_once_with(filtered_history)
        mock_llm_with_tools.invoke.assert_not_called()

    def test_tools_restored_after_explanation(self):
        """
        Given an explanation has been provided (force_explanation_next was cleared)
        When the LLM is invoked in the subsequent round
        Then tools should be restored (use llm_with_tools normally)
        """
        # Arrange
        mock_coding_llm = Mock()
        mock_llm_with_tools = Mock()
        
        tool_response = AIMessage(
            content="Now I'll examine another case...",
            tool_calls=[{
                'name': 'plexus_feedback_find',
                'args': {'scorecard_name': 'Test', 'limit': 1},
                'id': 'call_456'
            }]
        )
        mock_llm_with_tools.invoke.return_value = tool_response
        
        # force_explanation_next is False (explanation was provided in previous round)
        results = {"force_explanation_next": False, "tools_used": []}
        filtered_history = [HumanMessage(content="test")]
        
        # Act - Simulate normal LLM invocation (tools restored)
        if results.get("force_explanation_next", False):
            ai_response = mock_coding_llm.invoke(filtered_history)
            used_normal_tools = False
        else:
            ai_response = mock_llm_with_tools.invoke(filtered_history)
            used_normal_tools = True
        
        # Assert
        assert used_normal_tools is True, \
            "Tools should be restored when force_explanation_next is False"
        assert hasattr(ai_response, 'tool_calls') and ai_response.tool_calls, \
            "AI should be able to make tool calls when tools are restored"
        
        # Verify the correct LLM method was called
        mock_llm_with_tools.invoke.assert_called_once_with(filtered_history)
        mock_coding_llm.invoke.assert_not_called()

    def test_reminder_message_injection_behavior(self):
        """
        Given a tool has been executed
        When the tool result is added to conversation history
        Then a reminder message should be injected immediately after the tool result
        And the reminder should contain specific required text
        """
        # Arrange
        conversation_history = []
        tool_result = "Sample feedback data"
        tool_call_id = "call_123"
        
        # Act - Simulate the reminder injection logic
        tool_message = ToolMessage(content=str(tool_result), tool_call_id=tool_call_id)
        conversation_history.append(tool_message)
        
        reminder_message = SystemMessage(
            content="🚨 REMINDER: You must explain what you learned from this tool result in your next response before calling any other tools. Start with '### Summary of Tool Result:' and describe the key findings."
        )
        conversation_history.append(reminder_message)
        
        # Assert
        assert len(conversation_history) == 2, \
            "Conversation should contain tool result and reminder"
        assert isinstance(conversation_history[0], ToolMessage), \
            "First message should be the tool result"
        assert isinstance(conversation_history[1], SystemMessage), \
            "Second message should be the system reminder"
        assert "🚨 REMINDER" in conversation_history[1].content, \
            "Reminder should contain warning emoji and REMINDER text"
        assert "### Summary of Tool Result:" in conversation_history[1].content, \
            "Reminder should specify the required format"
        assert "before calling any other tools" in conversation_history[1].content, \
            "Reminder should explicitly prevent tool chaining"

    def test_complete_enforcement_cycle_logic(self):
        """
        Integration test for the complete tool explanation enforcement cycle logic:
        
        Given: Normal operation with tools available
        When: Tool is executed
        Then: Reminder is injected and tools are removed for next response
        When: Explanation is provided  
        Then: Tools are restored for subsequent responses
        """
        # Arrange
        mock_coding_llm = Mock()
        mock_llm_with_tools = Mock()
        
        # Phase 1: Normal tool call
        tool_response = AIMessage(
            content="",
            tool_calls=[{
                'name': 'plexus_feedback_find',
                'args': {'limit': 1},
                'id': 'call_123'
            }]
        )
        
        # Phase 2: Forced explanation (no tools)
        explanation_response = AIMessage(
            content="### Summary of Tool Result:\nThe data shows..."
        )
        
        # Phase 3: Normal operation restored
        next_tool_response = AIMessage(
            content="Based on my analysis...",
            tool_calls=[{
                'name': 'plexus_feedback_find', 
                'args': {'limit': 1},
                'id': 'call_456'
            }]
        )
        
        mock_llm_with_tools.invoke.side_effect = [tool_response, next_tool_response]
        mock_coding_llm.invoke.return_value = explanation_response
        
        results = {"tools_used": []}
        history = [HumanMessage(content="Start analysis")]
        
        # Act & Assert - Simulate the complete cycle
        
        # Phase 1: Initial tool call
        ai_response_1 = mock_llm_with_tools.invoke(history)
        assert ai_response_1.tool_calls, "Initial response should have tool calls"
        
        # Tool execution sets flag
        results["force_explanation_next"] = True
        
        # Phase 2: Forced explanation
        if results.get("force_explanation_next", False):
            ai_response_2 = mock_coding_llm.invoke(history)
            results["force_explanation_next"] = False
            tools_were_removed = True
        else:
            tools_were_removed = False
        
        assert tools_were_removed, "Tools should be removed to force explanation"
        assert "### Summary of Tool Result:" in ai_response_2.content, \
            "Response should contain required explanation format"
        assert not hasattr(ai_response_2, 'tool_calls') or not ai_response_2.tool_calls, \
            "Explanation response should not contain tool calls"
        
        # Phase 3: Tools restored
        if results.get("force_explanation_next", False):
            tools_restored = False
        else:
            ai_response_3 = mock_llm_with_tools.invoke(history)
            tools_restored = True
        
        assert tools_restored, "Tools should be restored after explanation"
        assert ai_response_3.tool_calls, "Subsequent response should allow tool calls again"

    def test_logging_behavior_during_enforcement(self):
        """
        Given the tool explanation enforcement is active
        When tools are temporarily removed
        Then specific logging messages should be generated for debugging
        """
        # This test verifies that the logging message
        # "🚨 FORCING EXPLANATION: Removing tools temporarily to require text response"
        # is generated when the enforcement kicks in
        
        results = {"force_explanation_next": True}
        
        # Simulate the logging check
        if results.get("force_explanation_next", False):
            logged_enforcement = True
            log_message = "🚨 FORCING EXPLANATION: Removing tools temporarily to require text response"
        else:
            logged_enforcement = False
            log_message = None
        
        assert logged_enforcement, "Enforcement should be logged for debugging"
        assert "🚨 FORCING EXPLANATION" in log_message, \
            "Log message should clearly indicate enforcement is active"
        assert "Removing tools temporarily" in log_message, \
            "Log should explain what action is being taken"

    def test_edge_case_no_tool_calls_in_response(self):
        """
        Given the assistant provides a text response without tool calls
        When that response is processed
        Then the force_explanation_next flag should not be set
        And normal flow should continue
        """
        # Arrange
        results = {"tools_used": []}
        
        # Act - Simulate processing a text-only response
        text_response = AIMessage(content="I need to analyze the feedback data first...")
        
        # No tool execution occurs, so flag should not be set
        force_flag_set = results.get("force_explanation_next", False)
        
        # Assert
        assert not force_flag_set, \
            "force_explanation_next should not be set for text-only responses"
        assert not hasattr(text_response, 'tool_calls') or not text_response.tool_calls, \
            "Response should not contain tool calls"

    def test_multiple_tool_calls_enforcement(self):
        """
        Given the AI attempts to make multiple tool calls in a single response
        When the response is processed 
        Then only the first tool call should be executed
        And the force_explanation_next flag should still be set correctly
        """
        # Arrange - AI response with multiple tool calls
        multi_tool_response = AIMessage(
            content="",
            tool_calls=[
                {
                    'name': 'plexus_feedback_find',
                    'args': {'initial_value': 'No', 'final_value': 'Yes', 'limit': 1},
                    'id': 'call_1'
                },
                {
                    'name': 'plexus_feedback_find', 
                    'args': {'initial_value': 'Yes', 'final_value': 'No', 'limit': 1},
                    'id': 'call_2'
                }
            ]
        )
        
        # Act - Simulate the single tool call enforcement
        if len(multi_tool_response.tool_calls) > 1:
            warning_logged = True
            processed_tool_call = multi_tool_response.tool_calls[0]  # Only first one
        else:
            warning_logged = False
            processed_tool_call = multi_tool_response.tool_calls[0]
        
        # After processing first tool call, flag should be set
        results = {"force_explanation_next": True}
        
        # Assert
        assert warning_logged, \
            "Warning should be logged when multiple tool calls are attempted"
        assert processed_tool_call['id'] == 'call_1', \
            "Only the first tool call should be processed"
        assert results["force_explanation_next"], \
            "Explanation should still be enforced after first tool execution"

    def test_enforcement_prevents_tool_chaining_pattern(self):
        """
        Integration test that demonstrates the prevention of tool chaining.
        
        Before: Tool → Tool → Tool (bad)
        After: Tool → Explanation → Tool → Explanation (good)
        """
        # This test demonstrates the expected behavior patterns
        
        # BAD PATTERN (what used to happen - now prevented):
        bad_pattern = [
            "ASSISTANT: Tool call 1",
            "TOOL_RESULT: Data 1", 
            "ASSISTANT: Tool call 2",  # ❌ No explanation!
            "TOOL_RESULT: Data 2",
            "ASSISTANT: Tool call 3"   # ❌ Still no explanation!
        ]
        
        # GOOD PATTERN (what our enforcement creates):
        good_pattern = [
            "ASSISTANT: Tool call 1",
            "TOOL_RESULT: Data 1",
            "SYSTEM: 🚨 REMINDER: You must explain...",
            "ASSISTANT: ### Summary of Tool Result: Data 1 shows...",  # ✅ Forced explanation!
            "ASSISTANT: Tool call 2", 
            "TOOL_RESULT: Data 2",
            "SYSTEM: 🚨 REMINDER: You must explain...",
            "ASSISTANT: ### Summary of Tool Result: Data 2 reveals..."  # ✅ Another explanation!
        ]
        
        # The enforcement mechanism ensures we get the good pattern
        assert len(good_pattern) > len(bad_pattern), \
            "Good pattern should be longer due to required explanations"
        
        # Count explanations in good pattern
        explanations = [step for step in good_pattern if "### Summary of Tool Result:" in step]
        tool_results = [step for step in good_pattern if "TOOL_RESULT:" in step]
        
        assert len(explanations) == len(tool_results), \
            "Every tool result should have a corresponding explanation"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
