# SOP Agent Coin Flip Experiment Scenario
#
# This feature demonstrates the complete SOP (Standard Operating Procedure) Agent
# functionality using a simple, testable coin flip experiment scenario.
#
# The scenario exercises all core SOP agent capabilities:
# - Custom procedure definitions with specific tool subsets
# - Worker agent tool access management and enforcement
# - Tool explanation enforcement (no tool chaining without explanations)
# - Manager agent coaching and guidance
# - Stop tool functionality for procedure completion
# - Chat recording and session management
# - Configurable prompts and completion criteria

Feature: SOP Agent Coin Flip Experiment
  As a system designer
  I want to demonstrate SOP agent functionality with a simple coin flip experiment
  So that all core features are tested and the architecture is validated

  Background:
    Given an SOP agent configured for coin flip experiments
    And the agent has access to specific coin flip tools only
    And tool explanation enforcement is enabled
    And manager coaching is active

  # =============================================================================
  # SCENARIO 1: CUSTOM PROCEDURE DEFINITION
  # =============================================================================

  Scenario: Custom procedure defines experiment-specific configuration
    Given a coin flip procedure definition
    When the procedure is initialized
    Then it should provide exactly 4 allowed tools
    And the tools should be ["coin_flip", "data_logging", "accuracy_calculator", "stop_procedure"]
    And it should not include other experimental tools like "plexus_feedback_find"
    And it should provide task-specific system prompts mentioning coin flipping
    And it should provide task-specific user prompts with the experiment steps

  Scenario: Procedure definition provides contextual manager guidance
    Given a coin flip procedure definition
    When the manager needs to provide guidance at different workflow stages
    Then it should ask about starting when no tools used: "Have you started flipping the coin yet?"
    And it should track progress when some flips done: "You've flipped X times. How many more?"
    And it should prompt for logging when flips complete: "Have you logged all your results?"
    And it should suggest analysis when data logged: "Have you calculated the accuracy?"
    And it should guide toward completion when analysis done: "Are you ready to summarize and stop?"

  # =============================================================================
  # SCENARIO 2: TOOL ACCESS MANAGEMENT
  # =============================================================================

  Scenario: Worker agent has access only to procedure-specific tools
    Given a worker agent in a coin flip experiment
    When the agent attempts to use tools
    Then it should have access to "coin_flip" tool
    And it should have access to "data_logging" tool
    And it should have access to "accuracy_calculator" tool
    And it should have access to "stop_procedure" tool
    But it should not have access to "plexus_feedback_find" tool
    And it should not have access to "create_experiment_node" tool

  Scenario: SOP agent filters available tools based on procedure definition
    Given an SOP agent with a custom procedure definition
    When the agent initializes tool access for the worker
    Then only tools listed in procedure.get_allowed_tools() should be available
    And other MCP tools should be filtered out
    And the worker should receive binding only for allowed tools

  # =============================================================================
  # SCENARIO 3: TOOL EXPLANATION ENFORCEMENT
  # =============================================================================

  Scenario: Worker must explain tool results before making another tool call
    Given a worker agent conducting coin flip experiment
    When the agent calls the "coin_flip" tool
    Then a tool result should be returned (e.g., "heads")
    And a system reminder should be injected: "🚨 REMINDER: You must explain what you learned"
    And the force_explanation_next flag should be set to True

    When the agent is prompted for the next response
    Then tools should be temporarily removed from the LLM
    And the system should log "🚨 FORCING EXPLANATION: Removing tools temporarily"
    And the agent should be forced to provide explanatory text only
    And the response should ideally start with "### Summary of Tool Result:"

    When the agent provides the explanation
    Then the force_explanation_next flag should be cleared
    And tools should be restored for subsequent responses
    And the agent should be able to make the next tool call

  Scenario: System prevents tool call chaining without explanations
    Given a worker agent that attempts to chain multiple tool calls
    When the agent generates a response with multiple tool calls
    Then only the first tool call should be executed
    And subsequent tool calls should be ignored
    And a warning should be logged about multiple tool call attempts
    And the explanation enforcement should still trigger for the executed tool

  # =============================================================================
  # SCENARIO 4: COMPLETE WORKFLOW ORCHESTRATION
  # =============================================================================

  Scenario: Complete coin flip experiment workflow
    Given an SOP agent configured for coin flip experiments
    When executing the complete experimental procedure

    # Round 1: First coin flip
    Then the worker should call "coin_flip" tool
    And the system should enforce explanation: "### Summary: First flip was heads"
    
    # Round 2: Log first result
    Then the worker should call "data_logging" tool with the result
    And the system should enforce explanation: "### Summary: First result logged"
    
    # Round 3: Second coin flip
    Then the worker should call "coin_flip" tool again
    And the system should enforce explanation: "### Summary: Second flip was tails"
    
    # Round 4: Log second result
    Then the worker should call "data_logging" tool with second result
    And the system should enforce explanation: "### Summary: Second result logged"
    
    # Round 5: Third coin flip
    Then the worker should call "coin_flip" tool a third time
    And the system should enforce explanation: "### Summary: Third flip was heads"
    
    # Round 6: Log third result
    Then the worker should call "data_logging" tool with third result
    And the system should enforce explanation: "### Summary: All results logged"
    
    # Round 7: Calculate accuracy
    Then the worker should call "accuracy_calculator" tool
    And the system should enforce explanation: "### Summary: Accuracy calculated"
    
    # Round 8: Complete procedure
    Then the worker should call "stop_procedure" tool
    And the procedure should terminate with success status

  # =============================================================================
  # SCENARIO 5: MANAGER COACHING BEHAVIOR
  # =============================================================================

  Scenario: Manager provides coaching guidance throughout experiment
    Given an SOP agent with manager coaching enabled
    When the worker agent progresses through the coin flip experiment

    # Early stage coaching
    When no tools have been used yet
    Then the manager should ask: "Have you started flipping the coin yet?"
    
    # Progress tracking coaching
    When 2 coin flips have been completed
    Then the manager should ask: "You've flipped 2 times. How many more flips do you need?"
    
    # Data logging coaching
    When 3 flips are done but no logging
    Then the manager should ask: "Have you logged all your coin flip results?"
    
    # Analysis coaching
    When all data is logged but no analysis
    Then the manager should ask: "Have you calculated the accuracy of your experiment?"
    
    # Completion coaching
    When all experiment steps are complete
    Then the manager should ask: "Are you ready to summarize and stop?"

  # =============================================================================
  # SCENARIO 6: STOP TOOL FUNCTIONALITY
  # =============================================================================

  Scenario: Worker agent can signal procedure completion
    Given a worker agent that has completed all experiment steps
    When the agent calls the "stop_procedure" tool
    Then the tool should accept parameters like {"reason": "Experiment complete", "success": true}
    And the procedure execution should terminate
    And the stop_requested flag should be set to True
    And the stop_reason should be recorded
    And the completion summary should reflect the work done

  Scenario: Procedure respects stop requests and safety limits
    Given a coin flip procedure definition
    When checking continuation criteria
    Then it should continue normally for reasonable round counts
    But it should stop when stop_requested is True
    And it should stop when round count exceeds safety limit (20 rounds)
    And it should generate appropriate completion summaries

  # =============================================================================
  # SCENARIO 7: CHAT RECORDING AND SESSION MANAGEMENT
  # =============================================================================

  Scenario: SOP agent records complete experiment session
    Given an SOP agent with chat recording enabled
    When executing a coin flip experiment
    Then the chat recorder should start a session with experiment context
    And it should record each worker message and response
    And it should record each manager guidance message
    And it should record tool calls and tool results
    And it should record system reminder messages
    And it should end the session with a completion summary

  Scenario: Chat recording captures tool explanation enforcement
    Given chat recording is active during tool explanation enforcement
    When a tool result triggers explanation enforcement
    Then the recorder should capture the tool result message
    And it should capture the system reminder injection
    And it should capture the forced explanation response
    And it should capture the tool restoration for next iteration

  # =============================================================================
  # SCENARIO 8: CUSTOMIZATION AND EXTENSIBILITY
  # =============================================================================

  Scenario: SOP agent supports multiple procedure configurations
    Given the base SOP agent architecture
    When creating different procedure definitions
    Then each can specify its own tool subset
    And each can provide custom prompts and guidance
    And each can define custom completion criteria
    And the same SOP agent can run different procedures
    
    # Example: Standard coin flip vs Extended coin flip
    Given a standard coin flip procedure with 4 tools
    And an extended coin flip procedure with 6 tools
    When comparing their configurations
    Then the extended procedure should include additional tools
    And the extended procedure should have enhanced prompts
    But both should use the same underlying SOP agent infrastructure

  # =============================================================================
  # INTEGRATION PATTERNS
  # =============================================================================

  Scenario: SOP agent demonstrates separation of concerns
    Given the coin flip experiment implementation
    Then the StandardOperatingProcedureAgent class should handle orchestration logic
    And the CoinFlipProcedureDefinition should handle experiment-specific configuration
    And the tool explanation enforcement should be generic SOP agent functionality
    And the manager coaching should be generic SOP agent functionality
    And the chat recording should be generic SOP agent functionality
    And only the tools, prompts, and completion criteria should be experiment-specific

  Scenario: Architecture supports future meta-procedure orchestration
    Given the current SOP agent design
    When considering future requirements for meta-procedures
    Then multiple SOP agents could be orchestrated by a higher-level controller
    And each SOP agent could run different procedure definitions
    And the higher-level controller could coordinate between different experiments
    And the core SOP agent functionality would remain reusable

# Expected Tool Call Patterns:

# ✅ CORRECT WORKFLOW (With Explanation Enforcement):
# [1] WORKER: coin_flip() → "heads"
# [2] SYSTEM: 🚨 REMINDER: You must explain...
# [3] WORKER: ### Summary: The first flip was heads. Now I'll record this result.
# [4] WORKER: data_logging(result="heads", flip=1) → "Data logged successfully"
# [5] SYSTEM: 🚨 REMINDER: You must explain...
# [6] WORKER: ### Summary: First result recorded. Making second flip.
# [7] WORKER: coin_flip() → "tails"
# [8] SYSTEM: 🚨 REMINDER: You must explain...
# [9] WORKER: ### Summary: Second flip was tails. Recording this result.
# [10] WORKER: data_logging(result="tails", flip=2) → "Data logged successfully"
# [Continue pattern...]

# ❌ PREVENTED PATTERN (Tool Chaining Without Explanation):
# [1] WORKER: coin_flip() → "heads"
# [2] SYSTEM: 🚨 REMINDER: You must explain...
# [3] WORKER: data_logging() ← BLOCKED! Tools removed until explanation provided

# 🎯 MANAGER COACHING PATTERN:
# Worker completes 2 flips...
# MANAGER: "You've flipped 2 times. How many more flips do you need?"
# Worker continues systematically...
# MANAGER: "Have you logged all your coin flip results?"
# Worker completes all tasks...
# MANAGER: "Are you ready to summarize and stop?"
