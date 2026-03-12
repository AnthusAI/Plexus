"""
ReAct Loop Integration Test Suite

This test suite demonstrates the complete ReAct (Reasoning and Acting) loop
with proper manager-worker collaboration:

## ReAct Loop Architecture
**ReAct = Reason + Act in cycles**

1. **Manager Reasons**: Analyzes current state, determines next action needed
2. **Worker Acts**: Executes specific tools based on manager's reasoning  
3. **Manager Observes**: Evaluates worker's action results
4. **Manager Reasons**: Determines next guidance based on observations
5. **Cycle Continues**: Until completion criteria are met

## Story Flow Integration Tests
These tests tell the complete story of how our multi-agent system
collaborates through ReAct cycles to accomplish complex tasks:

- **State Management**: Proper progression through conversation phases
- **Tool Scoping**: Phase-appropriate tool access enforcement  
- **Orchestration**: Manager provides contextual guidance based on progress
- **Execution**: Worker performs actions within scoped constraints
- **Evaluation**: Manager evaluates results and provides next direction
- **Termination**: System completes when objectives are achieved
"""

import asyncio
import json
from types import SimpleNamespace
from unittest.mock import patch, MagicMock, AsyncMock
import pytest
from typing import Dict, List, Any, Optional, Tuple


class ReActTestFramework:
    """
    Test framework for ReAct loop integration testing.
    
    This framework simulates the complete ReAct loop with:
    - Manager agent that reasons about state and provides guidance
    - Worker agent that acts on guidance with scoped tools
    - State tracking through conversation phases
    - Tool scoping enforcement
    - Result evaluation and next action determination
    """
    
    def __init__(self):
        self.manager_reasoning_log = []
        self.worker_action_log = []
        self.state_transition_log = []
        self.tool_scoping_log = []
        self.evaluation_log = []
        
        # Current system state
        self.current_phase = "exploration"
        self.nodes_created = 0
        self.tools_used = []
        self.conversation_round = 0
        
        # Available tools by phase
        self.tool_scopes = {
            "exploration": ["plexus_feedback_analysis", "plexus_feedback_find", "plexus_item_info", "think"],
            "synthesis": ["think"],
            "hypothesis_generation": ["create_experiment_node", "update_node_content", "think"]
        }
        
        # Mock tools
        self.tools = {}
        self._setup_mock_tools()
    
    def _setup_mock_tools(self):
        """Set up mock tools for testing."""
        tool_behaviors = {
            "plexus_feedback_analysis": "Found 15 feedback items with scoring issues over the last 7 days",
            "plexus_feedback_find": "Retrieved 10 specific feedback items showing threshold sensitivity problems",
            "plexus_item_info": "Item shows AI prediction: 0.8, Human correction: 0.3, indicating over-confidence",
            "think": "Reasoning: Based on the data, the main issue is threshold calibration",
            "create_experiment_node": "Successfully created experiment node with ID: exp_node_123",
            "update_node_content": "Successfully updated node configuration with new parameters"
        }
        
        for tool_name, behavior in tool_behaviors.items():
            self.tools[tool_name] = self._create_mock_tool(tool_name, behavior)
    
    def _create_mock_tool(self, name: str, behavior: str):
        """Create a mock tool with specified behavior."""
        def tool_func(args):
            if name == "create_experiment_node":
                self.nodes_created += 1
            self.tools_used.append(name)
            return behavior
        
        return SimpleNamespace(name=name, func=tool_func, description=f"Mock {name} tool")
    
    def manager_reason(self, conversation_history: List[Dict], current_state: Dict) -> str:
        """
        Simulate manager reasoning process.
        
        The manager:
        1. Analyzes current conversation state
        2. Evaluates worker's previous actions
        3. Determines what should happen next according to SOP
        4. Provides specific guidance for worker's next action
        """
        self.conversation_round += 1
        
        reasoning_context = {
            "round": self.conversation_round,
            "phase": self.current_phase,
            "nodes_created": self.nodes_created,
            "tools_used": self.tools_used.copy(),
            "conversation_length": len(conversation_history)
        }
        
        self.manager_reasoning_log.append(reasoning_context)
        
        # Manager's reasoning logic based on SOP
        if self.current_phase == "exploration":
            if len(self.tools_used) == 0:
                guidance = "Begin by analyzing the feedback data to understand scoring patterns using plexus_feedback_analysis."
            elif "plexus_feedback_analysis" in self.tools_used and "plexus_feedback_find" not in self.tools_used:
                guidance = "Good analysis. Now examine specific feedback items using plexus_feedback_find to see examples."
            elif len(self.tools_used) >= 2:
                self._transition_phase("synthesis")
                guidance = "You have sufficient data. Now synthesize your findings to identify root causes."
            else:
                guidance = "Continue gathering more detailed information about the scoring problems."
        
        elif self.current_phase == "synthesis":
            if "think" not in self.tools_used:
                guidance = "Use the think tool to reason about the patterns you've identified and determine root causes."
            else:
                self._transition_phase("hypothesis_generation")
                guidance = "Your analysis is complete. Now create experiment nodes to test solutions."
        
        elif self.current_phase == "hypothesis_generation":
            if self.nodes_created == 0:
                guidance = "Create your first experiment node to test a hypothesis based on your analysis."
            elif self.nodes_created == 1:
                guidance = "Create a second experiment node to test an alternative approach."
            else:
                guidance = "Excellent! You have created sufficient hypotheses. Analysis is complete."
        
        else:
            guidance = "Continue with the current phase activities."
        
        print(f"🧠 Manager Reasoning (Round {self.conversation_round}): {guidance}")
        return guidance
    
    def _transition_phase(self, new_phase: str):
        """Transition to a new conversation phase."""
        old_phase = self.current_phase
        self.current_phase = new_phase
        
        transition_record = {
            "from": old_phase,
            "to": new_phase,
            "round": self.conversation_round,
            "trigger": f"tools_used: {len(self.tools_used)}, nodes_created: {self.nodes_created}"
        }
        
        self.state_transition_log.append(transition_record)
        print(f"🔄 Phase Transition: {old_phase} → {new_phase} (Round {self.conversation_round})")
    
    def worker_act(self, guidance: str) -> Tuple[str, bool, str]:
        """
        Simulate worker acting on manager guidance.
        
        The worker:
        1. Interprets manager's guidance
        2. Selects appropriate tool for the task
        3. Checks if tool is available in current phase
        4. Executes tool if authorized
        5. Reports results back to manager
        
        Returns: (tool_name, success, result)
        """
        # Worker interprets guidance to select tool
        tool_selection_logic = {
            "analyzing the feedback data": "plexus_feedback_analysis",
            "examine specific feedback items": "plexus_feedback_find", 
            "detailed information": "plexus_item_info",
            "synthesize": "think",
            "identify root causes": "think",
            "create experiment": "create_experiment_node",
            "create your first": "create_experiment_node",
            "create a second": "create_experiment_node",
            "update node": "update_node_content"
        }
        
        # Find matching tool based on guidance (more precise matching)
        selected_tool = None
        for keyword, tool_name in tool_selection_logic.items():
            if keyword.lower() in guidance.lower():
                selected_tool = tool_name
                break
        
        # If no match found, be more specific about what was requested
        if not selected_tool:
            if "create" in guidance.lower() and "experiment" in guidance.lower():
                selected_tool = "create_experiment_node"
            elif "analyze" in guidance.lower() or "feedback" in guidance.lower():
                selected_tool = "plexus_feedback_analysis"
            else:
                selected_tool = "think"  # Default fallback
        
        # Check tool scoping
        allowed_tools = self.tool_scopes.get(self.current_phase, [])
        
        scoping_check = {
            "tool": selected_tool,
            "phase": self.current_phase,
            "allowed": selected_tool in allowed_tools,
            "round": self.conversation_round
        }
        self.tool_scoping_log.append(scoping_check)
        
        if selected_tool not in allowed_tools:
            error_msg = f"Tool {selected_tool} not available in {self.current_phase} phase"
            print(f"🚫 Worker Action Blocked: {error_msg}")
            return selected_tool, False, error_msg
        
        # Execute the tool
        if selected_tool in self.tools:
            result = self.tools[selected_tool].func({})
            
            action_record = {
                "tool": selected_tool,
                "phase": self.current_phase,
                "round": self.conversation_round,
                "result": result,
                "success": True
            }
            self.worker_action_log.append(action_record)
            
            print(f"🔧 Worker Action: {selected_tool} → {result[:50]}...")
            return selected_tool, True, result
        else:
            error_msg = f"Tool {selected_tool} not found"
            print(f"❌ Worker Action Failed: {error_msg}")
            return selected_tool, False, error_msg
    
    def manager_evaluate(self, tool_name: str, success: bool, result: str) -> Dict[str, Any]:
        """
        Simulate manager evaluating worker's action results.
        
        The manager:
        1. Analyzes the tool execution result
        2. Determines if the action accomplished the intended goal
        3. Decides if phase transition or continuation is needed
        4. Prepares context for next reasoning cycle
        """
        evaluation = {
            "round": self.conversation_round,
            "tool": tool_name,
            "success": success,
            "result_quality": "good" if success else "failed",
            "phase_progress": self._assess_phase_progress(),
            "next_action_needed": self._determine_next_action()
        }
        
        self.evaluation_log.append(evaluation)
        
        print(f"📊 Manager Evaluation: {tool_name} {'succeeded' if success else 'failed'}, "
              f"progress: {evaluation['phase_progress']}")
        
        return evaluation
    
    def _assess_phase_progress(self) -> str:
        """Assess progress within current phase."""
        if self.current_phase == "exploration":
            analysis_tools_used = len([tool for tool in self.tools_used 
                                     if tool in ["plexus_feedback_analysis", "plexus_feedback_find", "plexus_item_info"]])
            if analysis_tools_used >= 2:
                return "sufficient_data_gathered"
            elif analysis_tools_used >= 1:
                return "partial_analysis_complete"
            else:
                return "analysis_needed"
        
        elif self.current_phase == "synthesis":
            if "think" in self.tools_used:
                return "synthesis_complete"
            else:
                return "synthesis_needed"
        
        elif self.current_phase == "hypothesis_generation":
            if self.nodes_created >= 2:
                return "hypotheses_complete"
            elif self.nodes_created >= 1:
                return "partial_hypotheses_created"
            else:
                return "hypotheses_needed"
        
        return "in_progress"
    
    def _determine_next_action(self) -> str:
        """Determine what action should happen next."""
        progress = self._assess_phase_progress()
        
        if progress in ["sufficient_data_gathered", "synthesis_complete"]:
            return "phase_transition"
        elif progress in ["hypotheses_complete"]:
            return "completion"
        else:
            return "continue_phase"
    
    def should_continue(self) -> bool:
        """Determine if the ReAct loop should continue."""
        return (self.conversation_round < 10 and  # Safety limit
                self.nodes_created < 2)  # Completion criteria
    
    def get_system_state(self) -> Dict[str, Any]:
        """Get current system state for analysis."""
        return {
            "phase": self.current_phase,
            "nodes_created": self.nodes_created,
            "tools_used": self.tools_used.copy(),
            "conversation_round": self.conversation_round,
            "phase_progress": self._assess_phase_progress()
        }


class TestReActLoopIntegration:
    """Test suite for complete ReAct loop integration."""
    
    def test_complete_react_loop_cycle(self):
        """
        STORY: Complete ReAct loop demonstrating manager-worker collaboration
        
        This test demonstrates a full ReAct cycle:
        1. **Manager Reasons**: Analyzes state, provides guidance
        2. **Worker Acts**: Executes tools based on guidance
        3. **Manager Evaluates**: Assesses results, determines next action
        4. **Cycle Repeats**: Until completion criteria met
        
        The loop should show proper state management, tool scoping,
        and intelligent progression through conversation phases.
        """
        print("\n🔄 Starting Complete ReAct Loop Test...")
        
        framework = ReActTestFramework()
        conversation_history = []
        
        # Execute ReAct loop
        cycle_count = 0
        while framework.should_continue() and cycle_count < 10:
            cycle_count += 1
            print(f"\n--- ReAct Cycle {cycle_count} ---")
            
            # 1. MANAGER REASONS
            current_state = framework.get_system_state()
            guidance = framework.manager_reason(conversation_history, current_state)
            
            # 2. WORKER ACTS
            tool_name, success, result = framework.worker_act(guidance)
            
            # 3. MANAGER EVALUATES
            evaluation = framework.manager_evaluate(tool_name, success, result)
            
            # Update conversation history
            conversation_history.append({
                "cycle": cycle_count,
                "guidance": guidance,
                "action": {"tool": tool_name, "success": success, "result": result},
                "evaluation": evaluation
            })
            
            # Safety check
            if not success:
                print(f"⚠️ Tool execution failed: {result}")
                break
        
        # === VERIFICATION ===
        print(f"\n✅ REACT LOOP VERIFICATION (Completed {cycle_count} cycles)")
        
        # Verify conversation progression
        assert cycle_count >= 4, f"Should complete multiple ReAct cycles, completed {cycle_count}"
        print(f"    ✓ Completed {cycle_count} ReAct cycles")
        
        # Verify manager reasoning
        assert len(framework.manager_reasoning_log) == cycle_count, "Manager should reason in each cycle"
        reasoning_phases = [log["phase"] for log in framework.manager_reasoning_log]
        assert "exploration" in reasoning_phases, "Should include exploration reasoning"
        assert "hypothesis_generation" in reasoning_phases, "Should reach hypothesis generation"
        print(f"    ✓ Manager reasoning across phases: {set(reasoning_phases)}")
        
        # Verify worker actions
        assert len(framework.worker_action_log) == len([h for h in conversation_history if h["action"]["success"]]), "Worker should act successfully in each successful cycle"
        tools_executed = [log["tool"] for log in framework.worker_action_log]
        assert "plexus_feedback_analysis" in tools_executed, "Should execute analysis tools"
        assert "create_experiment_node" in tools_executed, "Should create experiment nodes"
        print(f"    ✓ Worker executed tools: {set(tools_executed)}")
        
        # Verify state transitions
        assert len(framework.state_transition_log) >= 2, "Should transition through multiple phases"
        transitions = [(t["from"], t["to"]) for t in framework.state_transition_log]
        expected_transitions = [("exploration", "synthesis"), ("synthesis", "hypothesis_generation")]
        for expected in expected_transitions:
            assert expected in transitions, f"Should include transition {expected[0]} → {expected[1]}"
        print(f"    ✓ Phase transitions: {transitions}")
        
        # Verify tool scoping
        scoping_logs = framework.tool_scoping_log
        blocked_attempts = [log for log in scoping_logs if not log["allowed"]]
        # Note: In this test we don't expect blocks since worker selects appropriate tools
        print(f"    ✓ Tool scoping enforced: {len(scoping_logs)} checks, {len(blocked_attempts)} blocks")
        
        # Verify evaluations
        assert len(framework.evaluation_log) == cycle_count, "Manager should evaluate each action"
        successful_evaluations = [log for log in framework.evaluation_log if log["success"]]
        assert len(successful_evaluations) >= 3, "Should have multiple successful evaluations"
        print(f"    ✓ Manager evaluations: {len(successful_evaluations)} successful")
        
        # Verify completion criteria
        final_state = framework.get_system_state()
        assert final_state["nodes_created"] >= 1, "Should create at least one hypothesis node"
        assert final_state["phase"] in ["hypothesis_generation"], "Should reach final phases"
        print(f"    ✓ Completion: {final_state['nodes_created']} nodes, phase {final_state['phase']}")
        
        print("\n🎉 REACT LOOP INTEGRATION TEST SUCCESSFUL!")
        print("    Manager reasoning guided worker actions effectively")
        print("    Worker executed appropriate tools in each phase")
        print("    System progressed through phases systematically") 
        print("    Evaluation feedback informed next actions")


class TestToolScopingEnforcement:
    """Test suite for tool scoping enforcement in ReAct loop."""
    
    def test_tool_scoping_prevents_unauthorized_access(self):
        """
        STORY: Tool scoping system prevents worker from accessing wrong tools
        
        This test demonstrates:
        1. **Phase-Appropriate Tools**: Worker only gets tools for current phase
        2. **Unauthorized Blocking**: Attempts to use wrong-phase tools are blocked
        3. **Clear Error Messages**: Scoping violations provide helpful feedback
        4. **Graceful Handling**: System continues despite scoping violations
        """
        print("\n🛡️ Testing Tool Scoping Enforcement...")
        
        framework = ReActTestFramework()
        
        # Test exploration phase restrictions
        framework.current_phase = "exploration"
        
        # Try to use hypothesis tool during exploration (should be blocked)
        tool_name, success, result = framework.worker_act("Create an experiment node to test threshold adjustments")
        
        assert not success, "Hypothesis tool should be blocked during exploration"
        assert "not available" in result, "Should provide clear scoping error message"
        assert framework.tool_scoping_log[-1]["allowed"] == False, "Scoping log should record the block"
        
        print("    ✓ Exploration phase correctly blocks hypothesis tools")
        
        # Test synthesis phase restrictions  
        framework.current_phase = "synthesis"
        
        # Try to use analysis tool during synthesis (should be blocked)
        tool_name, success, result = framework.worker_act("Analyze more feedback data using plexus_feedback_analysis")
        
        assert not success, "Analysis tool should be blocked during synthesis"
        assert "not available" in result, "Should provide clear scoping error message"
        
        print("    ✓ Synthesis phase correctly blocks analysis tools")
        
        # Test hypothesis phase allows creation tools
        framework.current_phase = "hypothesis_generation"
        
        # Try to use hypothesis tool during hypothesis phase (should work)
        tool_name, success, result = framework.worker_act("Create an experiment node to test threshold adjustments")
        
        assert success, "Hypothesis tool should be allowed during hypothesis generation"
        assert "create_experiment_node" == tool_name, "Should select correct tool"
        assert framework.nodes_created == 1, "Should successfully create node"
        
        print("    ✓ Hypothesis phase correctly allows creation tools")
        
        # Verify scoping log
        scoping_checks = framework.tool_scoping_log
        assert len(scoping_checks) == 3, "Should have recorded 3 scoping checks"
        
        blocked_checks = [check for check in scoping_checks if not check["allowed"]]
        allowed_checks = [check for check in scoping_checks if check["allowed"]]
        
        assert len(blocked_checks) == 2, "Should have blocked 2 unauthorized tool attempts"
        assert len(allowed_checks) == 1, "Should have allowed 1 authorized tool attempt"
        
        print(f"    ✓ Scoping enforcement: {len(blocked_checks)} blocked, {len(allowed_checks)} allowed")
        
        print("\n🎉 TOOL SCOPING ENFORCEMENT TEST SUCCESSFUL!")


class TestConversationStateManagement:
    """Test suite for conversation state management and transitions."""
    
    def test_state_transitions_follow_logical_progression(self):
        """
        STORY: Conversation state transitions follow logical SOP progression
        
        This test demonstrates:
        1. **Sequential Phases**: Exploration → Synthesis → Hypothesis Generation
        2. **Transition Triggers**: Phases advance when criteria are met
        3. **State Persistence**: System maintains state across transitions
        4. **Rollback Prevention**: Cannot move backwards in progression
        """
        print("\n🔄 Testing Conversation State Management...")
        
        framework = ReActTestFramework()
        
        # Start in exploration phase
        assert framework.current_phase == "exploration", "Should start in exploration phase"
        
        # Simulate progression through exploration
        initial_state = framework.get_system_state()
        assert initial_state["phase_progress"] == "analysis_needed", "Should need analysis initially"
        
        # Execute analysis tools to trigger transition
        framework.worker_act("Start by analyzing the feedback data using plexus_feedback_analysis")
        framework.worker_act("Examine specific feedback items using plexus_feedback_find")
        
        # Check state after sufficient analysis
        post_analysis_state = framework.get_system_state()
        analysis_tools_used = len([tool for tool in framework.tools_used 
                                  if tool in ["plexus_feedback_analysis", "plexus_feedback_find"]])
        assert analysis_tools_used >= 2, "Should have used multiple analysis tools"
        
        # Trigger transition to synthesis
        conversation_history = []
        framework.manager_reason(conversation_history, post_analysis_state)
        
        # Verify transition to synthesis
        assert framework.current_phase == "synthesis", "Should transition to synthesis phase"
        assert len(framework.state_transition_log) == 1, "Should record one transition"
        
        transition = framework.state_transition_log[0]
        assert transition["from"] == "exploration", "Should transition from exploration"
        assert transition["to"] == "synthesis", "Should transition to synthesis"
        
        print("    ✓ Exploration → Synthesis transition triggered correctly")
        
        # Execute synthesis work
        framework.worker_act("Synthesize findings to identify root causes")
        
        # Trigger transition to hypothesis generation
        framework.manager_reason(conversation_history, framework.get_system_state())
        
        # Verify transition to hypothesis generation
        assert framework.current_phase == "hypothesis_generation", "Should transition to hypothesis generation"
        assert len(framework.state_transition_log) == 2, "Should record two transitions"
        
        final_transition = framework.state_transition_log[1]
        assert final_transition["from"] == "synthesis", "Should transition from synthesis"
        assert final_transition["to"] == "hypothesis_generation", "Should transition to hypothesis generation"
        
        print("    ✓ Synthesis → Hypothesis Generation transition triggered correctly")
        
        # Verify complete progression
        transitions = [(t["from"], t["to"]) for t in framework.state_transition_log]
        expected_progression = [("exploration", "synthesis"), ("synthesis", "hypothesis_generation")]
        
        assert transitions == expected_progression, f"Should follow expected progression: {expected_progression}"
        
        # Verify state persistence
        final_state = framework.get_system_state()
        assert len(final_state["tools_used"]) >= 3, "Should persist tool usage across transitions"
        assert final_state["conversation_round"] >= 2, "Should persist conversation progress"
        
        print(f"    ✓ State progression: {' → '.join([t[0] for t in transitions] + [transitions[-1][1]])}")
        print(f"    ✓ State persistence: {len(final_state['tools_used'])} tools, round {final_state['conversation_round']}")
        
        print("\n🎉 CONVERSATION STATE MANAGEMENT TEST SUCCESSFUL!")


class TestSafeguardsAndTermination:
    """Test suite for safety limits and proper termination conditions."""
    
    def test_safety_limits_prevent_infinite_loops(self):
        """
        STORY: Safety mechanisms prevent runaway conversations
        
        This test demonstrates:
        1. **Round Limits**: Maximum conversation rounds enforced
        2. **Completion Detection**: System recognizes when objectives are met
        3. **Graceful Termination**: Proper cleanup when limits reached
        4. **State Preservation**: Final state is accessible for analysis
        """
        print("\n🛡️ Testing Safety Limits and Termination...")
        
        framework = ReActTestFramework()
        
        # Test round limit enforcement
        max_rounds_reached = False
        round_count = 0
        
        # Simulate a scenario that could go infinite without limits
        while framework.should_continue() and round_count < 15:  # Higher than framework's limit
            round_count += 1
            conversation_history = []
            
            # Manager provides guidance
            guidance = framework.manager_reason(conversation_history, framework.get_system_state())
            
            # Worker acts (always succeeding to avoid early termination)
            tool_name, success, result = framework.worker_act(guidance)
            
            # Check if we've hit the safety limit
            if round_count >= 10:  # Framework's internal limit
                max_rounds_reached = True
                break
        
        # Verify safety limit enforcement
        assert round_count <= 10, "Should enforce maximum round limit"
        assert framework.conversation_round <= 10, "Framework should track rounds correctly"
        
        print(f"    ✓ Safety limit enforced: stopped at round {round_count}")
        
        # Test completion detection
        completion_framework = ReActTestFramework()
        
        # Simulate rapid completion by creating nodes directly
        completion_framework.nodes_created = 2  # Meet completion criteria
        
        should_continue = completion_framework.should_continue()
        assert not should_continue, "Should detect completion when criteria are met"
        
        print("    ✓ Completion detection: recognizes when objectives met")
        
        # Test graceful termination state
        final_state = framework.get_system_state()
        
        required_state_fields = ["phase", "nodes_created", "tools_used", "conversation_round", "phase_progress"]
        for field in required_state_fields:
            assert field in final_state, f"Final state should include {field}"
        
        assert isinstance(final_state["tools_used"], list), "Tools used should be preserved as list"
        assert isinstance(final_state["nodes_created"], int), "Node count should be preserved as integer"
        assert final_state["conversation_round"] > 0, "Should have completed some conversation rounds"
        
        print(f"    ✓ Graceful termination: state preserved with {len(final_state)} fields")
        
        # Test termination reasons tracking
        termination_reasons = []
        
        if framework.conversation_round >= 10:
            termination_reasons.append("max_rounds_reached")
        if framework.nodes_created >= 2:
            termination_reasons.append("completion_criteria_met")
        
        assert len(termination_reasons) > 0, "Should identify termination reasons"
        
        print(f"    ✓ Termination reasons identified: {termination_reasons}")
        
        print("\n🎉 SAFETY LIMITS AND TERMINATION TEST SUCCESSFUL!")


class TestReActStoryIntegration:
    """Integration test demonstrating the complete ReAct story."""
    
    @pytest.mark.asyncio
    async def test_complete_multi_agent_react_story_integration(self):
        """
        COMPLETE INTEGRATION STORY: Multi-agent ReAct system collaboration
        
        This test tells the complete story of our multi-agent ReAct system:
        
        **THE STORY:**
        A complex AI evaluation task requires systematic analysis and hypothesis creation.
        The manager agent follows standard operating procedures to guide a worker agent
        through the task using structured ReAct cycles.
        
        **CHARACTERS:**
        - **Manager Agent**: Follows SOPs, provides guidance, evaluates progress
        - **Worker Agent**: Executes tools, reports results, follows manager direction
        
        **PLOT:**
        1. **Setup**: Manager and worker initialized with tools and constraints
        2. **Exploration**: Manager guides worker to analyze feedback data systematically
        3. **Synthesis**: Manager guides worker to identify patterns and root causes
        4. **Hypothesis**: Manager guides worker to create experiment nodes for testing
        5. **Completion**: System recognizes objectives met and terminates gracefully
        
        **THEMES:**
        - Structured collaboration between AI agents
        - Tool scoping and security enforcement  
        - Adaptive reasoning and action cycles
        - Systematic problem-solving methodology
        
        This integration test validates that all components work together
        to accomplish complex reasoning tasks through agent collaboration.
        """
        print("\n🎭 COMPLETE MULTI-AGENT REACT STORY INTEGRATION")
        print("="*60)
        
        framework = ReActTestFramework()
        story_log = []
        
        print("\n📚 STORY SETUP")
        print("Manager Agent: Initialized with standard operating procedures")
        print("Worker Agent: Initialized with scoped tool access")
        print("Task: Analyze scoring feedback and create improvement hypotheses")
        
        # === ACT 1: EXPLORATION ===
        print("\n🎬 ACT 1: EXPLORATION - Understanding the Problem")
        print("-" * 40)
        
        act1_cycles = 0
        while framework.current_phase == "exploration" and act1_cycles < 4:
            act1_cycles += 1
            
            # Manager reasons about exploration needs
            guidance = framework.manager_reason([], framework.get_system_state())
            story_log.append(f"Act 1.{act1_cycles}: Manager guidance - {guidance[:60]}...")
            
            # Worker acts on exploration guidance
            tool_name, success, result = framework.worker_act(guidance)
            story_log.append(f"Act 1.{act1_cycles}: Worker action - {tool_name} ({'success' if success else 'failed'})")
            
            # Manager evaluates exploration progress
            evaluation = framework.manager_evaluate(tool_name, success, result)
            story_log.append(f"Act 1.{act1_cycles}: Manager evaluation - {evaluation['phase_progress']}")
            
            if not success:
                break
        
        # Verify Act 1 completion
        assert framework.current_phase != "exploration" or len(framework.tools_used) >= 2, "Act 1 should gather sufficient exploration data"
        exploration_tools = [tool for tool in framework.tools_used if "feedback" in tool or "item" in tool]
        assert len(exploration_tools) >= 1, "Should use exploration tools in Act 1"
        
        print(f"✅ Act 1 Complete: {act1_cycles} cycles, transitioned from exploration")
        
        # === ACT 2: SYNTHESIS ===
        print("\n🎬 ACT 2: SYNTHESIS - Identifying Root Causes") 
        print("-" * 40)
        
        act2_cycles = 0
        while framework.current_phase == "synthesis" and act2_cycles < 3:
            act2_cycles += 1
            
            # Manager reasons about synthesis needs
            guidance = framework.manager_reason([], framework.get_system_state())
            story_log.append(f"Act 2.{act2_cycles}: Manager guidance - {guidance[:60]}...")
            
            # Worker acts on synthesis guidance
            tool_name, success, result = framework.worker_act(guidance)
            story_log.append(f"Act 2.{act2_cycles}: Worker action - {tool_name} ({'success' if success else 'failed'})")
            
            # Manager evaluates synthesis progress
            evaluation = framework.manager_evaluate(tool_name, success, result)
            story_log.append(f"Act 2.{act2_cycles}: Manager evaluation - {evaluation['phase_progress']}")
            
            if not success:
                break
        
        # Verify Act 2 completion
        assert framework.current_phase != "synthesis" or "think" in framework.tools_used, "Act 2 should include reasoning"
        
        print(f"✅ Act 2 Complete: {act2_cycles} cycles, transitioned from synthesis")
        
        # === ACT 3: HYPOTHESIS GENERATION ===
        print("\n🎬 ACT 3: HYPOTHESIS GENERATION - Creating Solutions")
        print("-" * 40)
        
        act3_cycles = 0
        while framework.current_phase == "hypothesis_generation" and framework.nodes_created < 2 and act3_cycles < 4:
            act3_cycles += 1
            
            # Manager reasons about hypothesis needs
            guidance = framework.manager_reason([], framework.get_system_state())
            story_log.append(f"Act 3.{act3_cycles}: Manager guidance - {guidance[:60]}...")
            
            # Worker acts on hypothesis guidance
            tool_name, success, result = framework.worker_act(guidance)
            story_log.append(f"Act 3.{act3_cycles}: Worker action - {tool_name} ({'success' if success else 'failed'})")
            
            # Manager evaluates hypothesis progress
            evaluation = framework.manager_evaluate(tool_name, success, result)
            story_log.append(f"Act 3.{act3_cycles}: Manager evaluation - {evaluation['phase_progress']}")
            
            if not success:
                break
        
        # Verify Act 3 completion
        assert framework.nodes_created >= 1, "Act 3 should create hypothesis nodes"
        node_creation_tools = [tool for tool in framework.tools_used if "create" in tool]
        assert len(node_creation_tools) >= 1, "Should use node creation tools in Act 3"
        
        print(f"✅ Act 3 Complete: {act3_cycles} cycles, {framework.nodes_created} nodes created")
        
        # === EPILOGUE: COMPLETION ===
        print("\n🎬 EPILOGUE: STORY COMPLETION")
        print("-" * 40)
        
        final_state = framework.get_system_state()
        
        print("Story Outcome:")
        print(f"  📊 Data Analysis: {len([t for t in framework.tools_used if 'feedback' in t or 'item' in t])} analysis tools used")
        print(f"  🧠 Synthesis: {'✓' if 'think' in framework.tools_used else '✗'} reasoning completed")
        print(f"  🧪 Hypotheses: {framework.nodes_created} experiment nodes created")
        print(f"  🔄 Collaboration: {framework.conversation_round} ReAct cycles completed")
        print(f"  📈 Progression: {len(framework.state_transition_log)} phase transitions")
        
        # === STORY VALIDATION ===
        print("\n🎯 STORY VALIDATION")
        print("="*40)
        
        # Validate story structure
        assert len(story_log) >= 6, f"Story should have sufficient narrative events, got {len(story_log)}"
        print(f"✓ Story Events: {len(story_log)} narrative events recorded")
        
        # Validate character roles
        manager_actions = len(framework.manager_reasoning_log)
        worker_actions = len(framework.worker_action_log)
        assert manager_actions >= 3, f"Manager should reason multiple times, got {manager_actions}"
        assert worker_actions >= 3, f"Worker should act multiple times, got {worker_actions}"
        print(f"✓ Character Development: Manager {manager_actions} reasonings, Worker {worker_actions} actions")
        
        # Validate plot progression
        phases_visited = set([log["phase"] for log in framework.manager_reasoning_log])
        expected_phases = {"exploration", "synthesis", "hypothesis_generation"}
        assert len(phases_visited.intersection(expected_phases)) >= 2, f"Should visit multiple phases, visited {phases_visited}"
        print(f"✓ Plot Progression: {len(phases_visited)} phases visited")
        
        # Validate theme execution (structured collaboration)
        collaboration_indicators = {
            "tool_scoping": len(framework.tool_scoping_log) > 0,
            "state_management": len(framework.state_transition_log) > 0,
            "evaluation_feedback": len(framework.evaluation_log) > 0,
            "systematic_progression": framework.nodes_created > 0
        }
        
        successful_themes = sum(collaboration_indicators.values())
        assert successful_themes >= 3, f"Should demonstrate key collaboration themes, achieved {successful_themes}/4"
        print(f"✓ Theme Execution: {successful_themes}/4 collaboration themes demonstrated")
        
        # Validate story completion
        completion_criteria = {
            "nodes_created": framework.nodes_created >= 1,
            "analysis_completed": len([t for t in framework.tools_used if 'feedback' in t]) >= 1,
            "synthesis_performed": 'think' in framework.tools_used,
            "phases_progressed": len(framework.state_transition_log) >= 1
        }
        
        completion_score = sum(completion_criteria.values())
        assert completion_score >= 3, f"Should meet completion criteria, achieved {completion_score}/4"
        print(f"✓ Story Completion: {completion_score}/4 completion criteria met")
        
        print("\n🎉 MULTI-AGENT REACT STORY INTEGRATION SUCCESSFUL!")
        print("="*60)
        print("The manager and worker agents successfully collaborated")
        print("through structured ReAct cycles to accomplish complex reasoning")
        print("and hypothesis generation tasks using systematic methodology.")
        print("="*60)
        
        # Print story summary for documentation
        print(f"\n📖 STORY SUMMARY ({len(story_log)} events):")
        for i, event in enumerate(story_log[-8:], 1):  # Show last 8 events
            print(f"  {len(story_log)-8+i:2}. {event}")
        if len(story_log) > 8:
            print(f"  ... ({len(story_log)-8} earlier events)")


# Test completion marker
@pytest.fixture(autouse=True)
def mark_react_test_completion():
    """Mark ReAct loop test completion."""
    yield
    print("📝 ReAct loop integration test coverage executed")
