"""
Tests for experiment-specific SOP Agent implementation.

These tests verify the ExperimentSOPAgent properly implements experiment
procedures using the general-purpose StandardOperatingProcedureAgent.
"""

import pytest
import asyncio
from unittest.mock import Mock, AsyncMock, patch
from types import SimpleNamespace

from .experiment_sop_agent import (
    ExperimentSOPAgent,
    ExperimentProcedureDefinition,
    ExperimentFlowManagerAdapter,
    ExperimentChatRecorderAdapter,
    run_sop_guided_experiment
)


class MockMCPServer:
    """Mock MCP server for experiment testing."""
    
    def connect(self, config):
        return MockMCPConnection()


class MockMCPConnection:
    """Mock MCP connection for experiment testing."""
    
    async def __aenter__(self):
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        pass


class TestExperimentProcedureDefinition:
    """Test experiment-specific procedure definition."""
    
    def test_experiment_procedure_definition_initialization(self):
        """Test ExperimentProcedureDefinition initializes correctly."""
        procedure_def = ExperimentProcedureDefinition()
        
        # Test that the hardcoded available tools are returned
        available_tools = procedure_def.get_allowed_tools()
        assert "plexus_feedback_find" in available_tools
        assert "create_experiment_node" in available_tools
        assert "stop_procedure" in available_tools
        # Should have exactly 3 tools (simplified from dynamic scoping)
        assert len(available_tools) == 3
    
    def test_experiment_prompts_delegate_to_experiment_prompts_class(self):
        """Test that experiment procedure definition uses ExperimentPrompts."""
        procedure_def = ExperimentProcedureDefinition()
        context = {"scorecard_name": "TestCard", "score_name": "TestScore"}
        
        system_prompt = procedure_def.get_system_prompt(context)
        user_prompt = procedure_def.get_user_prompt(context)
        
        # These should delegate to ExperimentPrompts
        assert isinstance(system_prompt, str)
        assert isinstance(user_prompt, str)
        assert len(system_prompt) > 0
        assert len(user_prompt) > 0
    
    def test_experiment_continuation_criteria(self):
        """Test experiment-specific continuation logic."""
        procedure_def = ExperimentProcedureDefinition()
        
        # Should continue for normal rounds (worker agent controls stopping)
        state_early = {"round": 5}
        assert procedure_def.should_continue(state_early) == True
        
        # Should continue even with nodes created (worker decides when to stop)
        state_with_nodes = {"round": 10}
        assert procedure_def.should_continue(state_with_nodes) == True
        
        # Should continue until worker explicitly stops
        state_normal = {"round": 25}
        assert procedure_def.should_continue(state_normal) == True
        
        # Should stop only at safety limit (round >= 100)
        state_safety = {"round": 105}
        assert procedure_def.should_continue(state_safety) == False
    
    def test_experiment_completion_summary(self):
        """Test experiment completion summary generation."""
        procedure_def = ExperimentProcedureDefinition()
        
        # No experiment nodes created
        state_no_nodes = {"tools_used": ["plexus_feedback_find"], "round": 10}
        summary = procedure_def.get_completion_summary(state_no_nodes)
        assert "no hypothesis nodes were created" in summary
        
        # One experiment node created
        state_one_node = {"tools_used": ["plexus_feedback_find", "create_experiment_node"], "round": 15}
        summary = procedure_def.get_completion_summary(state_one_node)
        assert "1 hypothesis node created" in summary
        
        # Multiple experiment nodes created (3 create_experiment_node calls)
        state_multiple_nodes = {"tools_used": ["plexus_feedback_find", "create_experiment_node", "create_experiment_node", "create_experiment_node"], "round": 25}
        summary = procedure_def.get_completion_summary(state_multiple_nodes)
        assert "3 hypothesis nodes created" in summary


class TestExperimentSOPAgent:
    """Test the ExperimentSOPAgent wrapper."""
    
    def test_experiment_sop_agent_initialization(self):
        """Test ExperimentSOPAgent initializes with experiment-specific components."""
        mcp_server = MockMCPServer()
        experiment_context = {"scorecard_name": "TestCard", "score_name": "TestScore"}
        
        experiment_agent = ExperimentSOPAgent(
            experiment_id="test_exp",
            mcp_server=mcp_server,
            experiment_context=experiment_context
        )
        
        assert experiment_agent.experiment_id == "test_exp"
        assert experiment_agent.experiment_context == experiment_context
        assert isinstance(experiment_agent.procedure_definition, ExperimentProcedureDefinition)
    
    @pytest.mark.asyncio
    async def test_experiment_setup_creates_components(self):
        """Test experiment setup creates flow manager and chat recorder."""
        mcp_server = MockMCPServer()
        mock_client = Mock()
        experiment_context = {"scorecard_name": "TestCard"}
        
        experiment_agent = ExperimentSOPAgent(
            experiment_id="test_exp",
            mcp_server=mcp_server,
            client=mock_client,
            experiment_context=experiment_context
        )
        
        experiment_yaml = """
        class: "BeamSearch"
        exploration: "Analyze feedback data"
        """
        
        # Mock the StandardOperatingProcedureAgent class itself
        with patch('plexus.cli.experiment.experiment_sop_agent.StandardOperatingProcedureAgent') as mock_sop_agent_class:
            mock_sop_agent = Mock()
            mock_sop_agent.setup = AsyncMock(return_value=True)
            mock_sop_agent_class.return_value = mock_sop_agent
            
            setup_result = await experiment_agent.setup(experiment_yaml)
            
            assert setup_result == True
            assert isinstance(experiment_agent.flow_manager, ExperimentFlowManagerAdapter)
            assert isinstance(experiment_agent.chat_recorder, ExperimentChatRecorderAdapter)
            mock_sop_agent.setup.assert_called_once_with(experiment_yaml)
    
    @pytest.mark.asyncio
    async def test_experiment_execution_delegates_to_sop_agent(self):
        """Test experiment execution delegates to underlying SOP Agent."""
        mcp_server = MockMCPServer()
        experiment_agent = ExperimentSOPAgent("test_exp", mcp_server)
        
        # Mock SOP Agent execution
        mock_sop_agent = Mock()
        mock_sop_agent.execute_procedure = AsyncMock(return_value={
            "success": True,
            "rounds_completed": 5,
            "tools_used": ["plexus_feedback_analysis", "create_experiment_node", "create_experiment_node"],
            "completion_summary": "Test completed"
        })
        experiment_agent.sop_agent = mock_sop_agent
        
        result = await experiment_agent.execute_sop_guided_experiment()
        
        assert result["success"] == True
        assert result["experiment_id"] == "test_exp"
        assert result["nodes_created"] == 2  # Two create_experiment_node calls
        assert result["rounds_completed"] == 5
        assert "plexus_feedback_analysis" in result["tool_names"]
        
        mock_sop_agent.execute_procedure.assert_called_once()
    
    def test_backward_compatibility_methods(self):
        """Test that backward compatibility methods work."""
        mcp_server = MockMCPServer()
        experiment_context = {"scorecard_name": "TestCard"}
        
        experiment_agent = ExperimentSOPAgent(
            experiment_id="test_exp",
            mcp_server=mcp_server,
            experiment_context=experiment_context
        )
        
        # These methods should work for backward compatibility
        exploration_prompt = experiment_agent.get_exploration_prompt()
        system_prompt = experiment_agent.get_system_prompt()
        user_prompt = experiment_agent.get_user_prompt()
        
        assert isinstance(exploration_prompt, str)
        assert isinstance(system_prompt, str)
        assert isinstance(user_prompt, str)


class TestExperimentSOPIntegration:
    """Integration tests for experiment SOP Agent workflow."""
    
    @pytest.mark.asyncio
    async def test_run_sop_guided_experiment_function(self):
        """Test the run_sop_guided_experiment convenience function."""
        experiment_yaml = """
        class: "BeamSearch"
        exploration: "Test experiment"
        """
        mcp_server = MockMCPServer()
        experiment_context = {"scorecard_name": "TestCard", "score_name": "TestScore"}
        
        # Mock the ExperimentSOPAgent to avoid complex setup
        with patch('plexus.cli.experiment.experiment_sop_agent.ExperimentSOPAgent') as mock_agent_class:
            mock_agent = Mock()
            mock_agent.setup = AsyncMock(return_value=True)
            mock_agent.execute_sop_guided_experiment = AsyncMock(return_value={
                "success": True,
                "experiment_id": "test_func_exp",
                "nodes_created": 2
            })
            mock_agent_class.return_value = mock_agent
            
            result = await run_sop_guided_experiment(
                experiment_id="test_func_exp",
                experiment_yaml=experiment_yaml,
                mcp_server=mcp_server,
                experiment_context=experiment_context
            )
            
            assert result["success"] == True
            assert result["experiment_id"] == "test_func_exp"
            assert result["nodes_created"] == 2
            
            # Verify ExperimentSOPAgent was created and used properly
            mock_agent_class.assert_called_once()
            mock_agent.setup.assert_called_once_with(experiment_yaml)
            mock_agent.execute_sop_guided_experiment.assert_called_once()


class TestExperimentAdapters:
    """Test the adapter classes that bridge experiment components to SOP Agent."""
    
    def test_experiment_flow_manager_adapter(self):
        """Test ExperimentFlowManagerAdapter wraps ConversationFlowManager."""
        experiment_config = {"conversation_flow": {"initial_state": "exploration"}}
        experiment_context = {"scorecard_name": "TestCard"}
        
        adapter = ExperimentFlowManagerAdapter(experiment_config, experiment_context)
        
        # Test adapter methods
        state = adapter.update_state(["plexus_feedback_analysis"], "test response")
        assert isinstance(state, dict)
        
        should_continue = adapter.should_continue()
        assert isinstance(should_continue, bool)
        
        guidance = adapter.get_next_guidance()
        # Guidance could be None or string
        assert guidance is None or isinstance(guidance, str)
        
        summary = adapter.get_completion_summary()
        assert isinstance(summary, str)
    
    @pytest.mark.asyncio
    async def test_experiment_chat_recorder_adapter(self):
        """Test ExperimentChatRecorderAdapter wraps ExperimentChatRecorder."""
        mock_client = Mock()
        
        adapter = ExperimentChatRecorderAdapter(mock_client, "test_exp", None)
        
        # Mock the underlying ExperimentChatRecorder
        adapter.experiment_chat_recorder = Mock()
        adapter.experiment_chat_recorder.start_session = AsyncMock(return_value="session_123")
        adapter.experiment_chat_recorder.record_message = AsyncMock(return_value="msg_456")
        adapter.experiment_chat_recorder.record_system_message = AsyncMock(return_value="sys_789")
        adapter.experiment_chat_recorder.end_session = AsyncMock(return_value=True)
        
        # Test adapter methods
        session_id = await adapter.start_session({"test": "context"})
        assert session_id == "session_123"
        
        msg_id = await adapter.record_message("USER", "test message", "MESSAGE")
        assert msg_id == "msg_456"
        
        sys_id = await adapter.record_system_message("system message")
        assert sys_id == "sys_789"
        
        end_result = await adapter.end_session("COMPLETED", "Test Session")
        assert end_result == True


# Story test that demonstrates the experiment workflow
@pytest.mark.asyncio
async def test_experiment_sop_agent_story():
    """
    STORY: ExperimentSOPAgent executes complete experiment workflow
    
    This story demonstrates:
    1. Experiment setup with YAML configuration
    2. SOP-guided execution through experiment phases
    3. Tool usage tracking and node creation
    4. Proper completion with experiment results
    """
    print("\n🧪 Starting Experiment SOP Agent Story...")
    
    # Arrange: Set up experiment components
    experiment_yaml = """
    class: "BeamSearch"
    exploration: |
      Analyze feedback data to understand scoring errors and create hypotheses.
    """
    
    experiment_context = {
        "experiment_id": "story_exp",
        "scorecard_name": "StoryCard", 
        "score_name": "StoryScore"
    }
    
    mcp_server = MockMCPServer()
    
    # Mock the underlying SOP Agent execution to tell our story
    with patch('plexus.cli.experiment.experiment_sop_agent.StandardOperatingProcedureAgent') as mock_sop_agent_class:
        mock_sop_agent = Mock()
        mock_sop_agent.setup = AsyncMock(return_value=True)
        mock_sop_agent.execute_procedure = AsyncMock(return_value={
            "success": True,
            "procedure_id": "story_exp",
            "rounds_completed": 8,
            "tools_used": [
                "plexus_feedback_analysis",
                "plexus_feedback_find", 
                "plexus_item_info",
                "create_experiment_node",
                "create_experiment_node"
            ],
            "completion_summary": "Experiment completed with 2 hypothesis nodes",
            "final_state": {"nodes_created": 2}
        })
        mock_sop_agent_class.return_value = mock_sop_agent
        
        # Act: Execute the experiment story
        experiment_agent = ExperimentSOPAgent(
            experiment_id="story_exp",
            mcp_server=mcp_server,
            experiment_context=experiment_context
        )
        
        setup_success = await experiment_agent.setup(experiment_yaml)
        assert setup_success == True
        
        result = await experiment_agent.execute_sop_guided_experiment()
        
        # Assert: Verify the story unfolded correctly
        assert result["success"] == True
        assert result["experiment_id"] == "story_exp"
        assert result["nodes_created"] == 2
        assert result["rounds_completed"] == 8
        
        # Verify experiment tools were used
        expected_tools = ["plexus_feedback_analysis", "plexus_feedback_find", "plexus_item_info", "create_experiment_node"]
        for tool in expected_tools:
            assert tool in result["tool_names"]
        
        print(f"✅ Story completed: {result['nodes_created']} nodes created in {result['rounds_completed']} rounds")
        print(f"🔧 Tools used: {result['tool_names']}")
        print("🎯 Experiment SOP Agent successfully orchestrated hypothesis generation")


if __name__ == "__main__":
    pytest.main([__file__])
