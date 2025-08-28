"""
Comprehensive end-to-end test for AI + MCP integration in experiments.

This test validates that:
1. MCP transport works with all Plexus tools
2. LangChain can successfully use MCP tools
3. AI models can interact with real Plexus data
4. The complete experiment run workflow functions properly
"""

import pytest
import asyncio
import os
import logging
from unittest.mock import Mock, AsyncMock, patch
from plexus.cli.experiment.service import ExperimentService
from plexus.cli.experiment.mcp_transport import create_experiment_mcp_server
from plexus.cli.experiment.experiment_sop_agent import run_sop_guided_experiment, ExperimentSOPAgent

logger = logging.getLogger(__name__)

# Mock OpenAI API key for testing
TEST_OPENAI_KEY = "test-key-123"

# Sample experiment YAML with enhanced exploration prompt
TEST_EXPERIMENT_YAML = """
class: "BeamSearch"

value: |
  local score = experiment_node.value.accuracy or 0
  local penalty = (experiment_node.value.cost or 0) * 0.1
  return score - penalty

exploration: |
  You are an AI assistant helping to test the Plexus MCP tool integration.
  
  Your task is to demonstrate that you can successfully use Plexus MCP tools by:
  1. Using the 'think' tool to plan your approach
  2. Listing available scorecards with 'plexus_scorecards_list'
  3. Getting detailed information about a scorecard
  4. Analyzing the results and providing insights
  
  Please use at least 3 different tools to show the integration is working properly.
  Be thorough and provide detailed responses about what you discover.

prompts:
  worker_system_prompt: |
    You are an AI assistant testing Plexus MCP tool integration.
    Use the available tools to demonstrate the integration works properly.
  worker_user_prompt: |
    Begin testing the MCP tool integration by using at least 3 different tools.
  manager_system_prompt: |
    You are a test manager overseeing MCP integration testing.
  manager_user_prompt: |
    Welcome to the MCP integration test session.
"""

class TestAIMCPIntegration:
    """Test class for AI + MCP integration."""
    
    @pytest.fixture
    def mock_client(self):
        """Create a mock client for testing."""
        client = Mock()
        client.execute = Mock()
        return client
    
    @pytest.fixture
    def experiment_service(self, mock_client):
        """Create an experiment service with mock client."""
        return ExperimentService(mock_client)
    
    @pytest.fixture
    def experiment_context(self):
        """Sample experiment context for testing."""
        return {
            'experiment_id': 'test-exp-123',
            'experiment_name': 'Test AI Integration Experiment',
            'scorecard_name': 'Test Scorecard',
            'score_name': 'Test Score',
            'node_count': 1,
            'version_count': 1,
            'options': {'enable_mcp': True}
        }
    
    @pytest.mark.asyncio
    async def test_mcp_server_creation_with_plexus_tools(self, experiment_context):
        """Test that MCP server can be created with all Plexus tools."""
        # Create MCP server with standard tool categories
        mcp_server = await create_experiment_mcp_server(
            experiment_context=experiment_context,
            plexus_tools=['scorecard', 'score', 'feedback', 'prediction']
        )
        
        assert mcp_server is not None
        assert hasattr(mcp_server, 'transport')
        
        # Check that tools are registered
        tools = mcp_server.transport.tools
        assert len(tools) > 0
        
        # Verify core tools are present
        tool_names = list(tools.keys())
        assert 'think' in tool_names
        assert 'get_experiment_context' in tool_names
        assert 'log_message' in tool_names
        
        # Verify some Plexus tools are present (will depend on availability)
        plexus_tool_names = [name for name in tools.keys() if name.startswith('plexus_')]
        assert len(plexus_tool_names) > 0
        
        logger.info(f"Successfully created MCP server with {len(tools)} tools")
        logger.info(f"Plexus tools available: {plexus_tool_names}")
    
    @pytest.mark.asyncio 
    async def test_mcp_tools_can_be_called(self, experiment_context):
        """Test that MCP tools can be called successfully."""
        mcp_server = await create_experiment_mcp_server(
            experiment_context=experiment_context,
            plexus_tools=['scorecard']
        )
        
        async with mcp_server.connect({'name': 'Test Client'}) as client:
            # Test core tools
            result = await client.call_tool('get_experiment_context', {})
            # MCP tools return wrapped results - extract content
            if 'content' in result and isinstance(result['content'], list) and len(result['content']) > 0:
                import json
                content_text = result['content'][0]['text']
                parsed_result = json.loads(content_text)
                assert 'experiment_context' in parsed_result
                assert parsed_result['experiment_context']['experiment_id'] == 'test-exp-123'
            else:
                # Fallback to direct access for backward compatibility
                assert 'experiment_id' in result
                assert result['experiment_id'] == 'test-exp-123'
            
            # Test think tool
            think_result = await client.call_tool('think', {
                'thought': 'Testing MCP tool integration'
            })
            # Handle wrapped MCP response
            if 'content' in think_result and isinstance(think_result['content'], list):
                content_text = think_result['content'][0]['text']
                # Think tool returns plain text, not JSON
                assert 'Thought processed' in content_text or 'thought' in content_text.lower()
            else:
                # Direct access fallback
                assert isinstance(think_result, (str, dict))
                if isinstance(think_result, str):
                    assert 'thought' in think_result.lower()
                else:
                    assert 'thought' in think_result
            
            # Test log message tool
            await client.call_tool('log_message', {
                'message': 'Test log from MCP tool',
                'level': 'info'
            })
            
            logger.info("Successfully called core MCP tools")
    
    @pytest.mark.asyncio
    async def test_langchain_adapter_loads_tools(self, experiment_context):
        """Test that LangChain adapter can load MCP tools."""
        from plexus.cli.experiment.experiment_sop_agent import LangChainMCPAdapter
        
        mcp_server = await create_experiment_mcp_server(
            experiment_context=experiment_context,
            plexus_tools=['scorecard', 'score']
        )
        
        async with mcp_server.connect({'name': 'LangChain Test'}) as client:
            adapter = LangChainMCPAdapter(client)
            tools = await adapter.load_tools()
            
            assert len(tools) > 0
            
            # Check tool properties
            for tool in tools:
                assert hasattr(tool, 'name')
                assert hasattr(tool, 'description')
                assert hasattr(tool, 'func')
                assert callable(tool.func)
            
            logger.info(f"LangChain adapter loaded {len(tools)} tools")
            tool_names = [tool.name for tool in tools]
            logger.info(f"Tool names: {tool_names}")
    
    @pytest.mark.asyncio
    async def test_experiment_ai_runner_setup(self, experiment_context):
        """Test that ExperimentSOPAgent can be set up properly."""
        from plexus.cli.experiment.experiment_sop_agent import ExperimentSOPAgent
        
        mcp_server = await create_experiment_mcp_server(
            experiment_context=experiment_context,
            plexus_tools=['scorecard', 'score', 'feedback']
        )
        
        runner = ExperimentSOPAgent(
            experiment_id='test-exp-123',
            mcp_server=mcp_server,
            openai_api_key=TEST_OPENAI_KEY
        )
        
        # Test setup
        setup_success = await runner.setup(TEST_EXPERIMENT_YAML)
        assert setup_success is True
        
        # Check configuration was loaded
        assert runner.experiment_config is not None
        assert 'exploration' in runner.experiment_config
        
        # Test prompt generation
        prompt = runner.get_exploration_prompt()
        assert len(prompt) > 0
        assert 'plexus_scorecards_list' in prompt  # Enhanced prompt should mention tools
        
        logger.info("ExperimentSOPAgent setup completed successfully")
        logger.info(f"Generated prompt length: {len(prompt)} characters")
    
    @pytest.mark.asyncio
    async def test_mock_ai_execution_with_tools(self, experiment_context):
        """Test AI execution with mocked LangChain components."""
        
        # Mock the imports and execution - patch the import locations where they're actually used
        with patch('langchain.chat_models.ChatOpenAI') as mock_chat_openai, \
             patch('langchain.agents.initialize_agent') as mock_init_agent, \
             patch('langchain.agents.AgentType') as mock_agent_type, \
             patch('langchain.memory.ConversationBufferMemory') as mock_memory, \
             patch('langchain.tools.Tool') as mock_tool:
            
            # Set up mocks
            mock_llm = Mock()
            mock_chat_openai.return_value = mock_llm
            
            mock_agent = Mock()
            mock_agent.invoke = Mock(return_value={"output": "AI successfully used 3 tools: think, plexus_scorecards_list, and plexus_scorecard_info. Found 2 scorecards with detailed analysis."})
            mock_init_agent.return_value = mock_agent
            
            # Create MCP server
            mcp_server = await create_experiment_mcp_server(
                experiment_context=experiment_context,
                plexus_tools=['scorecard', 'score', 'feedback']
            )
            
            # Run the AI experiment
            result = await run_sop_guided_experiment(
                experiment_id='test-exp-123',
                experiment_yaml=TEST_EXPERIMENT_YAML,
                mcp_server=mcp_server,
                openai_api_key=TEST_OPENAI_KEY
            )
            
            # Verify results
            assert result['success'] is True
            assert result['experiment_id'] == 'test-exp-123'
            assert 'response' in result
            assert 'tools_available' in result
            assert 'tool_names' in result
            assert result['tools_available'] > 0
            
            logger.info("Mock AI execution completed successfully")
            logger.info(f"AI response: {result['response']}")
            logger.info(f"Tools available: {result['tools_available']}")
    
    @pytest.mark.asyncio
    async def test_full_experiment_run_with_ai_mocked(self, mock_client, experiment_context):
        """Test the full experiment run workflow with mocked AI."""
        
        # Mock experiment info
        mock_experiment_info = Mock()
        mock_experiment_info.name = 'Test Experiment'
        mock_experiment_info.scorecard_name = 'Test Scorecard'
        mock_experiment_info.score_name = 'Test Score'
        mock_experiment_info.node_count = 1
        mock_experiment_info.version_count = 1
        
        service = ExperimentService(mock_client)
        
        with patch.object(service, 'get_experiment_info') as mock_get_info, \
             patch.object(service, 'get_experiment_yaml') as mock_get_yaml, \
             patch('plexus.cli.experiment.experiment_sop_agent.run_sop_guided_experiment') as mock_run_ai:
            
            # Set up mocks
            mock_get_info.return_value = mock_experiment_info
            mock_get_yaml.return_value = TEST_EXPERIMENT_YAML
            mock_run_ai.return_value = {
                'success': True,
                'response': 'AI executed successfully with MCP tools',
                'tool_names': ['think', 'plexus_scorecards_list', 'plexus_scorecard_info'],
                'tools_used': 3
            }
            
            # Run the experiment
            result = await service.run_experiment(
                experiment_id='test-exp-123',
                enable_mcp=True,
                mcp_tools=['scorecard', 'score', 'feedback'],
                openai_api_key=TEST_OPENAI_KEY
            )
            
            # Verify results
            assert result['status'] == 'completed'
            assert result['experiment_id'] == 'test-exp-123'
            assert 'mcp_info' in result
            assert 'available_tools' in result['mcp_info']
            assert len(result['mcp_info']['available_tools']) > 0
            assert 'ai_execution' in result
            assert result['ai_execution']['completed'] is True
            
            logger.info("Full experiment run test completed successfully")
            logger.info(f"Final status: {result['status']}")
    
    @pytest.mark.asyncio
    async def test_error_handling_without_openai_key(self, experiment_context):
        """Test proper error handling when OpenAI key is not available."""
        
        mcp_server = await create_experiment_mcp_server(
            experiment_context=experiment_context,
            plexus_tools=['scorecard']
        )
        
        # Mock the config loader to return None for OpenAI key to simulate missing key
        with patch('os.getenv') as mock_getenv:
            # Make os.getenv return None for OPENAI_API_KEY
            def mock_getenv_func(key, default=None):
                if key == 'OPENAI_API_KEY':
                    return None
                return default
            
            mock_getenv.side_effect = mock_getenv_func
            
            # Test without API key (explicitly set to None)
            result = await run_sop_guided_experiment(
                experiment_id='test-exp-123',
                experiment_yaml=TEST_EXPERIMENT_YAML,
                mcp_server=mcp_server,
                openai_api_key=None
            )
        
        # Should handle missing key gracefully
        assert result['success'] is False
        assert 'error' in result
        assert 'API key' in result['error']
        assert 'suggestion' in result
        
        logger.info("Error handling test completed - missing API key handled properly")
    
    @pytest.mark.asyncio
    async def test_tool_execution_simulation(self, experiment_context):
        """Test that individual tools can be executed and return proper results."""
        
        mcp_server = await create_experiment_mcp_server(
            experiment_context=experiment_context,
            plexus_tools=['scorecard', 'score']
        )
        
        async with mcp_server.connect({'name': 'Tool Test Client'}) as client:
            # Test think tool with detailed thought
            think_result = await client.call_tool('think', {
                'thought': 'I need to analyze the available scorecards and understand their structure to help optimize the AI system.'
            })
            
            # Handle wrapped MCP response - think tool returns plain text "Thought processed"
            if 'content' in think_result and isinstance(think_result['content'], list):
                content_text = think_result['content'][0]['text']
                # Think tool returns plain text, not JSON
                assert 'Thought processed' in content_text or 'thought' in content_text.lower()
            else:
                # Direct access fallback
                assert isinstance(think_result, (str, dict))
                if isinstance(think_result, str):
                    assert 'thought' in think_result.lower()
                else:
                    assert 'thought' in think_result
            logger.info("Think tool executed successfully")
            
            # Test get_experiment_context
            context_result = await client.call_tool('get_experiment_context', {})
            if 'content' in context_result and isinstance(context_result['content'], list):
                import json
                content_text = context_result['content'][0]['text']
                parsed_result = json.loads(content_text)
                assert parsed_result['experiment_context']['experiment_id'] == 'test-exp-123'
                assert parsed_result['experiment_context']['experiment_name'] == 'Test AI Integration Experiment'
            else:
                assert context_result['experiment_id'] == 'test-exp-123'
                assert context_result['experiment_name'] == 'Test AI Integration Experiment'
            logger.info("Experiment context tool executed successfully")
            
            # Test log_message with different levels
            await client.call_tool('log_message', {
                'message': 'Starting analysis phase',
                'level': 'info'
            })
            
            await client.call_tool('log_message', {
                'message': 'Analysis complete - found optimization opportunities',
                'level': 'info'
            })
            
            logger.info("Log message tools executed successfully")
    
    def test_experiment_yaml_parsing(self):
        """Test that experiment YAML is properly parsed."""
        import yaml
        
        config = yaml.safe_load(TEST_EXPERIMENT_YAML)
        
        assert 'class' in config
        assert config['class'] == 'BeamSearch'
        assert 'exploration' in config
        assert 'value' in config
        
        # Check exploration prompt contains tool mentions
        exploration = config['exploration']
        assert 'plexus_scorecards_list' in exploration
        assert 'think' in exploration
        assert 'tools' in exploration.lower()
        
        logger.info("YAML parsing test completed successfully")

# Integration test runner
async def run_integration_test():
    """
    Run a comprehensive integration test manually.
    This can be called directly to test the system end-to-end.
    """
    logger.info("Starting comprehensive AI + MCP integration test...")
    
    try:
        # Create experiment context
        experiment_context = {
            'experiment_id': 'integration-test-001',
            'experiment_name': 'AI MCP Integration Test',
            'scorecard_name': 'Integration Test Scorecard',
            'score_name': 'Integration Test Score',
            'node_count': 1,
            'version_count': 1,
            'options': {'enable_mcp': True, 'test_mode': True}
        }
        
        # Create MCP server with all tool categories
        logger.info("Creating MCP server with all Plexus tools...")
        mcp_server = await create_experiment_mcp_server(
            experiment_context=experiment_context,
            plexus_tools=['scorecard', 'score', 'feedback', 'prediction']
        )
        
        tools_count = len(mcp_server.transport.tools)
        logger.info(f"✓ MCP server created with {tools_count} tools")
        
        # Test tool execution
        logger.info("Testing individual tool execution...")
        async with mcp_server.connect({'name': 'Integration Test Client'}) as client:
            
            # Test core tools
            context_result = await client.call_tool('get_experiment_context', {})
            if 'content' in context_result and isinstance(context_result['content'], list):
                import json
                content_text = context_result['content'][0]['text']
                parsed_result = json.loads(content_text)
                experiment_context_data = parsed_result.get('experiment_context', {})
            else:
                experiment_context_data = context_result.get('experiment_context', {})
            experiment_name = experiment_context_data.get('experiment_name', 'Unknown')
            logger.info(f"✓ Experiment context: {experiment_name}")
            
            think_result = await client.call_tool('think', {
                'thought': 'Testing the MCP integration to ensure AI models can access Plexus tools properly.'
            })
            logger.info("✓ Think tool executed successfully")
            
            await client.call_tool('log_message', {
                'message': 'Integration test in progress',
                'level': 'info'
            })
            logger.info("✓ Log message tool executed successfully")
        
        # Test LangChain adapter
        logger.info("Testing LangChain adapter...")
        from plexus.cli.experiment.experiment_sop_agent import LangChainMCPAdapter
        
        async with mcp_server.connect({'name': 'LangChain Integration Test'}) as client:
            adapter = LangChainMCPAdapter(client)
            langchain_tools = await adapter.load_tools()
            logger.info(f"✓ LangChain adapter loaded {len(langchain_tools)} tools")
            
            # Test one tool conversion
            if langchain_tools:
                test_tool = langchain_tools[0]
                logger.info(f"✓ Sample tool: {test_tool.name} - {test_tool.description[:100]}...")
        
        # Test experiment runner setup
        logger.info("Testing ExperimentSOPAgent setup...")
        from plexus.cli.experiment.experiment_sop_agent import ExperimentSOPAgent
        
        runner = ExperimentSOPAgent(
            experiment_id='integration-test-001',
            mcp_server=mcp_server,
            openai_api_key=TEST_OPENAI_KEY
        )
        
        setup_success = await runner.setup(TEST_EXPERIMENT_YAML)
        logger.info(f"✓ AI runner setup: {'successful' if setup_success else 'failed'}")
        
        if setup_success:
            prompt = runner.get_exploration_prompt()
            logger.info(f"✓ Generated exploration prompt ({len(prompt)} chars)")
            logger.info(f"  Prompt preview: {prompt[:200]}...")
        
        logger.info("\n🎉 Integration test completed successfully!")
        logger.info("The AI + MCP integration is working properly:")
        logger.info(f"  • MCP server: {tools_count} tools available")
        logger.info(f"  • LangChain: {len(langchain_tools)} tools converted")
        logger.info(f"  • AI runner: {'✓' if setup_success else '✗'} setup complete")
        
        return True
        
    except Exception as e:
        logger.error(f"Integration test failed: {e}")
        logger.error("", exc_info=True)
        return False

if __name__ == "__main__":
    # Run the integration test directly
    logging.basicConfig(level=logging.INFO)
    result = asyncio.run(run_integration_test())
    if result:
        print("\n✅ All integration tests passed!")
    else:
        print("\n❌ Integration tests failed!")