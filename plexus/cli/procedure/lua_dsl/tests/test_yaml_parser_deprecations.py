"""Tests for deprecated graph-node token validation in YAML parser."""

import pytest

from plexus.cli.procedure.lua_dsl.yaml_parser import ProcedureConfigError, ProcedureYAMLParser


def _base_yaml(workflow: str) -> str:
    return f"""
name: parser-test
version: "1.0"
class: LuaDSL
agents:
  writer:
    system_prompt: "test"
    initial_message: "start"
workflow: |
{workflow}
"""


@pytest.mark.parametrize(
    "token_line",
    [
        "  GraphNode.create({})",
        "  Session.load_from_node(node)",
        "  Session.save_to_node(node)",
    ],
)
def test_parse_rejects_deprecated_graph_node_tokens(token_line: str):
    yaml_text = _base_yaml(
        f"  Session.append(\"USER\", \"hello\")\n{token_line}\n"
    )

    with pytest.raises(ProcedureConfigError, match="Deprecated graph-node API reference detected"):
        ProcedureYAMLParser.parse(yaml_text)


def test_parse_accepts_non_graph_workflow():
    yaml_text = _base_yaml(
        '  Session.append("USER", "hello")\n  Session.history()\n'
    )
    parsed = ProcedureYAMLParser.parse(yaml_text)

    assert parsed["name"] == "parser-test"
