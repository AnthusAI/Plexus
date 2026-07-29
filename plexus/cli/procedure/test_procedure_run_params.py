"""Contracts for typed ``plexus procedure run --set`` values."""

from plexus.cli.procedure.procedures import _parse_set_parameter_value


def test_set_parameter_parser_preserves_json_arrays_and_nested_objects():
    assert _parse_set_parameter_value(
        '["opaque-one", "opaque-two"]'
    ) == ["opaque-one", "opaque-two"]
    assert _parse_set_parameter_value(
        '{"targets":[{"id":"one"},{"id":"two"}]}'
    ) == {"targets": [{"id": "one"}, {"id": "two"}]}


def test_set_parameter_parser_preserves_existing_scalar_coercion():
    assert _parse_set_parameter_value("true") is True
    assert _parse_set_parameter_value("false") is False
    assert _parse_set_parameter_value("12") == 12
    assert _parse_set_parameter_value("1.25") == 1.25
    assert _parse_set_parameter_value("opaque-value") == "opaque-value"


def test_set_parameter_parser_leaves_malformed_structured_text_visible():
    assert _parse_set_parameter_value('["unfinished"') == '["unfinished"'
