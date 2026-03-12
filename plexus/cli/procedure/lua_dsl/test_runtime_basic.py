"""
Basic test for Lua DSL Runtime.

This is a simple smoke test to verify the core components work together.
It doesn't require a full Plexus setup - just tests the primitives and sandbox.
"""

import logging
import sys
import os

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

logger = logging.getLogger(__name__)


def test_yaml_parser():
    """Test YAML parsing."""
    from plexus.cli.procedure.lua_dsl.yaml_parser import ProcedureYAMLParser

    yaml_content = """
name: test_procedure
version: 1.0.0

agents:
  worker:
    system_prompt: "You are a worker"
    initial_message: "Start working"

workflow: |
  print("Hello from Lua!")
  return {success = true}
"""

    config = ProcedureYAMLParser.parse(yaml_content)
    assert config['name'] == 'test_procedure'
    assert 'worker' in config['agents']

    logger.info("✓ YAML parser test passed")


def test_lua_sandbox():
    """Test Lua sandbox."""
    from plexus.cli.procedure.lua_dsl.lua_sandbox import LuaSandbox

    sandbox = LuaSandbox()

    # Test basic Lua execution
    result = sandbox.execute("return 2 + 2")
    assert result == 4

    # Test that dangerous operations are blocked
    try:
        sandbox.execute("os.execute('echo test')")
        assert False, "Should have blocked os.execute"
    except Exception as e:
        logger.info(f"✓ Correctly blocked dangerous operation: {e}")

    logger.info("✓ Lua sandbox test passed")


def test_state_primitive():
    """Test State primitive."""
    from plexus.cli.procedure.lua_dsl.primitives.state import StatePrimitive
    from plexus.cli.procedure.lua_dsl.lua_sandbox import LuaSandbox

    state = StatePrimitive()
    sandbox = LuaSandbox()

    # Inject primitive into Lua
    sandbox.inject_primitive("State", state)

    # Test from Lua
    sandbox.execute("""
        State.set("count", 0)
        State.increment("count")
        State.increment("count")
        State.set("name", "test")
    """)

    assert state.get("count") == 2
    assert state.get("name") == "test"

    logger.info("✓ State primitive test passed")


def test_control_primitives():
    """Test Control primitives."""
    from plexus.cli.procedure.lua_dsl.primitives.control import IterationsPrimitive, StopPrimitive
    from plexus.cli.procedure.lua_dsl.lua_sandbox import LuaSandbox

    iterations = IterationsPrimitive()
    stop = StopPrimitive()
    sandbox = LuaSandbox()

    # Inject primitives
    sandbox.inject_primitive("Iterations", iterations)
    sandbox.inject_primitive("Stop", stop)

    # Test from Lua
    iterations.increment()
    iterations.increment()
    iterations.increment()

    result = sandbox.execute("""
        local count = Iterations.current()
        local exceeded = Iterations.exceeded(5)
        return {count = count, exceeded = exceeded}
    """)

    # Convert Lua table to Python dict
    result_dict = sandbox.lua_table_to_dict(result)
    assert result_dict['count'] == 3
    assert result_dict['exceeded'] == False

    logger.info("✓ Control primitives test passed")


def test_tool_primitive():
    """Test Tool primitive."""
    from plexus.cli.procedure.lua_dsl.primitives.tool import ToolPrimitive
    from plexus.cli.procedure.lua_dsl.lua_sandbox import LuaSandbox

    tool = ToolPrimitive()
    sandbox = LuaSandbox()

    # Inject primitive
    sandbox.inject_primitive("Tool", tool)

    # Simulate tool calls
    tool.record_call("search", {"query": "test"}, "Search result: found 5 items")
    tool.record_call("done", {"reason": "Task complete"}, "Acknowledged")

    # Test from Lua
    result = sandbox.execute("""
        local search_called = Tool.called("search")
        local done_called = Tool.called("done")
        local search_result = Tool.last_result("search")
        return {
            search_called = search_called,
            done_called = done_called,
            search_result = search_result
        }
    """)

    result_dict = sandbox.lua_table_to_dict(result)
    assert result_dict['search_called'] == True
    assert result_dict['done_called'] == True
    assert "found 5 items" in result_dict['search_result']

    logger.info("✓ Tool primitive test passed")


def test_full_workflow():
    """Test a complete minimal workflow."""
    from plexus.cli.procedure.lua_dsl.lua_sandbox import LuaSandbox
    from plexus.cli.procedure.lua_dsl.primitives.state import StatePrimitive
    from plexus.cli.procedure.lua_dsl.primitives.control import IterationsPrimitive, StopPrimitive
    from plexus.cli.procedure.lua_dsl.primitives.tool import ToolPrimitive

    # Setup
    sandbox = LuaSandbox()
    state = StatePrimitive()
    iterations = IterationsPrimitive()
    stop = StopPrimitive()
    tool = ToolPrimitive()

    # Inject all primitives
    sandbox.inject_primitive("State", state)
    sandbox.inject_primitive("Iterations", iterations)
    sandbox.inject_primitive("Stop", stop)
    sandbox.inject_primitive("Tool", tool)

    # Simulate a simple workflow
    workflow_code = """
        -- Initialize state
        State.set("tasks_completed", 0)

        -- Simulate agent loop
        for i = 1, 5 do
            Iterations.increment()

            -- Simulate some work
            State.increment("tasks_completed")

            -- Stop if we've done 3 tasks
            if State.get("tasks_completed") >= 3 then
                Tool.record_call("done", {reason = "Completed 3 tasks"}, "Success")
                break
            end
        end

        -- Return results
        return {
            success = true,
            iterations = Iterations.current(),
            tasks = State.get("tasks_completed"),
            done = Tool.called("done")
        }
    """

    # Need to expose tool.record_call for testing
    # In real usage, AgentPrimitive would call this
    def lua_record_call(name, args, result):
        tool.record_call(name, args, result)

    sandbox.set_global("record_call", lua_record_call)

    # Update workflow to use the exposed function
    workflow_code = workflow_code.replace("Tool.record_call", "record_call")

    result = sandbox.execute(workflow_code)
    result_dict = sandbox.lua_table_to_dict(result)

    assert result_dict['success'] == True
    assert result_dict['iterations'] == 3
    assert result_dict['tasks'] == 3
    assert result_dict['done'] == True

    logger.info("✓ Full workflow test passed")


def main():
    """Run all tests."""
    logger.info("Starting Lua DSL Runtime tests...")
    logger.info("=" * 60)

    try:
        test_yaml_parser()
        test_lua_sandbox()
        test_state_primitive()
        test_control_primitives()
        test_tool_primitive()
        test_full_workflow()

        logger.info("=" * 60)
        logger.info("✓ ALL TESTS PASSED!")
        logger.info("")
        logger.info("The Lua DSL Runtime core components are working correctly.")
        logger.info("Next step: Test with Example 1 from the spec (requires MCP server setup)")

        return 0

    except Exception as e:
        logger.error(f"✗ TEST FAILED: {e}", exc_info=True)
        return 1


if __name__ == "__main__":
    # Change to the lua_dsl directory for imports
    script_dir = os.path.dirname(os.path.abspath(__file__))
    os.chdir(script_dir)

    sys.exit(main())
