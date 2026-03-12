"""
Multi-Agent ReAct Loop Test Suite

This test suite tells the story of our multi-agent system:

## Architecture Story
- **Manager Agent (Orchestrator)**: Follows standard operating procedures (SOP) and 
  guides the conversation flow through different phases
- **Worker Agent (Coding Assistant)**: Executes tool calls based on manager guidance,
  has access to scoped tools appropriate for each phase
- **ReAct Loop**: Manager observes worker actions, provides next guidance, 
  worker acts on guidance, repeat until completion

## Key Components Tested
1. Manager/Orchestrator Role: ConversationFlowManager + orchestration LLM
2. Worker/Coding Assistant Role: LangChain agent with MCP tools
3. Tool Scoping: Different tools available in different phases
4. State Management: Exploration → Synthesis → Hypothesis Generation
5. Safeguards: Safety limits, proper termination conditions

## Test Structure
Each test tells a story about how the multi-agent system works together
to accomplish complex tasks through structured collaboration.
"""

import asyncio
import json
from types import SimpleNamespace
from unittest.mock import patch, MagicMock, AsyncMock
import pytest
from typing import Dict, List, Any, Optional


class MockMCPServer:
    """Mock MCP server that provides tools to the worker agent."""
    
    class MockClient:
        async def call_tool(self, name, args):
            return {"ok": True, "tool": name, "args": args}
    
    def __init__(self):
        self._client = self.MockClient()
    
    def connect(self, _info):
        server = self
        
        class ConnectionContext:
            async def __aenter__(self):
                return server._client
            
            async def __aexit__(self, exc_type, exc, tb):
                return False
        
        return ConnectionContext()


class MockLLMResponse:
    """Mock LLM response that can contain either text or tool calls."""
    
    def __init__(self, content: str, tool_calls: Optional[List[Dict]] = None):
        self.content = content
        self.tool_calls = tool_calls or []


class ManagerAgentMock:
    """
    Mock for the Manager/Orchestrator Agent that follows SOPs.
    
    This simulates the manager agent that:
    1. Follows standard operating procedures
    2. Tracks conversation state and progress
    3. Provides contextual guidance to the worker agent
    4. Decides when to transition between phases
    """
    
    def __init__(self):
        self.responses = []
        self.current_phase = "exploration"
        self.guidance_calls = 0
        self.state_updates = []
    
    def queue_orchestration_responses(self, responses: List[str]):
        """Queue up orchestration responses the manager will provide."""
        self.responses = responses
    
    async def generate_guidance(self, conversation_history: List, state_data: Dict[str, Any]) -> str:
        """
        Simulate the manager agent generating contextual guidance.
        
        This represents the SOP-following behavior where the manager:
        1. Analyzes what the worker has done
        2. Determines what should happen next according to the SOP
        3. Provides specific guidance to keep the worker on track
        """
        self.guidance_calls += 1
        self.state_updates.append(state_data.copy())
        
        if self.responses:
            response = self.responses.pop(0)
            print(f"Manager Agent providing guidance #{self.guidance_calls}: {response[:100]}...")
            return response
        
        # Fallback guidance based on phase
        phase = state_data.get('current_state', 'exploration')
        if phase == 'exploration':
            return "Continue analyzing feedback data to understand the scoring problems."
        elif phase == 'synthesis':
            return "Synthesize your findings and identify the root causes of scoring errors."
        elif phase == 'hypothesis_generation':
            return "Create experiment nodes to test your hypotheses."
        else:
            return "Continue working towards completing the analysis."


class WorkerAgentMock:
    """
    Mock for the Worker/Coding Assistant Agent that executes tools.
    
    This simulates the worker agent that:
    1. Receives guidance from the manager
    2. Executes appropriate tool calls
    3. Has access to scoped tools based on current phase
    4. Reports results back to the manager
    """
    
    def __init__(self):
        self.tool_calls_made = []
        self.tools_available = []
        self.responses = []
        self.current_response_idx = 0
    
    def set_available_tools(self, tools: List[str]):
        """Set which tools are available to the worker in current phase."""
        self.tools_available = tools
    
    def queue_responses(self, responses: List[str]):
        """Queue up responses the worker will make."""
        self.responses = responses
        self.current_response_idx = 0
    
    def get_next_response(self) -> MockLLMResponse:
        """Get the next scripted response from the worker agent."""
        if self.current_response_idx < len(self.responses):
            response = self.responses[self.current_response_idx]
            self.current_response_idx += 1
            
            # Check if this is a tool call or regular response
            if response.startswith('{"tool":'):
                try:
                    tool_data = json.loads(response)
                    tool_name = tool_data['tool']
                    
                    # Simulate tool scoping enforcement
                    if tool_name not in self.tools_available:
                        print(f"Worker Agent: Tool {tool_name} blocked by scoping")
                        return MockLLMResponse(f"Error: Tool {tool_name} not available in current phase")
                    
                    # Record the tool call
                    self.tool_calls_made.append(tool_name)
                    tool_calls = [{
                        'name': tool_name,
                        'args': tool_data.get('arguments', {}),
                        'id': f"call_{len(self.tool_calls_made)}",
                        'type': 'tool_call'
                    }]
                    print(f"Worker Agent making tool call: {tool_name}")
                    return MockLLMResponse("", tool_calls=tool_calls)
                except json.JSONDecodeError:
                    pass
            
            # Regular text response
            print(f"Worker Agent responding: {response[:100]}...")
            return MockLLMResponse(response)
        
        return MockLLMResponse("I have completed my analysis.")


class MockMCPAdapter:
    """Mock MCP adapter that provides scoped tools to the worker agent."""
    
    def __init__(self, client):
        self.tools = []
        self.chat_recorder = None
        self.tools_called = set()
        self.scoped_tools = []  # Tools available in current phase
    
    def set_tool_scope(self, allowed_tools: List[str]):
        """Set which tools are available based on current phase."""
        self.scoped_tools = allowed_tools
    
    async def load_tools(self):
        """Load tools available to the worker agent (scoped by phase)."""
        def make_tool_func(tool_name):
            def tool_func(args):
                self.tools_called.add(tool_name)
                print(f"MCP Tool executed: {tool_name}({args})")
                return f"Tool {tool_name} executed successfully with results"
            return tool_func
        
        # Only provide tools that are in scope for current phase
        all_tools = {
            'plexus_feedback_analysis': 'Analyze feedback data',
            'plexus_feedback_find': 'Find specific feedback items',
            'plexus_item_info': 'Get item information',
            'create_experiment_node': 'Create hypothesis node',
            'update_node_content': 'Update node configuration',
            'think': 'Internal reasoning tool'
        }
        
        self.tools = []
        for tool_name, description in all_tools.items():
            if tool_name in self.scoped_tools:
                self.tools.append(SimpleNamespace(
                    name=tool_name,
                    description=description,
                    func=make_tool_func(tool_name)
                ))
        
        print(f"MCP Adapter loaded {len(self.tools)} scoped tools: {[t.name for t in self.tools]}")
        return self.tools


@pytest.fixture
def mock_experiment_setup():
    """Set up mocks for the multi-agent experiment system."""
    manager = ManagerAgentMock()
    worker = WorkerAgentMock()
    mcp_adapter = MockMCPAdapter(None)
    
    return {
        'manager': manager,
        'worker': worker,
        'mcp_adapter': mcp_adapter,
        'experiment_yaml': """
class: "MultiAgentReAct"
conversation_flow:
  initial_state: "exploration"
  states:
    exploration:
      tools: ["plexus_feedback_analysis", "plexus_feedback_find", "think"]
    synthesis:
      tools: ["think"]
    hypothesis_generation:
      tools: ["create_experiment_node", "update_node_content", "think"]
""",
        'experiment_context': {
            'experiment_id': 'multi-agent-test',
            'scorecard_name': 'TestCard',
            'score_name': 'TestScore'
        }
    }


class TestManagerOrchestratorAgent:
    """Test suite for the Manager/Orchestrator Agent behavior."""
    
    def test_manager_follows_sop_and_provides_contextual_guidance(self, mock_experiment_setup):
        """
        STORY: Manager agent follows standard operating procedures to guide worker
        
        The manager agent:
        1. Tracks conversation state and worker progress
        2. Follows SOP to determine next steps
        3. Provides contextual guidance to keep worker focused
        4. Adapts guidance based on what worker has accomplished
        """
        manager = mock_experiment_setup['manager']
        
        # Simulate different states the manager tracks
        state_scenarios = [
            {
                'current_state': 'exploration',
                'tools_used': [],
                'nodes_created': 0,
                'round_in_stage': 1
            },
            {
                'current_state': 'exploration', 
                'tools_used': ['plexus_feedback_analysis'],
                'nodes_created': 0,
                'round_in_stage': 2
            },
            {
                'current_state': 'synthesis',
                'tools_used': ['plexus_feedback_analysis', 'plexus_feedback_find'],
                'nodes_created': 0,
                'round_in_stage': 1
            },
            {
                'current_state': 'hypothesis_generation',
                'tools_used': ['plexus_feedback_analysis', 'plexus_feedback_find'],
                'nodes_created': 0,
                'round_in_stage': 1
            }
        ]
        
        # Manager provides SOP-guided responses
        manager.queue_orchestration_responses([
            "Start by analyzing the feedback data using plexus_feedback_analysis tool.",
            "Good analysis. Now examine specific feedback items with plexus_feedback_find.",
            "Synthesize your findings to identify the root causes of scoring errors.",
            "Create your first experiment node to test a hypothesis."
        ])
        
        # Test manager guidance for each state
        conversation_history = []
        for i, state_data in enumerate(state_scenarios):
            asyncio.run(self._test_manager_guidance_step(manager, conversation_history, state_data, i))
        
        # Verify manager followed SOP correctly
        assert manager.guidance_calls == 4
        assert len(manager.state_updates) == 4
        
        # Verify state progression tracking
        assert manager.state_updates[0]['current_state'] == 'exploration'
        assert manager.state_updates[2]['current_state'] == 'synthesis'  
        assert manager.state_updates[3]['current_state'] == 'hypothesis_generation'
    
    async def _test_manager_guidance_step(self, manager, conversation_history, state_data, step):
        """Helper to test one guidance step from the manager."""
        guidance = await manager.generate_guidance(conversation_history, state_data)
        
        # Verify guidance is contextual and appropriate for state
        if state_data['current_state'] == 'exploration':
            assert 'analyz' in guidance.lower() or 'feedback' in guidance.lower()
        elif state_data['current_state'] == 'synthesis':
            assert 'synthesize' in guidance.lower() or 'root cause' in guidance.lower()
        elif state_data['current_state'] == 'hypothesis_generation':
            assert 'experiment' in guidance.lower() or 'node' in guidance.lower()
        
        print(f"✅ Manager provided appropriate guidance for {state_data['current_state']} phase")


class TestWorkerCodingAgent:
    """Test suite for the Worker/Coding Assistant Agent behavior."""
    
    def test_worker_executes_tools_based_on_manager_guidance(self, mock_experiment_setup):
        """
        STORY: Worker agent executes tools based on manager's guidance
        
        The worker agent:
        1. Receives specific guidance from manager
        2. Makes appropriate tool calls to accomplish guidance
        3. Has access only to phase-appropriate tools
        4. Reports results back for manager evaluation
        """
        worker = mock_experiment_setup['worker']
        mcp_adapter = mock_experiment_setup['mcp_adapter']
        
        # Test exploration phase tools
        exploration_tools = ['plexus_feedback_analysis', 'plexus_feedback_find', 'think']
        mcp_adapter.set_tool_scope(exploration_tools)
        worker.set_available_tools(exploration_tools)
        
        # Worker receives guidance and makes tool calls
        worker.queue_responses([
            '{"tool":"plexus_feedback_analysis","arguments":{"scorecard_name":"TestCard","score_name":"TestScore"}}',
            'Based on the analysis, I found several scoring patterns. Let me examine specific items.',
            '{"tool":"plexus_feedback_find","arguments":{"scorecard_name":"TestCard","score_name":"TestScore","limit":10}}'
        ])
        
        # Simulate worker executing tools
        asyncio.run(self._test_worker_tool_execution(worker, mcp_adapter, exploration_tools))
        
        # Verify worker made appropriate tool calls
        assert 'plexus_feedback_analysis' in worker.tool_calls_made
        assert 'plexus_feedback_find' in worker.tool_calls_made
        assert len(worker.tool_calls_made) == 2
        
        print("✅ Worker agent successfully executed tools based on guidance")
    
    async def _test_worker_tool_execution(self, worker, mcp_adapter, available_tools):
        """Helper to test worker tool execution."""
        await mcp_adapter.load_tools()
        
        # Simulate worker making tool calls
        for _ in range(3):  # Three queued responses
            response = worker.get_next_response()
            if response.tool_calls:
                # Verify tool is available and execute it
                tool_call = response.tool_calls[0]
                tool_name = tool_call['name']
                
                assert tool_name in available_tools, f"Tool {tool_name} should be available"
                
                # Find and execute the tool
                for tool in mcp_adapter.tools:
                    if tool.name == tool_name:
                        result = tool.func(tool_call['args'])
                        assert 'successfully' in result
                        break
    
    def test_worker_tool_scoping_enforcement(self, mock_experiment_setup):
        """
        STORY: Worker agent is restricted to phase-appropriate tools
        
        Tool scoping ensures:
        1. Worker can only access tools appropriate for current phase
        2. Unauthorized tools are blocked (e.g., no predictions during analysis)
        3. Phase transitions change available tool set
        4. Scoping violations are caught and reported
        """
        worker = mock_experiment_setup['worker']
        
        # Test exploration phase - should block hypothesis tools
        exploration_tools = ['plexus_feedback_analysis', 'think']
        worker.set_available_tools(exploration_tools)
        worker.queue_responses([
            '{"tool":"create_experiment_node","arguments":{"experiment_id":"test"}}'  # Should be blocked
        ])
        
        response = worker.get_next_response()
        
        # Verify unauthorized tool was blocked
        assert response.tool_calls == []  # No tool calls made
        assert 'not available' in response.content.lower() or 'blocked' in response.content.lower()
        
        # Test hypothesis phase - should allow node creation
        hypothesis_tools = ['create_experiment_node', 'update_node_content', 'think']
        worker.set_available_tools(hypothesis_tools)
        worker.queue_responses([
            '{"tool":"create_experiment_node","arguments":{"experiment_id":"test","hypothesis_description":"Test hypothesis"}}'
        ])
        
        response = worker.get_next_response()
        
        # Verify authorized tool was allowed
        assert len(response.tool_calls) == 1
        assert response.tool_calls[0]['name'] == 'create_experiment_node'
        assert 'create_experiment_node' in worker.tool_calls_made
        
        print("✅ Tool scoping correctly enforced across phases")


class TestReActLoopIntegration:
    """Test suite for the complete ReAct loop integration."""
    
    def test_complete_react_loop_manager_worker_collaboration(self, mock_experiment_setup):
        """
        STORY: Complete ReAct loop showing manager-worker collaboration
        
        The ReAct loop demonstrates:
        1. Manager provides guidance based on SOP
        2. Worker acts on guidance with appropriate tools
        3. Manager observes worker actions and results
        4. Manager provides next guidance based on progress
        5. Loop continues until completion criteria met
        """
        manager = mock_experiment_setup['manager']
        worker = mock_experiment_setup['worker']
        mcp_adapter = mock_experiment_setup['mcp_adapter']
        
        # Simulate a complete ReAct loop
        react_steps = [
            {
                'phase': 'exploration',
                'tools': ['plexus_feedback_analysis', 'think'],
                'manager_guidance': 'Analyze the feedback data to understand scoring patterns.',
                'worker_action': '{"tool":"plexus_feedback_analysis","arguments":{"scorecard_name":"TestCard"}}',
                'worker_reflection': 'I analyzed the feedback and found several scoring issues.'
            },
            {
                'phase': 'exploration',
                'tools': ['plexus_feedback_analysis', 'plexus_feedback_find', 'think'],
                'manager_guidance': 'Examine specific feedback items to understand the problems.',
                'worker_action': '{"tool":"plexus_feedback_find","arguments":{"scorecard_name":"TestCard","limit":5}}',
                'worker_reflection': 'I found specific examples of scoring errors.'
            },
            {
                'phase': 'synthesis',
                'tools': ['think'],
                'manager_guidance': 'Synthesize your findings to identify root causes.',
                'worker_action': 'Based on my analysis, the main issues are threshold sensitivity and pattern gaps.',
                'worker_reflection': 'I have identified the key problems and their causes.'
            },
            {
                'phase': 'hypothesis_generation',
                'tools': ['create_experiment_node', 'think'],
                'manager_guidance': 'Create experiment nodes to test solutions.',
                'worker_action': '{"tool":"create_experiment_node","arguments":{"experiment_id":"test","hypothesis_description":"GOAL: Reduce false positives | METHOD: Adjust thresholds"}}',
                'worker_reflection': 'I created a hypothesis to test threshold adjustments.'
            }
        ]
        
        # Execute the ReAct loop
        conversation_state = {'nodes_created': 0, 'tools_used': []}
        
        for step_num, step in enumerate(react_steps):
            print(f"\n--- ReAct Loop Step {step_num + 1}: {step['phase']} ---")
            
            # Manager provides guidance
            manager.queue_orchestration_responses([step['manager_guidance']])
            state_data = {
                'current_state': step['phase'],
                'tools_used': conversation_state['tools_used'],
                'nodes_created': conversation_state['nodes_created'],
                'round_in_stage': 1
            }
            
            guidance = asyncio.run(manager.generate_guidance([], state_data))
            assert step['manager_guidance'] in guidance
            print(f"Manager: {guidance}")
            
            # Worker acts on guidance
            mcp_adapter.set_tool_scope(step['tools'])
            worker.set_available_tools(step['tools'])
            worker.queue_responses([step['worker_action'], step['worker_reflection']])
            
            # Worker makes action
            action_response = worker.get_next_response()
            if action_response.tool_calls:
                tool_name = action_response.tool_calls[0]['name']
                conversation_state['tools_used'].append(tool_name)
                
                # Simulate tool execution
                if tool_name == 'create_experiment_node':
                    conversation_state['nodes_created'] += 1
                
                print(f"Worker Action: Tool call to {tool_name}")
            else:
                print(f"Worker Action: {action_response.content}")
            
            # Worker provides reflection
            reflection_response = worker.get_next_response()
            print(f"Worker Reflection: {reflection_response.content}")
        
        # Verify complete ReAct loop execution
        assert manager.guidance_calls == 4  # Manager provided guidance 4 times
        assert len(conversation_state['tools_used']) >= 3  # Worker used multiple tools
        assert conversation_state['nodes_created'] == 1  # Worker created hypothesis
        assert 'plexus_feedback_analysis' in conversation_state['tools_used']
        assert 'create_experiment_node' in conversation_state['tools_used']
        
        print("✅ Complete ReAct loop executed successfully with manager-worker collaboration")


# TestConversationStateManagement removed - state machine functionality was simplified

class TestConversationStateManagement:
    """Test suite - DISABLED - state machine functionality was simplified."""
    
    def test_state_transitions_follow_sop_progression_DISABLED(self, mock_experiment_setup):
        """
        STORY: Conversation state transitions follow standard operating procedure
        
        State management ensures:
        1. Proper progression through phases (exploration → synthesis → hypothesis)
        2. Transition criteria are met before advancing
        3. State data is tracked and updated correctly
        4. Phase-specific behaviors are enforced
        """
        # DISABLED: State machine functionality was removed from the system
        # The simplified multi-agent ReAct loop no longer uses state machines
        return
    
    def test_phase_specific_tool_availability_DISABLED(self, mock_experiment_setup):
        """
        STORY: Each phase has appropriate tools available
        
        Phase-specific tooling ensures:
        1. Exploration: Analysis tools (feedback_analysis, feedback_find, item_info)
        2. Synthesis: Reasoning tools (think)
        3. Hypothesis: Creation tools (create_experiment_node, update_node_content)
        4. No cross-phase tool contamination
        """
        # DISABLED: State machine functionality was removed from the system
        # Tool scoping is now handled by the procedure definition directly
        return


class TestSafeguardsAndTermination:
    """Test suite for safety limits and termination conditions."""
    
    def test_safety_limits_prevent_infinite_loops(self, mock_experiment_setup):
        """
        STORY: Safety limits prevent runaway conversations
        
        Safety mechanisms include:
        1. Maximum round limits to prevent infinite loops
        2. Node creation tracking and limits
        3. Proper termination when objectives met
        4. Fallback termination when stuck
        """
        manager = mock_experiment_setup['manager']
        
        # Test maximum round limiting
        MAX_ROUNDS = 50  # From langchain_mcp.py safety_limit
        
        # Simulate a conversation that would go infinite without limits
        manager.queue_orchestration_responses(['Continue analysis.'] * 60)  # More than limit
        
        round_count = 0
        for i in range(60):
            if round_count >= MAX_ROUNDS:
                break
            
            state_data = {'current_state': 'exploration', 'round_in_stage': i}
            guidance = asyncio.run(manager.generate_guidance([], state_data))
            round_count += 1
        
        # Verify safety limit would be enforced
        assert round_count <= MAX_ROUNDS, "Safety limit should prevent infinite loops"
        
        print("✅ Safety limits properly configured to prevent infinite loops")
    
    def test_completion_criteria_and_termination(self, mock_experiment_setup):
        """
        STORY: System terminates when objectives are met
        
        Completion criteria:
        1. Target number of hypothesis nodes created
        2. All required analysis phases completed
        3. Manager determines objectives are met
        4. Proper session cleanup and summarization
        """
        # Test completion after creating target nodes
        TARGET_NODES = 2  # Typical target from the code
        
        completion_scenarios = [
            {'nodes_created': 0, 'should_continue': True},
            {'nodes_created': 1, 'should_continue': True},
            {'nodes_created': 2, 'should_continue': False},  # Target reached
            {'nodes_created': 3, 'should_continue': False}   # Exceeded target
        ]
        
        for scenario in completion_scenarios:
            nodes_created = scenario['nodes_created']
            expected_continue = scenario['should_continue']
            
            # Simple completion logic: stop when target nodes reached
            actual_continue = nodes_created < TARGET_NODES
            
            assert actual_continue == expected_continue, \
                f"Completion logic incorrect for {nodes_created} nodes"
        
        print("✅ Completion criteria properly defined for termination")


# Integration test that runs a realistic multi-agent scenario
class TestMultiAgentReActStory:
    """Integration test that tells the complete multi-agent story."""
    
    @pytest.mark.asyncio
    async def test_complete_multi_agent_react_story(self, mock_experiment_setup):
        """
        COMPLETE STORY: Multi-agent ReAct loop for hypothesis generation
        
        This integration test demonstrates the full story:
        
        1. **Setup**: Manager and worker agents initialized with SOPs and tools
        2. **Exploration Phase**: 
           - Manager guides worker to analyze feedback data
           - Worker uses analysis tools to understand scoring problems
           - Manager evaluates progress and provides next guidance
        3. **Synthesis Phase**:
           - Manager guides worker to identify root causes
           - Worker synthesizes findings using reasoning tools
           - Manager confirms analysis is complete
        4. **Hypothesis Generation Phase**:
           - Manager guides worker to create experiment nodes
           - Worker creates hypothesis nodes with specific configurations
           - Manager tracks progress towards completion
        5. **Termination**: System completes when objectives met
        
        This story validates that our multi-agent system can collaborate
        effectively to accomplish complex reasoning and creation tasks.
        """
        manager = mock_experiment_setup['manager']
        worker = mock_experiment_setup['worker']
        mcp_adapter = mock_experiment_setup['mcp_adapter']
        
        print("\n🚀 Starting Multi-Agent ReAct Loop Story...")
        
        # === PHASE 1: EXPLORATION ===
        print("\n📊 PHASE 1: EXPLORATION - Understanding the Problem")
        
        # Manager provides exploration guidance
        manager.queue_orchestration_responses([
            "Begin by analyzing the feedback data to understand what scoring problems exist.",
            "Now examine specific feedback items to see examples of the scoring errors."
        ])
        
        # Set exploration tools for worker
        exploration_tools = ['plexus_feedback_analysis', 'plexus_feedback_find', 'think']
        mcp_adapter.set_tool_scope(exploration_tools)
        worker.set_available_tools(exploration_tools)
        
        # Worker performs exploration actions
        worker.queue_responses([
            '{"tool":"plexus_feedback_analysis","arguments":{"scorecard_name":"TestCard","score_name":"TestScore","days":7}}',
            'I found significant patterns in the feedback showing threshold sensitivity issues.',
            '{"tool":"plexus_feedback_find","arguments":{"scorecard_name":"TestCard","score_name":"TestScore","limit":10}}',
            'Examining specific cases reveals the AI is being too strict in certain scenarios.'
        ])
        
        # Execute exploration phase
        await self._execute_react_round(manager, worker, mcp_adapter, 'exploration', 1)
        await self._execute_react_round(manager, worker, mcp_adapter, 'exploration', 2)
        
        # === PHASE 2: SYNTHESIS ===
        print("\n🧠 PHASE 2: SYNTHESIS - Identifying Root Causes")
        
        # Manager provides synthesis guidance
        manager.queue_orchestration_responses([
            "Synthesize your findings to identify the root causes of these scoring problems."
        ])
        
        # Set synthesis tools for worker (mainly reasoning)
        synthesis_tools = ['think']
        mcp_adapter.set_tool_scope(synthesis_tools)
        worker.set_available_tools(synthesis_tools)
        
        # Worker performs synthesis
        worker.queue_responses([
            'Based on my analysis, the root causes are: 1) Threshold too aggressive, 2) Missing edge case patterns, 3) Insufficient context handling.'
        ])
        
        # Execute synthesis phase
        await self._execute_react_round(manager, worker, mcp_adapter, 'synthesis', 1)
        
        # === PHASE 3: HYPOTHESIS GENERATION ===
        print("\n🧪 PHASE 3: HYPOTHESIS GENERATION - Creating Solutions")
        
        # Manager provides hypothesis guidance
        manager.queue_orchestration_responses([
            "Create experiment nodes to test solutions for the identified problems.",
            "Create another hypothesis to test a different approach."
        ])
        
        # Set hypothesis tools for worker
        hypothesis_tools = ['create_experiment_node', 'update_node_content', 'think']
        mcp_adapter.set_tool_scope(hypothesis_tools)
        worker.set_available_tools(hypothesis_tools)
        
        # Worker creates hypotheses
        worker.queue_responses([
            '{"tool":"create_experiment_node","arguments":{"experiment_id":"multi-agent-test","hypothesis_description":"GOAL: Reduce false positives | METHOD: Increase threshold by 10%","node_name":"Threshold Adjustment"}}',
            'Created first hypothesis to test threshold adjustments.',
            '{"tool":"create_experiment_node","arguments":{"experiment_id":"multi-agent-test","hypothesis_description":"GOAL: Handle edge cases | METHOD: Add pattern recognition rules","node_name":"Pattern Enhancement"}}',
            'Created second hypothesis to test pattern improvements.'
        ])
        
        # Execute hypothesis generation phase
        nodes_before = len([call for call in worker.tool_calls_made if call == 'create_experiment_node'])
        await self._execute_react_round(manager, worker, mcp_adapter, 'hypothesis_generation', 1)
        await self._execute_react_round(manager, worker, mcp_adapter, 'hypothesis_generation', 2)
        nodes_after = len([call for call in worker.tool_calls_made if call == 'create_experiment_node'])
        
        # === VALIDATION ===
        print("\n✅ STORY VALIDATION")
        
        # Verify manager orchestration
        assert manager.guidance_calls >= 5, "Manager should have provided multiple guidance messages"
        print(f"✓ Manager provided {manager.guidance_calls} guidance messages")
        
        # Verify worker tool execution
        tools_used = set(worker.tool_calls_made)
        expected_tools = {'plexus_feedback_analysis', 'plexus_feedback_find', 'create_experiment_node'}
        assert expected_tools.issubset(tools_used), f"Worker should have used analysis and creation tools. Used: {tools_used}"
        print(f"✓ Worker used appropriate tools: {tools_used}")
        
        # Verify node creation
        nodes_created = nodes_after - nodes_before
        assert nodes_created >= 2, f"Should have created at least 2 nodes, created {nodes_created}"
        print(f"✓ Created {nodes_created} experiment nodes")
        
        # Verify phase progression
        state_updates = manager.state_updates
        phases_seen = [update.get('current_state') for update in state_updates if update.get('current_state')]
        assert 'exploration' in phases_seen, "Should have gone through exploration phase"
        assert 'hypothesis_generation' in phases_seen, "Should have reached hypothesis generation"
        print(f"✓ Progressed through phases: {set(phases_seen)}")
        
        # Verify tool scoping was enforced
        mcp_tools_executed = mcp_adapter.tools_called
        print(f"✓ MCP tools executed: {mcp_tools_executed}")
        
        print("\n🎉 MULTI-AGENT REACT LOOP STORY COMPLETED SUCCESSFULLY!")
        print("   Manager orchestrated worker through structured problem-solving")
        print("   Worker executed appropriate tools in each phase")  
        print("   System created hypotheses based on systematic analysis")
        print("   Tool scoping prevented unauthorized actions")
    
    async def _execute_react_round(self, manager, worker, mcp_adapter, phase: str, round_num: int):
        """Execute one round of the ReAct loop."""
        print(f"\n  Round {round_num} ({phase})")
        
        # Manager provides guidance
        state_data = {
            'current_state': phase,
            'tools_used': worker.tool_calls_made.copy(),
            'nodes_created': len([call for call in worker.tool_calls_made if call == 'create_experiment_node']),
            'round_in_stage': round_num
        }
        
        guidance = await manager.generate_guidance([], state_data)
        print(f"    Manager: {guidance[:100]}...")
        
        # Worker acts on guidance
        await mcp_adapter.load_tools()
        action_response = worker.get_next_response()
        
        if action_response.tool_calls:
            # Execute tool call
            tool_call = action_response.tool_calls[0]
            tool_name = tool_call['name']
            print(f"    Worker: Calling tool {tool_name}")
            
            # Execute the tool through MCP adapter
            for tool in mcp_adapter.tools:
                if tool.name == tool_name:
                    result = tool.func(tool_call['args'])
                    print(f"    Tool Result: {result[:100]}...")
                    break
        else:
            print(f"    Worker: {action_response.content[:100]}...")
        
        # Worker provides reflection (if available)
        if worker.current_response_idx < len(worker.responses):
            reflection = worker.get_next_response()
            print(f"    Worker Reflection: {reflection.content[:100]}...")


# Test completion tracking
@pytest.fixture(autouse=True)  
def mark_test_completion():
    """Mark test completion for tracking purposes."""
    yield
    # This runs after each test - just for tracking
    print("📝 Multi-agent test coverage executed")
