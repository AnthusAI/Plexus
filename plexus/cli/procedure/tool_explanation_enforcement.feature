# Tool Explanation Enforcement System
# 
# This feature ensures that the AI assistant cannot chain tool calls without 
# providing explanations of the results. The system enforces this by temporarily
# removing tool access after each tool execution until an explanation is provided.

Feature: Tool Explanation Enforcement
  As a system operator
  I want to ensure AI assistants explain tool results before making additional tool calls
  So that tool outputs are always summarized and not lost in conversation filtering

  Background:
    Given an AI assistant with access to tools like "plexus_feedback_find"
    And a conversation history tracking system
    And tool explanation enforcement is enabled

  Scenario: Tool execution triggers explanation enforcement
    Given the assistant has made a tool call to "plexus_feedback_find"
    When the tool execution completes successfully
    Then a system reminder message should be injected into conversation history
    And the reminder should contain "🚨 REMINDER: You must explain what you learned"
    And the reminder should specify the required format "### Summary of Tool Result:"
    And a "force_explanation_next" flag should be set to True

  Scenario: Tools are temporarily removed to force explanation
    Given a tool has been executed and the "force_explanation_next" flag is True
    When the AI is prompted for its next response
    Then the system should invoke the LLM without any tools available
    And the system should log "🚨 FORCING EXPLANATION: Removing tools temporarily"
    And the "force_explanation_next" flag should be cleared after use

  Scenario: AI provides required explanation when tools are removed
    Given tools have been temporarily removed to force explanation
    When the AI generates its response
    Then the response should contain explanatory text only (no tool calls possible)
    And the response should ideally start with "### Summary of Tool Result:"
    And the response should describe key findings from the previous tool execution
    And no tool calls should be present in the response

  Scenario: Tools are restored after explanation is provided
    Given an explanation has been provided in the previous round
    And the "force_explanation_next" flag is False
    When the AI is prompted for its next response  
    Then the system should invoke the LLM with full tool access restored
    And the AI should be able to make tool calls normally if needed
    And the cycle can repeat if another tool is executed

  Scenario: Multiple tool calls are prevented - only first is processed
    Given the AI attempts to make multiple tool calls in a single response
    When the response is processed by the system
    Then only the first tool call should be executed
    And a warning should be logged about multiple tool call attempts
    And the explanation enforcement should still trigger normally
    And subsequent tool calls should be ignored until explanation is provided

  Scenario: Text-only responses do not trigger enforcement
    Given the AI provides a response with only text content
    When the response is processed
    Then no tool execution occurs
    And no "force_explanation_next" flag should be set
    And the normal conversation flow should continue
    And tools should remain available for the next response

  Scenario: Complete enforcement cycle
    Given normal operation with tools available
    When the AI makes a tool call to analyze feedback
    Then the tool executes and returns data
    And a reminder is injected: "🚨 REMINDER: You must explain..."
    And the "force_explanation_next" flag is set

    When the AI is prompted for the next response
    Then tools are temporarily removed
    And the system logs "🚨 FORCING EXPLANATION"
    And the AI provides explanation text only

    When the AI is prompted again after the explanation
    Then tools are restored to normal access
    And the AI can make new tool calls if needed
    And the cycle can repeat for each new tool execution

  Scenario: Enforcement prevents tool call chaining
    Given the assistant historically would chain multiple tool calls
    When tool explanation enforcement is active
    Then the pattern becomes: Tool → Explanation → Tool → Explanation
    And the pattern "Tool → Tool → Tool" is impossible
    And each tool result is guaranteed to be explained before proceeding

  Scenario: Logging provides clear debugging information
    Given tool explanation enforcement is active
    When tools are temporarily removed
    Then the log should contain "🚨 FORCING EXPLANATION: Removing tools temporarily to require text response"
    And when tools are restored, normal tool execution logging should resume
    And the enforcement status should be clearly visible in system logs

  Scenario: Integration with conversation filtering
    Given conversation history is filtered to manage token limits
    When tool results are lost due to filtering
    Then the explanation text (generated before filtering) preserves key information
    And the explanation serves as a summary that survives filtering
    And important findings are not lost when tool results are removed from history

# Expected Behavior Patterns:

# ✅ CORRECT (Enforced):
# [1] ASSISTANT: Tool call to plexus_feedback_find
# [2] TOOL_RESULT: {...feedback data...}
# [3] SYSTEM: 🚨 REMINDER: You must explain what you learned...
# [4] ASSISTANT: ### Summary of Tool Result: I found feedback showing...
# [5] ASSISTANT: Tool call to plexus_feedback_find (different parameters)
# [6] TOOL_RESULT: {...more feedback data...}
# [7] SYSTEM: 🚨 REMINDER: You must explain what you learned...
# [8] ASSISTANT: ### Summary of Tool Result: This case reveals...

# ❌ PREVENTED (What used to happen):
# [1] ASSISTANT: Tool call to plexus_feedback_find
# [2] TOOL_RESULT: {...feedback data...}
# [3] ASSISTANT: Tool call to plexus_feedback_find (immediately, no explanation)
# [4] TOOL_RESULT: {...more feedback data...}
# [5] ASSISTANT: Tool call to create_experiment_node (still no explanation)

# 🔧 ENFORCEMENT MECHANISM:
# - After tool execution: Inject reminder + Set force_explanation_next = True
# - Next LLM call: Use coding_assistant_llm (no tools) instead of llm_with_tools
# - After explanation: Clear force_explanation_next = False, restore tools
# - Result: Impossible to chain tools without explanation
