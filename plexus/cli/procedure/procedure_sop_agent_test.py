"""
Tests for experiment-specific SOP Agent implementation.

These tests verify the ProcedureSOPAgent properly implements experiment
procedures using the general-purpose StandardOperatingProcedureAgent.
"""

import pytest
import asyncio
from unittest.mock import Mock, AsyncMock, patch
from types import SimpleNamespace

from .procedure_sop_agent import (
    ProcedureSOPAgent,
    ProcedureProcedureDefinition,
    ProcedureChatRecorderAdapter,
    run_sop_guided_procedure
)


class MockMCPServer:
    """Mock MCP server for procedure testing."""
    
    def connect(self, config):
        return MockMCPConnection()


class MockMCPConnection:
    """Mock MCP connection for procedure testing."""
    
    async def __aenter__(self):
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        pass


class TestProcedureProcedureDefinition:
    """Test experiment-specific procedure definition."""
    
    def test_procedure_procedure_definition_initialization(self):
        """Test ProcedureProcedureDefinition initializes correctly."""
        procedure_def = ProcedureProcedureDefinition()
        
        # Test that the hardcoded available tools are returned
        available_tools = procedure_def.get_allowed_tools()
        assert "plexus_feedback_find" in available_tools
        assert "upsert_procedure_node" in available_tools
        assert "get_procedure_info" in available_tools
        assert "stop_procedure" in available_tools
        # Should have exactly 4 tools (simplified from dynamic scoping)
        assert len(available_tools) == 4
    
    def test_procedure_prompts_load_from_yaml_config(self):
        """Test that procedure procedure definition loads prompts from YAML configuration."""
        procedure_def = ProcedureProcedureDefinition()
        
        # Set up mock procedure config with all required prompts
        mock_config = {
            'prompts': {
                'worker_system_prompt': 'Test worker system prompt with {procedure_id}',
                'worker_user_prompt': 'Test worker user prompt for {scorecard_name} → {score_name}',
                'manager_system_prompt': 'Test manager system prompt for coaching',
                'manager_user_prompt': 'Welcome to procedure {procedure_id} for {scorecard_name} → {score_name}'
            }
        }
        procedure_def.experiment_config = mock_config
        
        context = {
            "procedure_id": "test-123",
            "scorecard_name": "TestCard", 
            "score_name": "TestScore"
        }
        state_data = {"round": 1, "tools_used": ["test_tool"]}
        
        # Test all prompt methods
        system_prompt = procedure_def.get_system_prompt(context)
        user_prompt = procedure_def.get_user_prompt(context)
        manager_system_prompt = procedure_def.get_sop_guidance_prompt(context, state_data)
        manager_user_prompt = procedure_def.get_manager_user_prompt(context, state_data)
        
        # Verify prompts load correctly
        assert isinstance(system_prompt, str)
        assert isinstance(user_prompt, str)
        assert isinstance(manager_system_prompt, str)
        assert isinstance(manager_user_prompt, str)
        assert len(system_prompt) > 0
        assert len(user_prompt) > 0
        assert len(manager_system_prompt) > 0
        assert len(manager_user_prompt) > 0
        
        # Verify template variable substitution
        assert "test-123" in system_prompt
        assert "TestCard" in user_prompt
        assert "TestScore" in user_prompt
        assert "test-123" in manager_user_prompt
        assert "TestCard" in manager_user_prompt
        assert "TestScore" in manager_user_prompt
    
    def test_get_manager_user_prompt_error_cases(self):
        """Test error handling for get_manager_user_prompt method."""
        procedure_def = ProcedureProcedureDefinition()
        context = {"procedure_id": "test", "scorecard_name": "Test", "score_name": "Test"}
        
        # Test missing procedure config
        with pytest.raises(ValueError, match="Procedure configuration must include 'prompts' section"):
            procedure_def.get_manager_user_prompt(context)
        
        # Test missing prompts section
        procedure_def.experiment_config = {}
        with pytest.raises(ValueError, match="Procedure configuration must include 'prompts' section"):
            procedure_def.get_manager_user_prompt(context)
        
        # Test missing manager_user_prompt in prompts section
        procedure_def.experiment_config = {'prompts': {'worker_system_prompt': 'test'}}
        with pytest.raises(ValueError, match="Procedure configuration missing 'manager_user_prompt'"):
            procedure_def.get_manager_user_prompt(context)
    
    def test_template_variable_processing(self):
        """Test template variable processing in prompts."""
        procedure_def = ProcedureProcedureDefinition()
        
        # Set up config with template variables
        procedure_def.experiment_config = {
            'prompts': {
                'manager_user_prompt': 'Procedure {procedure_id} for {scorecard_name} round {round} tools {tools_used}'
            }
        }
        
        context = {"procedure_id": "exp-456", "scorecard_name": "TestCard"}
        state_data = {"round": 5, "tools_used": ["tool1", "tool2"]}
        
        result = procedure_def.get_manager_user_prompt(context, state_data)
        
        # Verify all template variables are substituted
        assert "exp-456" in result
        assert "TestCard" in result
        assert "5" in result
        assert "['tool1', 'tool2']" in result
    
    def test_missing_template_variables_handled_gracefully(self):
        """Test that missing template variables are handled gracefully."""
        procedure_def = ProcedureProcedureDefinition()
        
        procedure_def.experiment_config = {
            'prompts': {
                'manager_user_prompt': 'Procedure {procedure_id} has {missing_variable} round {round}'
            }
        }
        
        context = {"procedure_id": "exp-789"}
        state_data = {"round": 3}
        
        # Should not raise error, should handle missing variables gracefully
        result = procedure_def.get_manager_user_prompt(context, state_data)
        # Current behavior: returns template as-is when any variable is missing
        # This is a limitation of the current implementation using .format(**template_vars)
        assert result == 'Procedure {procedure_id} has {missing_variable} round {round}'
        assert "{missing_variable}" in result
    
    def test_realistic_experiment_context_variables(self):
        """Test template processing with realistic experiment context variables that match actual procedure execution."""
        procedure_def = ProcedureProcedureDefinition()
        
        # Use realistic YAML prompt template that matches what's actually used
        realistic_template = """Current Experiment Context:

Experiment ID: {experiment_id}
Scorecard: {scorecard_name}
Score: {score_name}

Current Score Configuration (Champion Version):
{current_score_config}

Performance Analysis Summary:
{feedback_summary}"""
        
        procedure_def.experiment_config = {
            'prompts': {
                'worker_user_prompt': realistic_template
            }
        }
        
        # Use realistic context that matches what ProcedureService.run_procedure creates
        realistic_context = {
            'procedure_id': 'proc-abc123def456',
            'account_id': 'acc-123',
            'scorecard_id': 'scorecard-456',
            'score_id': 'score-789',
            'scorecard_name': 'Sales Performance Scorecard',
            'score_name': 'DNC Requested Adherence',
            'node_count': 5,
            'version_count': 3,
            'current_score_config': 'logic: "feedback.dnc_requested == true"\nweight: 1.0\nthreshold: 0.95',
            'feedback_summary': 'Analysis of 847 feedback items shows 23% non-compliance with DNC protocols.',
            'feedback_alignment_docs': [],
            'score_yaml_format_docs': [],
            'existing_nodes': []
        }
        
        result = procedure_def.get_user_prompt(realistic_context)
        
        # Verify all critical variables are properly interpolated
        assert 'proc-abc123def456' in result  # experiment_id should map to procedure_id
        assert 'Sales Performance Scorecard' in result
        assert 'DNC Requested Adherence' in result
        assert 'logic: "feedback.dnc_requested == true"' in result
        assert 'Analysis of 847 feedback items' in result
        
        # Ensure no template variables remain unsubstituted
        assert '{experiment_id}' not in result
        assert '{scorecard_name}' not in result
        assert '{score_name}' not in result
        assert '{current_score_config}' not in result
        assert '{feedback_summary}' not in result
    
    def test_experiment_id_backward_compatibility_mapping(self):
        """Test that {experiment_id} correctly maps to procedure_id for backward compatibility."""
        procedure_def = ProcedureProcedureDefinition()
        
        # Template using both old and new variable names
        template_mixed = "Procedure: {procedure_id}, Experiment: {experiment_id}, Scorecard: {scorecard_name}"
        
        procedure_def.experiment_config = {
            'prompts': {
                'manager_system_prompt': template_mixed
            }
        }
        
        context = {
            'procedure_id': 'test-procedure-123',
            'scorecard_name': 'Test Scorecard'
        }
        
        result = procedure_def.get_sop_guidance_prompt(context, {})
        
        # Both variables should resolve to the same procedure_id value
        assert 'Procedure: test-procedure-123' in result
        assert 'Experiment: test-procedure-123' in result
        assert 'Scorecard: Test Scorecard' in result
        
        # No unsubstituted template variables
        assert '{procedure_id}' not in result
        assert '{experiment_id}' not in result
        assert '{scorecard_name}' not in result
    
    def test_template_with_only_experiment_id_variable(self):
        """Test that templates using only {experiment_id} work correctly."""
        procedure_def = ProcedureProcedureDefinition()
        
        template_legacy = "Working on experiment {experiment_id} for {scorecard_name}"
        
        procedure_def.experiment_config = {
            'prompts': {
                'worker_system_prompt': template_legacy
            }
        }
        
        context = {
            'procedure_id': 'legacy-proc-456',
            'scorecard_name': 'Legacy Scorecard'
        }
        
        result = procedure_def.get_system_prompt(context)
        
        # experiment_id should be mapped from procedure_id
        assert 'Working on experiment legacy-proc-456' in result
        assert 'for Legacy Scorecard' in result
        
        # No unsubstituted variables
        assert '{experiment_id}' not in result
        assert '{scorecard_name}' not in result
    
    def test_end_to_end_template_processing_with_realistic_yaml(self):
        """Integration test that verifies template processing works end-to-end with realistic YAML config."""
        
        # Realistic YAML config that includes template variables
        realistic_yaml_config = """
prompts:
  worker_system_prompt: |
    You are an AI agent analyzing classification scoring procedures.
    
    Working on: {scorecard_name} - {score_name}
    Procedure ID: {experiment_id}
    
  worker_user_prompt: |
    Current Experiment Context:
    
    Experiment ID: {experiment_id}
    Scorecard: {scorecard_name}
    Score: {score_name}
    
    Current Score Configuration:
    {current_score_config}
    
    Performance Analysis Summary:
    {feedback_summary}
    
    Please analyze this configuration and provide recommendations.
    
  manager_system_prompt: |
    You are a procedure manager overseeing AI analysis of {scorecard_name}.
    Current procedure: {experiment_id}
    
  manager_user_prompt: |
    Review the analysis for {scorecard_name} - {score_name} procedure {experiment_id}.
    
max_total_rounds: 100
"""
        
        # Realistic experiment context matching actual procedure execution
        experiment_context = {
            'procedure_id': 'proc-integration-test-789',
            'account_id': 'acc-test-123',
            'scorecard_id': 'scorecard-test-456', 
            'score_id': 'score-test-789',
            'scorecard_name': 'Customer Service Quality',
            'score_name': 'Response Time Compliance',
            'node_count': 3,
            'version_count': 2,
            'current_score_config': 'logic: "response_time_seconds <= 30"\nweight: 0.8\nthreshold: 0.9',
            'feedback_summary': 'Analysis of 1,205 interactions shows 67% compliance with 30-second response time target.',
            'feedback_alignment_docs': [],
            'score_yaml_format_docs': [],
            'existing_nodes': []
        }
        
        # Create ProcedureSOPAgent and set it up
        procedure_agent = ProcedureSOPAgent(
            procedure_id=experiment_context['procedure_id'],
            mcp_server=None,  # Not needed for this test
            client=None,
            openai_api_key=None,
            experiment_context=experiment_context,
            model_config=None
        )
        
        # Set up with the realistic YAML
        # Note: setup() is async but we're testing the sync parts here
        import yaml
        config = yaml.safe_load(realistic_yaml_config)
        procedure_agent.procedure_definition.experiment_config = config
        
        # Test all prompt methods with template processing
        system_prompt = procedure_agent.procedure_definition.get_system_prompt(experiment_context)
        user_prompt = procedure_agent.procedure_definition.get_user_prompt(experiment_context)
        manager_prompt = procedure_agent.procedure_definition.get_sop_guidance_prompt(experiment_context, {})
        manager_user_prompt = procedure_agent.procedure_definition.get_manager_user_prompt(experiment_context, {})
        
        # Verify all prompts have proper template interpolation
        # Check each prompt individually since they have different content
        
        # System prompt should have scorecard_name, score_name, and experiment_id
        assert 'Customer Service Quality' in system_prompt
        assert 'Response Time Compliance' in system_prompt
        assert 'proc-integration-test-789' in system_prompt
        assert '{experiment_id}' not in system_prompt
        assert '{scorecard_name}' not in system_prompt
        assert '{score_name}' not in system_prompt
        
        # User prompt should have all the context variables
        assert 'Customer Service Quality' in user_prompt
        assert 'Response Time Compliance' in user_prompt
        assert 'proc-integration-test-789' in user_prompt
        assert 'logic: "response_time_seconds <= 30"' in user_prompt
        assert 'Analysis of 1,205 interactions' in user_prompt
        assert '{experiment_id}' not in user_prompt
        assert '{scorecard_name}' not in user_prompt
        assert '{score_name}' not in user_prompt
        assert '{current_score_config}' not in user_prompt
        assert '{feedback_summary}' not in user_prompt
        
        # Manager system prompt only has scorecard_name and experiment_id (not score_name)
        assert 'Customer Service Quality' in manager_prompt
        assert 'proc-integration-test-789' in manager_prompt
        assert '{experiment_id}' not in manager_prompt
        assert '{scorecard_name}' not in manager_prompt
        
        # Manager user prompt has scorecard_name, score_name, and experiment_id
        assert 'Customer Service Quality' in manager_user_prompt
        assert 'Response Time Compliance' in manager_user_prompt
        assert 'proc-integration-test-789' in manager_user_prompt
        assert '{experiment_id}' not in manager_user_prompt
        assert '{scorecard_name}' not in manager_user_prompt
        assert '{score_name}' not in manager_user_prompt
    
    def test_template_mismatch_detection_regression_test(self):
        """Regression test to catch the specific template variable mismatch issue that was reported."""
        procedure_def = ProcedureProcedureDefinition()
        
        # Simulate the exact scenario that caused the bug:
        # - YAML template contains {experiment_id}
        # - Context provides procedure_id but no experiment_id mapping
        buggy_template = """Current Experiment Context:



Experiment ID: {experiment_id}

Scorecard: {scorecard_name}

Score: {score_name}


Current Score Configuration (Champion Version):


{current_score_config}

Performance Analysis Summary:


{feedback_summary}"""
        
        procedure_def.experiment_config = {
            'prompts': {
                'worker_user_prompt': buggy_template
            }
        }
        
        # Context as it was originally provided (without experiment_id mapping)
        original_buggy_context = {
            'procedure_id': 'proc-test-123',  # This was procedure_id, not experiment_id
            'scorecard_name': 'Test Scorecard',
            'score_name': 'Test Score',
            'current_score_config': 'test config',
            'feedback_summary': 'test feedback'
        }
        
        # With the fix, this should work (experiment_id gets mapped from procedure_id)
        result = procedure_def.get_user_prompt(original_buggy_context)
        
        # Verify the bug is fixed - experiment_id should be interpolated
        assert 'Experiment ID: proc-test-123' in result
        assert 'Scorecard: Test Scorecard' in result
        assert 'Score: Test Score' in result
        assert 'test config' in result
        assert 'test feedback' in result
        
        # Most importantly, no template variables should remain unsubstituted
        assert '{experiment_id}' not in result, "REGRESSION: experiment_id template variable not substituted!"
        assert '{scorecard_name}' not in result
        assert '{score_name}' not in result
        assert '{current_score_config}' not in result
        assert '{feedback_summary}' not in result
    
    def test_template_variable_logging_helps_debugging(self):
        """Test that template processing works correctly with debug info available."""
        procedure_def = ProcedureProcedureDefinition()
        
        # Test that the template processing method can be called successfully
        # and that it provides useful error information when variables are missing
        procedure_def.experiment_config = {
            'prompts': {
                'worker_system_prompt': 'Test {procedure_id} with {scorecard_name} missing {undefined_var}'
            }
        }
        
        context = {
            'procedure_id': 'debug-test-456',
            'scorecard_name': 'Debug Scorecard'
        }
        
        # This should handle the missing variable gracefully and return the template as-is
        result = procedure_def.get_system_prompt(context)
        
        # The result should be the original template since undefined_var is missing
        expected = 'Test {procedure_id} with {scorecard_name} missing {undefined_var}'
        assert result == expected, f"Expected graceful handling of missing variables, got: {result}"
        
        # Test with all variables present
        procedure_def.experiment_config = {
            'prompts': {
                'worker_system_prompt': 'Test {procedure_id} with {scorecard_name}'
            }
        }
        
        result = procedure_def.get_system_prompt(context)
        assert result == 'Test debug-test-456 with Debug Scorecard'
    
    def test_procedure_continuation_criteria(self):
        """Test experiment-specific continuation logic."""
        procedure_def = ProcedureProcedureDefinition()
        
        # Should continue for normal rounds (worker agent controls stopping)
        state_early = {"round": 5}
        assert procedure_def.should_continue(state_early) == True
        
        # Should continue even with nodes created (worker decides when to stop)
        state_with_nodes = {"round": 10}
        assert procedure_def.should_continue(state_with_nodes) == True
        
        # Should continue until worker explicitly stops
        state_normal = {"round": 25}
        assert procedure_def.should_continue(state_normal) == True
        
        # Should continue until safety limit (round >= 500)
        state_below_safety = {"round": 105}
        assert procedure_def.should_continue(state_below_safety) == True
        
        # Should stop only at safety limit (round >= 500)
        state_safety = {"round": 500}
        assert procedure_def.should_continue(state_safety) == False
    
    def test_procedure_completion_summary(self):
        """Test procedure completion summary generation."""
        procedure_def = ProcedureProcedureDefinition()
        
        # No procedure nodes created
        state_no_nodes = {"tools_used": ["plexus_feedback_find"], "round": 10}
        summary = procedure_def.get_completion_summary(state_no_nodes)
        assert "no hypothesis nodes were created" in summary
        
        # One procedure node created
        state_one_node = {"tools_used": ["plexus_feedback_find", "upsert_procedure_node"], "round": 15}
        summary = procedure_def.get_completion_summary(state_one_node)
        assert "1 hypothesis node created" in summary
        
        # Multiple procedure nodes created (3 upsert_procedure_node calls)
        state_multiple_nodes = {"tools_used": ["plexus_feedback_find", "upsert_procedure_node", "upsert_procedure_node", "upsert_procedure_node"], "round": 25}
        summary = procedure_def.get_completion_summary(state_multiple_nodes)
        assert "3 hypothesis nodes created" in summary


class TestProcedureSOPAgent:
    """Test the ProcedureSOPAgent wrapper."""
    
    def test_procedure_sop_agent_initialization(self):
        """Test ProcedureSOPAgent initializes with experiment-specific components."""
        mcp_server = MockMCPServer()
        experiment_context = {"scorecard_name": "TestCard", "score_name": "TestScore"}
        
        experiment_agent = ProcedureSOPAgent(
            procedure_id="test_exp",
            mcp_server=mcp_server,
            experiment_context=experiment_context
        )
        
        assert experiment_agent.procedure_id == "test_exp"
        assert experiment_agent.experiment_context == experiment_context
        assert isinstance(experiment_agent.procedure_definition, ProcedureProcedureDefinition)
    
    @pytest.mark.asyncio
    async def test_procedure_setup_creates_components(self):
        """Test procedure setup creates chat recorder (simplified - no flow manager)."""
        mcp_server = MockMCPServer()
        mock_client = Mock()
        experiment_context = {"scorecard_name": "TestCard"}
        
        experiment_agent = ProcedureSOPAgent(
            procedure_id="test_exp",
            mcp_server=mcp_server,
            client=mock_client,
            experiment_context=experiment_context
        )
        
        experiment_yaml = """
        class: "BeamSearch"
        exploration: "Analyze feedback data"
        max_total_rounds: 500
        """
        
        # Mock the StandardOperatingProcedureAgent class itself
        with patch('plexus.cli.procedure.procedure_sop_agent.StandardOperatingProcedureAgent') as mock_sop_agent_class:
            mock_sop_agent = Mock()
            mock_sop_agent.setup = AsyncMock(return_value=True)
            mock_sop_agent_class.return_value = mock_sop_agent
            
            setup_result = await experiment_agent.setup(experiment_yaml)
            
            assert setup_result == True
            # No flow manager in simplified version
            assert isinstance(experiment_agent.chat_recorder, ProcedureChatRecorderAdapter)
            mock_sop_agent.setup.assert_called_once_with(experiment_yaml)
    
    @pytest.mark.asyncio
    async def test_procedure_execution_delegates_to_sop_agent(self):
        """Test procedure execution delegates to underlying SOP Agent."""
        mcp_server = MockMCPServer()
        experiment_agent = ProcedureSOPAgent("test_exp", mcp_server)
        
        # Set up mock procedure config for the procedure definition
        mock_config = {
            'prompts': {
                'worker_system_prompt': 'Test worker system prompt',
                'worker_user_prompt': 'Test worker user prompt',
                'manager_system_prompt': 'Test manager system prompt',
                'manager_user_prompt': 'Test manager user prompt'
            }
        }
        experiment_agent.procedure_definition.experiment_config = mock_config
        
        # Mock SOP Agent execution
        mock_sop_agent = Mock()
        mock_sop_agent.execute_procedure = AsyncMock(return_value={
            "success": True,
            "rounds_completed": 5,
            "tools_used": ["plexus_feedback_analysis", "upsert_procedure_node", "upsert_procedure_node"],
            "completion_summary": "Test completed"
        })
        experiment_agent.sop_agent = mock_sop_agent
        
        result = await experiment_agent.execute_sop_guided_procedure()
        
        assert result["success"] == True
        assert result["procedure_id"] == "test_exp"
        assert result["nodes_created"] == 2  # Two upsert_procedure_node calls
        assert result["rounds_completed"] == 5
        assert "plexus_feedback_analysis" in result["tool_names"]
        
        mock_sop_agent.execute_procedure.assert_called_once()
    
    def test_backward_compatibility_methods(self):
        """Test that backward compatibility methods work."""
        mcp_server = MockMCPServer()
        experiment_context = {"scorecard_name": "TestCard"}
        
        experiment_agent = ProcedureSOPAgent(
            procedure_id="test_exp",
            mcp_server=mcp_server,
            experiment_context=experiment_context
        )
        
        # Set up mock procedure config for the procedure definition
        mock_config = {
            'prompts': {
                'worker_system_prompt': 'Test worker system prompt',
                'worker_user_prompt': 'Test worker user prompt',
                'manager_system_prompt': 'Test manager system prompt',
                'manager_user_prompt': 'Test manager user prompt'
            }
        }
        experiment_agent.procedure_definition.experiment_config = mock_config
        
        # These methods should work for backward compatibility
        exploration_prompt = experiment_agent.get_exploration_prompt()
        system_prompt = experiment_agent.get_system_prompt()
        user_prompt = experiment_agent.get_user_prompt()
        
        assert isinstance(exploration_prompt, str)
        assert isinstance(system_prompt, str)
        assert isinstance(user_prompt, str)


class TestProcedureSOPIntegration:
    """Integration tests for procedure SOP Agent workflow."""
    
    @pytest.mark.asyncio
    async def test_run_sop_guided_procedure_function(self):
        """Test the run_sop_guided_procedure convenience function."""
        experiment_yaml = """
        class: "BeamSearch"
        exploration: "Test experiment"
        """
        mcp_server = MockMCPServer()
        experiment_context = {"scorecard_name": "TestCard", "score_name": "TestScore"}
        
        # Mock the ProcedureSOPAgent to avoid complex setup
        with patch('plexus.cli.procedure.procedure_sop_agent.ProcedureSOPAgent') as mock_agent_class:
            mock_agent = Mock()
            mock_agent.setup = AsyncMock(return_value=True)
            mock_agent.execute_sop_guided_procedure = AsyncMock(return_value={
                "success": True,
                "procedure_id": "test_func_exp",
                "nodes_created": 2
            })
            mock_agent_class.return_value = mock_agent
            
            result = await run_sop_guided_procedure(
                procedure_id="test_func_exp",
                experiment_yaml=experiment_yaml,
                mcp_server=mcp_server,
                experiment_context=experiment_context
            )
            
            assert result["success"] == True
            assert result["procedure_id"] == "test_func_exp"
            assert result["nodes_created"] == 2
            
            # Verify ProcedureSOPAgent was created and used properly
            mock_agent_class.assert_called_once()
            mock_agent.setup.assert_called_once_with(experiment_yaml)
            mock_agent.execute_sop_guided_procedure.assert_called_once()


class TestProcedureAdapters:
    """Test the adapter classes that bridge procedure components to SOP Agent."""
    
    # Removed test_procedure_flow_manager_adapter - using simplified multi-agent ReAct loop
    
    @pytest.mark.asyncio
    async def test_procedure_chat_recorder_adapter(self):
        """Test ProcedureChatRecorderAdapter wraps ProcedureChatRecorder."""
        mock_client = Mock()
        
        adapter = ProcedureChatRecorderAdapter(mock_client, "test_exp", None)
        
        # Mock the underlying ProcedureChatRecorder
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


# Story test that demonstrates the procedure workflow
@pytest.mark.asyncio
async def test_procedure_sop_agent_story():
    """
    STORY: ProcedureSOPAgent executes complete procedure workflow
    
    This story demonstrates:
    1. Procedure setup with YAML configuration
    2. SOP-guided execution through procedure phases
    3. Tool usage tracking and node creation
    4. Proper completion with procedure results
    """
    print("\n🧪 Starting Procedure SOP Agent Story...")
    
    # Arrange: Set up procedure components
    experiment_yaml = """
    class: "BeamSearch"
    exploration: |
      Analyze feedback data to understand scoring errors and create hypotheses.
    """
    
    experiment_context = {
        "procedure_id": "story_exp",
        "scorecard_name": "StoryCard", 
        "score_name": "StoryScore"
    }
    
    mcp_server = MockMCPServer()
    
    # Mock the underlying SOP Agent execution to tell our story
    with patch('plexus.cli.procedure.procedure_sop_agent.StandardOperatingProcedureAgent') as mock_sop_agent_class:
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
                "upsert_procedure_node",
                "upsert_procedure_node"
            ],
            "completion_summary": "Procedure completed with 2 hypothesis nodes",
            "final_state": {"nodes_created": 2}
        })
        mock_sop_agent_class.return_value = mock_sop_agent
        
        # Act: Execute the procedure story
        experiment_agent = ProcedureSOPAgent(
            procedure_id="story_exp",
            mcp_server=mcp_server,
            experiment_context=experiment_context
        )
        
        # Set up mock procedure config for the story
        mock_config = {
            'prompts': {
                'worker_system_prompt': 'Story worker system prompt',
                'worker_user_prompt': 'Story worker user prompt',
                'manager_system_prompt': 'Story manager system prompt',
                'manager_user_prompt': 'Story manager user prompt'
            }
        }
        experiment_agent.procedure_definition.experiment_config = mock_config
        
        setup_success = await experiment_agent.setup(experiment_yaml)
        assert setup_success == True
        
        # Since we mocked the SOP agent execution, we need to ensure the real
        # prompt methods are still accessible during result processing
        with patch.object(experiment_agent.procedure_definition, 'get_system_prompt', return_value='Mocked system prompt'), \
             patch.object(experiment_agent.procedure_definition, 'get_user_prompt', return_value='Mocked user prompt'):
            
            result = await experiment_agent.execute_sop_guided_procedure()
        
        # Assert: Verify the story unfolded correctly
        assert result["success"] == True
        assert result["procedure_id"] == "story_exp"
        assert result["nodes_created"] == 2
        assert result["rounds_completed"] == 8
        
        # Verify procedure tools were used
        expected_tools = ["plexus_feedback_analysis", "plexus_feedback_find", "plexus_item_info", "upsert_procedure_node"]
        for tool in expected_tools:
            assert tool in result["tool_names"]
        
        print(f"✅ Story completed: {result['nodes_created']} nodes created in {result['rounds_completed']} rounds")
        print(f"🔧 Tools used: {result['tool_names']}")
        print("🎯 Procedure SOP Agent successfully orchestrated hypothesis generation")


if __name__ == "__main__":
    pytest.main([__file__])
