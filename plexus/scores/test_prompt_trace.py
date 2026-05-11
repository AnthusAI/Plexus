from plexus.scores.prompt_trace import (
    build_prompt_diagnostics,
    rendered_messages_from_langchain,
)


def test_prompt_diagnostics_detects_xcc_placeholder():
    diagnostics = build_prompt_diagnostics(
        [{"role": "system", "content": "Disposition: {xcc: disposition}"}],
        node_name="classifier",
        metadata={"disposition": "Set Outside 48"},
    )

    unresolved = diagnostics["unresolved_placeholders"]

    assert unresolved[0]["type"] == "xcc"
    assert unresolved[0]["placeholder"] == "{xcc: disposition}"
    assert unresolved[0]["node_name"] == "classifier"
    assert unresolved[0]["role"] == "system"
    assert unresolved[0]["metadata_keys"] == ["disposition"]


def test_prompt_diagnostics_detects_unrendered_jinja_placeholder():
    diagnostics = build_prompt_diagnostics(
        [{"role": "human", "content": "Disposition: {{ metadata.disposition }}"}],
        node_name="classifier",
        metadata={"disposition": "Set Outside 48"},
    )

    assert diagnostics["unresolved_placeholders"][0]["type"] == "jinja"


def test_prompt_diagnostics_ignores_rendered_metadata_values():
    diagnostics = build_prompt_diagnostics(
        [{"role": "human", "content": "Disposition: Set Outside 48"}],
        node_name="classifier",
        metadata={"disposition": "Set Outside 48"},
    )

    assert diagnostics["unresolved_placeholders"] == []


def test_rendered_messages_normalizes_dict_messages():
    messages = rendered_messages_from_langchain(
        [{"type": "human", "content": "Hello"}]
    )

    assert messages == [{"role": "human", "content": "Hello"}]
