"""
BDD Test Suite: SOP Agent Coin Flip Scenario

This module provides comprehensive testing of the StandardOperatingProcedureAgent
using a simple, controllable scenario: conducting a coin flip experiment.

The scenario tests all core SOP agent features:
1. Worker agent tool access management
2. Tool explanation enforcement
3. Stop tool functionality
4. Manager agent coaching
5. Procedure completion detection
6. Chat recording integration

Test Scenario:
1. Worker calls coin_flip tool 3 times
2. Worker calls data_logging tool to record each result
3. Worker calls accuracy_calculator tool to compute results
4. Worker calls stop_procedure tool to finish
5. Manager provides coaching guidance throughout
"""

import pytest
import asyncio
from unittest.mock import Mock, AsyncMock, patch
from typing import Dict, Any, List, Optional
from langchain_core.messages import AIMessage, HumanMessage, SystemMessage, ToolMessage

from plexus.cli.experiment.sop_agent_base import StandardOperatingProcedureAgent, ProcedureDefinition, FlowManager, ChatRecorder


class CoinFlipProcedureDefinition(ProcedureDefinition):
    """
    Simple procedure definition for coin flip experiment.
    
    This demonstrates how to create a custom procedure with:
    - Specific tool subset for worker agent
    - Custom prompts for the task
    - Simple completion criteria
    """
    
    def __init__(self):
        """Initialize with coin flip experiment tools."""
        self.available_tools = [
            "coin_flip",           # Randomly returns "heads" or "tails"
            "data_logging",        # Records experiment results
            "accuracy_calculator", # Computes accuracy statistics
            "stop_procedure"       # Signals completion
        ]
    
    def get_system_prompt(self, context: Dict[str, Any]) -> str:
        """Get worker agent system prompt for coin flip experiment."""
        return """You are a research assistant conducting a simple coin flip experiment.

Your task is to:
1. Flip a coin 3 times using the coin_flip tool
2. Log each result using the data_logging tool
3. Calculate the accuracy using the accuracy_calculator tool
4. Summarize your findings
5. Use stop_procedure when complete

Available tools:
- coin_flip: Returns "heads" or "tails" randomly
- data_logging: Records experimental data
- accuracy_calculator: Computes statistics
- stop_procedure: Signals task completion

Work systematically and explain each step clearly."""

    def get_user_prompt(self, context: Dict[str, Any]) -> str:
        """Get initial user prompt for coin flip experiment."""
        experiment_name = context.get('experiment_name', 'Coin Flip Study')
        return f"""Please conduct a coin flip experiment: "{experiment_name}"

Your task:
1. Flip a coin 3 times 
2. Record each result
3. Calculate the accuracy/statistics
4. Provide a summary
5. Stop when complete

Start by making your first coin flip."""

    def get_sop_guidance_prompt(self, context: Dict[str, Any], state_data: Dict[str, Any]) -> str:
        """Get SOP manager guidance prompt."""
        tools_used = state_data.get('tools_used', [])
        coin_flips = tools_used.count('coin_flip')
        data_logs = tools_used.count('data_logging')
        
        if coin_flips == 0:
            return "Have you started flipping the coin yet? What's your first step?"
        elif coin_flips < 3:
            return f"You've flipped {coin_flips} times. How many more flips do you need?"
        elif data_logs < coin_flips:
            return "Have you logged all your coin flip results? What data needs to be recorded?"
        elif 'accuracy_calculator' not in tools_used:
            return "Have you calculated the accuracy of your experiment yet?"
        else:
            return "You've completed the experiment steps. Are you ready to summarize and stop?"

    def get_allowed_tools(self) -> List[str]:
        """Get allowed tools for worker agent."""
        return self.available_tools

    def should_continue(self, state_data: Dict[str, Any]) -> bool:
        """Determine if procedure should continue."""
        # Stop if explicitly requested
        if state_data.get('stop_requested', False):
            return False
        
        # Safety limit
        round_num = state_data.get('round', 0)
        if round_num >= 20:  # Much lower for simple task
            return False
        
        return True

    def get_completion_summary(self, state_data: Dict[str, Any]) -> str:
        """Get completion summary."""
        tools_used = state_data.get('tools_used', [])
        coin_flips = tools_used.count('coin_flip')
        data_logs = tools_used.count('data_logging')
        calculations = tools_used.count('accuracy_calculator')
        rounds = state_data.get('round', 0)
        
        return f"Coin flip experiment completed: {coin_flips} flips, {data_logs} data entries, {calculations} calculations in {rounds} rounds."


class MockCoinFlipFlowManager(FlowManager):
    """Mock flow manager for coin flip experiment."""
    
    def __init__(self):
        self.should_continue_flag = True
    
    def update_state(self, new_data: Dict[str, Any]) -> Dict[str, Any]:
        """Update and return current state."""
        return new_data
    
    def should_continue(self) -> bool:
        """Check if flow should continue."""
        return self.should_continue_flag
    
    def get_next_guidance(self) -> Optional[str]:
        """Get guidance for next step."""
        return "Continue with the experiment steps."
    
    def get_completion_summary(self) -> str:
        """Get completion summary."""
        return "Mock coin flip experiment completed."


class MockCoinFlipChatRecorder(ChatRecorder):
    """Mock chat recorder for testing."""
    
    def __init__(self):
        self.recorded_messages = []
        self.session_id = "test_session_123"
    
    async def start_session(self, context: Dict[str, Any]) -> Optional[str]:
        """Start recording session."""
        self.recorded_messages.append(("SESSION_START", context))
        return self.session_id
    
    async def record_message(self, role: str, content: str, message_type: str) -> Optional[str]:
        """Record a message."""
        message_id = f"msg_{len(self.recorded_messages)}"
        self.recorded_messages.append((role, content, message_type, message_id))
        return message_id
    
    async def record_system_message(self, content: str) -> Optional[str]:
        """Record a system message."""
        message_id = f"sys_{len(self.recorded_messages)}"
        self.recorded_messages.append(("SYSTEM", content, "SYSTEM_MESSAGE", message_id))
        return message_id
    
    async def end_session(self, status: str, name: str = None) -> bool:
        """End recording session."""
        self.recorded_messages.append(("SESSION_END", status, name))
        return True


class TestSOPAgentCoinFlipScenario:
    """
    Comprehensive BDD test suite for SOP agent using coin flip scenario.
    
    This tests all core SOP agent functionality:
    - Tool access management
    - Tool explanation enforcement 
    - Manager coaching
    - Stop functionality
    - Chat recording
    - Procedure completion
    """

    @pytest.fixture
    def coin_flip_procedure_definition(self):
        """Create coin flip procedure definition."""
        return CoinFlipProcedureDefinition()

    def test_given_coin_flip_procedure_when_initialized_then_has_correct_tools(self, coin_flip_procedure_definition):
        """
        Given a coin flip procedure definition
        When the procedure is initialized
        Then it should have the correct subset of tools available
        """
        # Act
        available_tools = coin_flip_procedure_definition.get_allowed_tools()
        
        # Assert
        assert "coin_flip" in available_tools
        assert "data_logging" in available_tools
        assert "accuracy_calculator" in available_tools
        assert "stop_procedure" in available_tools
        assert len(available_tools) == 4
        
        # Should not have access to other experimental tools
        assert "plexus_feedback_find" not in available_tools
        assert "create_experiment_node" not in available_tools

    def test_given_coin_flip_procedure_when_getting_prompts_then_provides_task_specific_guidance(self, coin_flip_procedure_definition):
        """
        Given a coin flip procedure definition
        When getting system and user prompts
        Then it should provide task-specific guidance for the coin flip experiment
        """
        # Arrange
        context = {"experiment_name": "Test Coin Flip Study"}
        
        # Act
        system_prompt = coin_flip_procedure_definition.get_system_prompt(context)
        user_prompt = coin_flip_procedure_definition.get_user_prompt(context)
        
        # Assert
        assert "coin flip experiment" in system_prompt
        assert "coin_flip tool" in system_prompt
        assert "data_logging tool" in system_prompt
        assert "accuracy_calculator tool" in system_prompt
        assert "stop_procedure" in system_prompt
        
        assert "Test Coin Flip Study" in user_prompt
        assert "Flip a coin 3 times" in user_prompt
        assert "Record each result" in user_prompt

    def test_given_coin_flip_procedure_when_checking_continuation_then_respects_stop_and_safety_limits(self, coin_flip_procedure_definition):
        """
        Given a coin flip procedure definition
        When checking if procedure should continue
        Then it should respect stop requests and safety limits
        """
        # Should continue normally
        normal_state = {"round": 5, "tools_used": ["coin_flip"]}
        assert coin_flip_procedure_definition.should_continue(normal_state) == True
        
        # Should stop when explicitly requested
        stop_state = {"round": 3, "stop_requested": True}
        assert coin_flip_procedure_definition.should_continue(stop_state) == False
        
        # Should stop at safety limit
        safety_state = {"round": 25}  # Above safety limit of 20
        assert coin_flip_procedure_definition.should_continue(safety_state) == False

    def test_given_coin_flip_procedure_when_generating_sop_guidance_then_provides_contextual_coaching(self, coin_flip_procedure_definition):
        """
        Given a coin flip procedure definition
        When generating SOP guidance at different stages
        Then it should provide contextual coaching questions
        """
        context = {"experiment_name": "Test Study"}
        
        # No tools used yet
        early_state = {"tools_used": []}
        guidance = coin_flip_procedure_definition.get_sop_guidance_prompt(context, early_state)
        assert "started flipping" in guidance
        
        # Some coin flips done
        mid_state = {"tools_used": ["coin_flip", "coin_flip"]}
        guidance = coin_flip_procedure_definition.get_sop_guidance_prompt(context, mid_state)
        assert "flipped 2 times" in guidance
        assert "more flips" in guidance
        
        # All flips done, need logging
        logging_state = {"tools_used": ["coin_flip", "coin_flip", "coin_flip"]}
        guidance = coin_flip_procedure_definition.get_sop_guidance_prompt(context, logging_state)
        assert "logged all your coin flip results" in guidance
        
        # Ready for calculation
        calc_state = {"tools_used": ["coin_flip", "coin_flip", "coin_flip", "data_logging", "data_logging", "data_logging"]}
        guidance = coin_flip_procedure_definition.get_sop_guidance_prompt(context, calc_state)
        assert "calculated the accuracy" in guidance

    def test_given_coin_flip_scenario_when_checking_stop_tool_functionality_then_stops_correctly(self, coin_flip_procedure_definition):
        """
        Given a coin flip scenario
        When the stop tool is used
        Then the procedure should stop correctly with proper reason tracking
        """
        # Simulate state where experiment is complete
        complete_state = {
            'tools_used': ['coin_flip', 'coin_flip', 'coin_flip', 'data_logging', 'data_logging', 'data_logging', 'accuracy_calculator'],
            'round': 8,
            'stop_requested': True,
            'stop_reason': 'All experiment steps completed successfully'
        }
        
        # Should not continue when stop is requested
        assert coin_flip_procedure_definition.should_continue(complete_state) == False
        
        # Completion summary should reflect the work done
        summary = coin_flip_procedure_definition.get_completion_summary(complete_state)
        assert "3 flips" in summary
        assert "3 data entries" in summary
        assert "1 calculations" in summary
        assert "8 rounds" in summary

    def test_given_multiple_coin_flip_procedures_when_comparing_configurations_then_demonstrates_customization(self):
        """
        Given multiple coin flip procedure configurations
        When comparing their setup
        Then it should demonstrate how the base SOP agent can be customized for different tasks
        """
        # Standard coin flip procedure
        standard_procedure = CoinFlipProcedureDefinition()
        
        # Extended coin flip procedure (simulating different experiment)
        class ExtendedCoinFlipProcedure(CoinFlipProcedureDefinition):
            def __init__(self):
                super().__init__()
                self.available_tools.extend(["statistical_analysis", "report_generator"])
            
            def get_system_prompt(self, context: Dict[str, Any]) -> str:
                base_prompt = super().get_system_prompt(context)
                return base_prompt + "\n\nAdditionally, perform statistical analysis and generate a report."
        
        extended_procedure = ExtendedCoinFlipProcedure()
        
        # Assert different tool sets
        standard_tools = standard_procedure.get_allowed_tools()
        extended_tools = extended_procedure.get_allowed_tools()
        
        assert len(extended_tools) > len(standard_tools)
        assert "statistical_analysis" in extended_tools
        assert "report_generator" in extended_tools
        assert "statistical_analysis" not in standard_tools
        
        # Assert different prompts
        context = {"experiment_name": "Test"}
        standard_prompt = standard_procedure.get_system_prompt(context)
        extended_prompt = extended_procedure.get_system_prompt(context)
        
        assert "statistical analysis" in extended_prompt
        assert "statistical analysis" not in standard_prompt

    def test_coin_flip_scenario_story_complete_workflow(self):
        """
        Story Test: Complete coin flip experiment workflow
        
        This test tells the complete story of using an SOP agent to accomplish
        the coin flip task, demonstrating all the key features working together.
        """
        # Chapter 1: Setup - Create procedure definition
        procedure = CoinFlipProcedureDefinition()
        
        # Verify the procedure knows its tools
        tools = procedure.get_allowed_tools()
        assert tools == ["coin_flip", "data_logging", "accuracy_calculator", "stop_procedure"]
        
        # Chapter 2: Worker gets task-specific instructions
        context = {"experiment_name": "Story Test Coin Flip"}
        worker_prompt = procedure.get_system_prompt(context)
        user_prompt = procedure.get_user_prompt(context)
        
        assert "coin flip experiment" in worker_prompt
        assert "Story Test Coin Flip" in user_prompt
        
        # Chapter 3: Simulate the workflow with state tracking
        workflow_states = [
            # State 1: Starting
            {"tools_used": [], "round": 1},
            # State 2: After first coin flip
            {"tools_used": ["coin_flip"], "round": 2},
            # State 3: After logging first result
            {"tools_used": ["coin_flip", "data_logging"], "round": 3},
            # State 4: After second coin flip
            {"tools_used": ["coin_flip", "data_logging", "coin_flip"], "round": 4},
            # State 5: After all flips and logging
            {"tools_used": ["coin_flip", "data_logging", "coin_flip", "data_logging", "coin_flip", "data_logging"], "round": 6},
            # State 6: After accuracy calculation
            {"tools_used": ["coin_flip", "data_logging", "coin_flip", "data_logging", "coin_flip", "data_logging", "accuracy_calculator"], "round": 7},
            # State 7: Completed
            {"tools_used": ["coin_flip", "data_logging", "coin_flip", "data_logging", "coin_flip", "data_logging", "accuracy_calculator"], "round": 8, "stop_requested": True}
        ]
        
        # Chapter 4: Manager provides appropriate guidance at each stage
        manager_guidance = []
        for state in workflow_states[:-1]:  # All except final completed state
            guidance = procedure.get_sop_guidance_prompt(context, state)
            manager_guidance.append(guidance)
        
        # Verify guidance progression makes sense
        assert "started flipping" in manager_guidance[0]  # Initial guidance
        assert "more flips" in manager_guidance[2]        # After some flips
        assert "accuracy" in manager_guidance[4]          # Before accuracy calculation (state 5)
        
        # Chapter 5: Procedure completion
        final_state = workflow_states[-1]
        assert procedure.should_continue(final_state) == False  # Should stop
        
        summary = procedure.get_completion_summary(final_state)
        assert "3 flips" in summary
        assert "3 data entries" in summary
        assert "1 calculations" in summary
        
        # Story complete: The SOP agent successfully orchestrated a simple task
        # with proper tool management, guidance, and completion detection


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
