#!/usr/bin/env python3
"""
Minimal runner for the SOP story scenario (bypasses pytest in restricted envs).
"""
import asyncio
from types import SimpleNamespace


class FakeMCPServer:
    class _Client:
        async def call_tool(self, name, args):
            return {"ok": True, "tool": name, "args": args}

    def __init__(self):
        self._client = self._Client()

    def connect(self, _info):
        server = self
        class _Ctx:
            async def __aenter__(self_inner):
                return server._client
            async def __aexit__(self_inner, exc_type, exc, tb):
                return False
        return _Ctx()


class FakeLLMResponse:
    def __init__(self, content: str):
        self.content = content


class FakeO3Model:
    _queue = []
    def __init__(self, *args, **kwargs):
        pass
    def invoke(self, _messages):
        content = FakeO3Model._queue.pop(0) if FakeO3Model._queue else ""
        return FakeLLMResponse(content)


async def main():
    # Install lightweight stubs for external modules to avoid heavy imports
    import sys, types

    # Stub: langchain_openai.ChatOpenAI
    mod_lco = types.ModuleType('langchain_openai')
    class _StubChatOpenAI:
        def __init__(self, *a, **k):
            pass
        def invoke(self, msgs):
            return FakeLLMResponse("ok")
    mod_lco.ChatOpenAI = _StubChatOpenAI
    sys.modules['langchain_openai'] = mod_lco

    # Stub: langchain.agents
    mod_agents = types.ModuleType('langchain.agents')
    def _stub_init_agent(*a, **k):
        return None
    class _StubAgentType:
        ZERO_SHOT_REACT_DESCRIPTION = 'stub'
    mod_agents.initialize_agent = _stub_init_agent
    mod_agents.AgentType = _StubAgentType
    sys.modules['langchain.agents'] = mod_agents

    # Stub: langchain.memory
    mod_memory = types.ModuleType('langchain.memory')
    class _StubMemory: ...
    mod_memory.ConversationBufferMemory = _StubMemory
    sys.modules['langchain.memory'] = mod_memory

    # Stub: langchain.tools and base
    mod_tools = types.ModuleType('langchain.tools')
    class _StubStructuredTool:
        def __init__(self, name, description, func, args_schema=None):
            self.name = name; self.description = description; self.func = func; self.args_schema = args_schema
    mod_tools.Tool = _StubStructuredTool
    mod_tools.StructuredTool = _StubStructuredTool
    sys.modules['langchain.tools'] = mod_tools

    mod_tools_base = types.ModuleType('langchain.tools.base')
    class _StubBaseTool: ...
    mod_tools_base.BaseTool = _StubBaseTool
    sys.modules['langchain.tools.base'] = mod_tools_base

    # Stub: langchain.callbacks.base
    mod_cb = types.ModuleType('langchain.callbacks.base')
    class _StubCB: ...
    mod_cb.BaseCallbackHandler = _StubCB
    sys.modules['langchain.callbacks.base'] = mod_cb

    # Stub: pydantic BaseModel/Field
    mod_pdm = types.ModuleType('pydantic')
    class _StubBaseModel: pass
    class _StubValidationError(Exception): pass
    def field_validator(*a, **k):
        def deco(fn):
            return fn
        return deco
    class _StubConfigDict(dict):
        pass
    def _stub_Field(*a, **k):
        class _D: pass
        return _D()
    mod_pdm.BaseModel = _StubBaseModel
    mod_pdm.Field = _stub_Field
    mod_pdm.ValidationError = _StubValidationError
    mod_pdm.field_validator = field_validator
    mod_pdm.ConfigDict = _StubConfigDict
    sys.modules['pydantic'] = mod_pdm

    # Stub: graphviz (imported indirectly via plexus.__init__)
    mod_gv = types.ModuleType('graphviz')
    class _StubDigraph:  # minimal placeholder
        def __init__(self, *a, **k):
            pass
        def node(self, *a, **k):
            pass
        def edge(self, *a, **k):
            pass
        def source(self):
            return ''
    mod_gv.Digraph = _StubDigraph
    sys.modules['graphviz'] = mod_gv

    # Now safe to import target code
    from plexus.cli.experiment.experiment_sop_agent import ExperimentSOPAgent, LangChainMCPAdapter
    from unittest.mock import patch

    # Prepare deterministic tool list (names only needed for extraction)
    fake_tools = [
        SimpleNamespace(name='plexus_feedback_analysis', description='Analyze feedback', func=lambda _: "ok"),
        SimpleNamespace(name='create_experiment_node', description='Create hypothesis node', func=lambda _: "ok"),
    ]

    class FakeAdapter:
        def __init__(self, _client):
            pass
        async def load_tools(self):
            return fake_tools

    def fake_call_tool(tool_name, kwargs, _mcp_tools):
        if tool_name == 'plexus_feedback_analysis':
            return '{"status":"ok","summary":"analysis complete"}'
        if tool_name == 'create_experiment_node':
            return '{"status":"ok","message":"node created","node id":"n-123"}'
        return '{"status":"ok"}'

    async def fake_orchestrator(self, conversation_history, state_data):
        return "Continue to next step."

    class FakeClient:
        def __init__(self):
            self._msg_id = 0
        def execute(self, _mutation, _vars):
            self._msg_id += 1
            if 'CreateChatSession' in _mutation:
                return {"data": {"createChatSession": {"id": "sess-1", "status": "ACTIVE"}}}
            if 'CreateChatMessage' in _mutation:
                return {"data": {"createChatMessage": {"id": f"msg-{self._msg_id}", "sequenceNumber": self._msg_id}}}
            if 'UpdateChatSession' in _mutation:
                return {"updateChatSession": {"id": "sess-1", "status": "COMPLETED"}}
            return {"data": {}}

    experiment_yaml = """
class: "BeamSearch"
exploration: |
  Tell a short story about analyzing feedback, then propose hypotheses.
"""

    experiment_context = {
        'experiment_id': 'story-exp',
        'experiment_name': 'SOP Story',
        'scorecard_name': 'StoryCard',
        'score_name': 'StoryScore',
        'options': {'enable_mcp': True}
    }

    FakeO3Model._queue = [
        '{"tool":"plexus_feedback_analysis","arguments":{"scorecard_name":"StoryCard","score_name":"StoryScore"}}',
        '{"tool":"create_experiment_node","arguments":{"experiment_id":"story-exp","hypothesis_description":"GOAL: Reduce errors | METHOD: Adjust thresholds","node_name":"Hypothesis A"}}',
        '{"tool":"create_experiment_node","arguments":{"experiment_id":"story-exp","hypothesis_description":"GOAL: Improve recall | METHOD: Expand patterns","node_name":"Hypothesis B"}}',
        'Session summary: created two nodes after analysis.'
    ]

    from contextlib import ExitStack
    with ExitStack() as stack:
        stack.enter_context(patch('plexus.cli.experiment.experiment_sop_agent.LangChainMCPAdapter', FakeAdapter))
        stack.enter_context(patch('plexus.cli.experiment.experiment_sop_agent.call_tool', fake_call_tool))
        stack.enter_context(patch('langchain_openai.ChatOpenAI', FakeO3Model))
        stack.enter_context(patch('plexus.cli.experiment.sop_agent_base.StandardOperatingProcedureAgent._generate_sop_guidance', fake_orchestrator))
        experiment_agent = ExperimentSOPAgent(
            experiment_id='story-exp',
            mcp_server=FakeMCPServer(),
            client=FakeClient(),
            openai_api_key='test-key',
            experiment_context=experiment_context
        )
        ok = await experiment_agent.setup(experiment_yaml)
        assert ok, 'setup failed'
        result = await experiment_agent.execute_sop_guided_experiment()
        assert result['success'] is True
        assert result['nodes_created'] == 2
        assert 'plexus_feedback_analysis' in result['tool_names']
        assert 'create_experiment_node' in result['tool_names']
        print('SOP story runner: PASS')


if __name__ == '__main__':
    asyncio.run(main())
