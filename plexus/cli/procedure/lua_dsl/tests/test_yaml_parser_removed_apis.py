import pytest

from plexus.cli.procedure.lua_dsl.yaml_parser import ProcedureConfigError, ProcedureYAMLParser


def test_parser_rejects_removed_graphnode_api():
    yaml_content = """
name: removed graph api
version: "1"
class: LuaDSL
agents:
  worker:
    system_prompt: test
    initial_message: test
workflow: |
  local node = GraphNode.create("obsolete")
"""

    with pytest.raises(ProcedureConfigError, match="removed GraphNode APIs"):
        ProcedureYAMLParser.parse(yaml_content)


def test_parser_rejects_removed_node_backed_session_persistence():
    yaml_content = """
name: removed session api
version: "1"
class: LuaDSL
agents:
  worker:
    system_prompt: test
    initial_message: test
workflow: |
  Session.save_to_node({ id = "node-1" })
"""

    with pytest.raises(ProcedureConfigError, match="node-backed session persistence"):
        ProcedureYAMLParser.parse(yaml_content)
