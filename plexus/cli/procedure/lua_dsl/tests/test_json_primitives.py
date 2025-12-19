"""
Tests for Json Primitive - JSON serialization/deserialization.

Tests all Json primitive methods:
- Json.encode(data) - Serialize to JSON string
- Json.decode(json_str) - Parse JSON string to data
"""

import pytest
import json
from unittest.mock import Mock
from plexus.cli.procedure.lua_dsl.primitives.json import JsonPrimitive


@pytest.fixture
def json_primitive():
    """Create a fresh Json primitive without Lua sandbox."""
    return JsonPrimitive(lua_sandbox=None)


@pytest.fixture
def json_primitive_with_sandbox():
    """Create a Json primitive with mock Lua sandbox."""
    mock_sandbox = Mock()
    mock_lua = Mock()
    mock_sandbox.lua = mock_lua

    # Mock lua.table() to return a dict-like object
    def create_table():
        return {}
    mock_lua.table.side_effect = create_table

    return JsonPrimitive(lua_sandbox=mock_sandbox)


class TestJsonEncode:
    """Tests for Json.encode()"""

    def test_encode_simple_dict(self, json_primitive):
        """Should encode simple dict to JSON."""
        data = {"name": "Alice", "age": 30}
        result = json_primitive.encode(data)

        # Parse back to verify
        parsed = json.loads(result)
        assert parsed["name"] == "Alice"
        assert parsed["age"] == 30

    def test_encode_nested_dict(self, json_primitive):
        """Should encode nested dict structures."""
        data = {
            "user": {"name": "Bob", "id": 123},
            "settings": {"theme": "dark", "notifications": True}
        }
        result = json_primitive.encode(data)

        parsed = json.loads(result)
        assert parsed["user"]["name"] == "Bob"
        assert parsed["settings"]["theme"] == "dark"

    def test_encode_list(self, json_primitive):
        """Should encode lists."""
        data = {"items": [1, 2, 3, 4, 5]}
        result = json_primitive.encode(data)

        parsed = json.loads(result)
        assert parsed["items"] == [1, 2, 3, 4, 5]

    def test_encode_mixed_types(self, json_primitive):
        """Should encode mixed types."""
        data = {
            "string": "text",
            "integer": 42,
            "float": 3.14,
            "boolean": True,
            "null": None,
            "list": [1, 2, 3],
            "dict": {"key": "value"}
        }
        result = json_primitive.encode(data)

        parsed = json.loads(result)
        assert parsed["string"] == "text"
        assert parsed["integer"] == 42
        assert parsed["float"] == 3.14
        assert parsed["boolean"] is True
        assert parsed["null"] is None
        assert parsed["list"] == [1, 2, 3]
        assert parsed["dict"] == {"key": "value"}

    def test_encode_empty_dict(self, json_primitive):
        """Should encode empty dict."""
        result = json_primitive.encode({})
        assert result == "{}"

    def test_encode_empty_list(self, json_primitive):
        """Should encode empty list."""
        result = json_primitive.encode([])
        assert result == "[]"

    def test_encode_string_primitive(self, json_primitive):
        """Should encode string primitive."""
        result = json_primitive.encode("hello")
        assert result == '"hello"'

    def test_encode_number_primitive(self, json_primitive):
        """Should encode number primitives."""
        assert json_primitive.encode(42) == "42"
        assert json_primitive.encode(3.14) == "3.14"

    def test_encode_boolean_primitive(self, json_primitive):
        """Should encode boolean primitives."""
        assert json_primitive.encode(True) == "true"
        assert json_primitive.encode(False) == "false"

    def test_encode_none_primitive(self, json_primitive):
        """Should encode None as null."""
        assert json_primitive.encode(None) == "null"

    def test_encode_unicode_strings(self, json_primitive):
        """Should encode unicode strings."""
        data = {"name": "张三", "greeting": "こんにちは"}
        result = json_primitive.encode(data)

        parsed = json.loads(result)
        assert parsed["name"] == "张三"
        assert parsed["greeting"] == "こんにちは"

    def test_encode_list_of_dicts(self, json_primitive):
        """Should encode list of dicts."""
        data = [
            {"id": 1, "name": "Alice"},
            {"id": 2, "name": "Bob"},
            {"id": 3, "name": "Charlie"}
        ]
        result = json_primitive.encode(data)

        parsed = json.loads(result)
        assert len(parsed) == 3
        assert parsed[0]["name"] == "Alice"
        assert parsed[2]["id"] == 3

    def test_encode_special_characters(self, json_primitive):
        """Should encode special characters correctly."""
        data = {"text": "Line1\nLine2\tTab\r\n"}
        result = json_primitive.encode(data)

        parsed = json.loads(result)
        assert parsed["text"] == "Line1\nLine2\tTab\r\n"

    def test_encode_invalid_data_raises_error(self, json_primitive):
        """Should raise ValueError for non-serializable data."""
        class CustomObject:
            pass

        with pytest.raises(ValueError, match="Failed to encode to JSON"):
            json_primitive.encode(CustomObject())


class TestJsonDecode:
    """Tests for Json.decode()"""

    def test_decode_simple_object(self, json_primitive):
        """Should decode simple JSON object."""
        json_str = '{"name": "Alice", "age": 30}'
        result = json_primitive.decode(json_str)

        assert result["name"] == "Alice"
        assert result["age"] == 30

    def test_decode_nested_object(self, json_primitive):
        """Should decode nested JSON objects."""
        json_str = '{"user": {"name": "Bob", "id": 123}}'
        result = json_primitive.decode(json_str)

        assert result["user"]["name"] == "Bob"
        assert result["user"]["id"] == 123

    def test_decode_array(self, json_primitive):
        """Should decode JSON arrays."""
        json_str = '[1, 2, 3, 4, 5]'
        result = json_primitive.decode(json_str)

        assert result == [1, 2, 3, 4, 5]

    def test_decode_mixed_types(self, json_primitive):
        """Should decode mixed types."""
        json_str = '{"string": "text", "number": 42, "bool": true, "null": null, "array": [1, 2]}'
        result = json_primitive.decode(json_str)

        assert result["string"] == "text"
        assert result["number"] == 42
        assert result["bool"] is True
        assert result["null"] is None
        assert result["array"] == [1, 2]

    def test_decode_empty_object(self, json_primitive):
        """Should decode empty object."""
        result = json_primitive.decode('{}')
        assert result == {}

    def test_decode_empty_array(self, json_primitive):
        """Should decode empty array."""
        result = json_primitive.decode('[]')
        assert result == []

    def test_decode_string_primitive(self, json_primitive):
        """Should decode string primitive."""
        result = json_primitive.decode('"hello"')
        assert result == "hello"

    def test_decode_number_primitive(self, json_primitive):
        """Should decode number primitives."""
        assert json_primitive.decode('42') == 42
        assert json_primitive.decode('3.14') == 3.14

    def test_decode_boolean_primitive(self, json_primitive):
        """Should decode boolean primitives."""
        assert json_primitive.decode('true') is True
        assert json_primitive.decode('false') is False

    def test_decode_null_primitive(self, json_primitive):
        """Should decode null as None."""
        assert json_primitive.decode('null') is None

    def test_decode_unicode_strings(self, json_primitive):
        """Should decode unicode strings."""
        json_str = '{"name": "张三", "greeting": "こんにちは"}'
        result = json_primitive.decode(json_str)

        assert result["name"] == "张三"
        assert result["greeting"] == "こんにちは"

    def test_decode_array_of_objects(self, json_primitive):
        """Should decode array of objects."""
        json_str = '[{"id": 1, "name": "Alice"}, {"id": 2, "name": "Bob"}]'
        result = json_primitive.decode(json_str)

        assert len(result) == 2
        assert result[0]["name"] == "Alice"
        assert result[1]["id"] == 2

    def test_decode_with_whitespace(self, json_primitive):
        """Should handle JSON with extra whitespace."""
        json_str = '''
        {
            "name": "Alice",
            "age": 30
        }
        '''
        result = json_primitive.decode(json_str)

        assert result["name"] == "Alice"
        assert result["age"] == 30

    def test_decode_malformed_json_raises_error(self, json_primitive):
        """Should raise ValueError for malformed JSON."""
        with pytest.raises(ValueError, match="Failed to decode JSON"):
            json_primitive.decode('{"invalid": }')

    def test_decode_invalid_json_raises_error(self, json_primitive):
        """Should raise ValueError for invalid JSON."""
        with pytest.raises(ValueError, match="Failed to decode JSON"):
            json_primitive.decode('not json at all')

    def test_decode_incomplete_json_raises_error(self, json_primitive):
        """Should raise ValueError for incomplete JSON."""
        with pytest.raises(ValueError, match="Failed to decode JSON"):
            json_primitive.decode('{"incomplete":')


class TestJsonRoundTrip:
    """Tests for encode/decode round-trip conversion."""

    def test_roundtrip_simple_dict(self, json_primitive):
        """Should preserve data through encode/decode cycle."""
        original = {"name": "Alice", "age": 30, "active": True}

        encoded = json_primitive.encode(original)
        decoded = json_primitive.decode(encoded)

        assert decoded == original

    def test_roundtrip_nested_structure(self, json_primitive):
        """Should preserve nested structures."""
        original = {
            "user": {"id": 123, "name": "Bob"},
            "settings": {"theme": "dark", "notifications": True},
            "tags": ["python", "testing"]
        }

        encoded = json_primitive.encode(original)
        decoded = json_primitive.decode(encoded)

        assert decoded == original

    def test_roundtrip_array(self, json_primitive):
        """Should preserve arrays."""
        original = [1, 2, 3, 4, 5]

        encoded = json_primitive.encode(original)
        decoded = json_primitive.decode(encoded)

        assert decoded == original

    def test_roundtrip_unicode(self, json_primitive):
        """Should preserve unicode strings."""
        original = {"name": "张三", "city": "北京"}

        encoded = json_primitive.encode(original)
        decoded = json_primitive.decode(encoded)

        assert decoded == original

    def test_roundtrip_empty_structures(self, json_primitive):
        """Should preserve empty structures."""
        assert json_primitive.decode(json_primitive.encode({})) == {}
        assert json_primitive.decode(json_primitive.encode([])) == []

    def test_roundtrip_mixed_types(self, json_primitive):
        """Should preserve all JSON types."""
        original = {
            "string": "text",
            "int": 42,
            "float": 3.14,
            "bool": True,
            "null": None,
            "array": [1, 2, 3],
            "object": {"key": "value"}
        }

        encoded = json_primitive.encode(original)
        decoded = json_primitive.decode(encoded)

        assert decoded == original


class TestJsonLuaConversion:
    """Tests for _lua_to_python() and _python_to_lua() helpers."""

    def test_lua_to_python_dict(self, json_primitive):
        """Should convert dict to Python dict."""
        python_dict = {"key": "value", "num": 123}
        result = json_primitive._lua_to_python(python_dict)

        assert result == {"key": "value", "num": 123}

    def test_lua_to_python_nested(self, json_primitive):
        """Should recursively convert nested structures."""
        nested = {
            "level1": {
                "level2": {
                    "level3": "value"
                }
            }
        }
        result = json_primitive._lua_to_python(nested)

        assert result["level1"]["level2"]["level3"] == "value"

    def test_lua_to_python_primitives(self, json_primitive):
        """Should return primitives unchanged."""
        assert json_primitive._lua_to_python("string") == "string"
        assert json_primitive._lua_to_python(123) == 123
        assert json_primitive._lua_to_python(45.67) == 45.67
        assert json_primitive._lua_to_python(True) is True
        assert json_primitive._lua_to_python(None) is None

    def test_python_to_lua_without_sandbox(self, json_primitive):
        """Should return value unchanged without sandbox."""
        data = {"key": "value"}
        result = json_primitive._python_to_lua(data)

        assert result == data

    def test_python_to_lua_with_sandbox_dict(self, json_primitive_with_sandbox):
        """Should convert dict to Lua table with sandbox."""
        data = {"key": "value", "num": 42}
        result = json_primitive_with_sandbox._python_to_lua(data)

        # Result should be dict-like (mock table)
        assert isinstance(result, dict)
        assert result["key"] == "value"
        assert result["num"] == 42

    def test_python_to_lua_with_sandbox_list(self, json_primitive_with_sandbox):
        """Should convert list to 1-indexed Lua array with sandbox."""
        data = ["a", "b", "c"]
        result = json_primitive_with_sandbox._python_to_lua(data)

        # 1-indexed (Lua convention)
        assert isinstance(result, dict)
        assert result[1] == "a"
        assert result[2] == "b"
        assert result[3] == "c"

    def test_python_to_lua_primitives(self, json_primitive_with_sandbox):
        """Should return primitives unchanged."""
        assert json_primitive_with_sandbox._python_to_lua("string") == "string"
        assert json_primitive_with_sandbox._python_to_lua(123) == 123
        assert json_primitive_with_sandbox._python_to_lua(True) is True


class TestJsonIntegration:
    """Integration tests combining multiple operations."""

    def test_api_response_pattern(self, json_primitive):
        """Test typical API response handling pattern."""
        # Simulate encoding API response
        response = {
            "status": "success",
            "data": {
                "users": [
                    {"id": 1, "name": "Alice"},
                    {"id": 2, "name": "Bob"}
                ]
            },
            "timestamp": "2024-01-01T00:00:00Z"
        }

        json_str = json_primitive.encode(response)

        # Simulate receiving and decoding response
        decoded = json_primitive.decode(json_str)

        assert decoded["status"] == "success"
        assert len(decoded["data"]["users"]) == 2
        assert decoded["data"]["users"][0]["name"] == "Alice"

    def test_config_file_pattern(self, json_primitive):
        """Test config file read/write pattern."""
        # Simulate config
        config = {
            "database": {
                "host": "localhost",
                "port": 5432
            },
            "features": {
                "logging": True,
                "debug": False
            }
        }

        # Write config
        json_str = json_primitive.encode(config)

        # Read config back
        loaded_config = json_primitive.decode(json_str)

        assert loaded_config["database"]["host"] == "localhost"
        assert loaded_config["features"]["logging"] is True

    def test_multiple_operations(self, json_primitive):
        """Test multiple encode/decode operations."""
        data1 = {"type": "event", "id": 1}
        data2 = {"type": "event", "id": 2}
        data3 = {"type": "event", "id": 3}

        json1 = json_primitive.encode(data1)
        json2 = json_primitive.encode(data2)
        json3 = json_primitive.encode(data3)

        assert json_primitive.decode(json1)["id"] == 1
        assert json_primitive.decode(json2)["id"] == 2
        assert json_primitive.decode(json3)["id"] == 3


class TestJsonEdgeCases:
    """Edge case and error condition tests."""

    def test_very_large_dict(self, json_primitive):
        """Should handle large dicts."""
        large_dict = {f"key_{i}": f"value_{i}" for i in range(1000)}
        json_str = json_primitive.encode(large_dict)
        decoded = json_primitive.decode(json_str)

        assert len(decoded) == 1000
        assert decoded["key_0"] == "value_0"
        assert decoded["key_999"] == "value_999"

    def test_very_large_array(self, json_primitive):
        """Should handle large arrays."""
        large_array = list(range(1000))
        json_str = json_primitive.encode(large_array)
        decoded = json_primitive.decode(json_str)

        assert len(decoded) == 1000
        assert decoded[0] == 0
        assert decoded[999] == 999

    def test_deeply_nested_structure(self, json_primitive):
        """Should handle deeply nested structures."""
        nested = {"level": 1}
        current = nested
        for i in range(2, 11):
            current["next"] = {"level": i}
            current = current["next"]

        json_str = json_primitive.encode(nested)
        decoded = json_primitive.decode(json_str)

        # Navigate to deepest level
        current = decoded
        for _ in range(9):
            current = current["next"]
        assert current["level"] == 10

    def test_special_float_values(self, json_primitive):
        """Should handle special float values."""
        data = {"regular": 3.14, "zero": 0.0, "negative": -2.5}
        json_str = json_primitive.encode(data)
        decoded = json_primitive.decode(json_str)

        assert decoded["regular"] == 3.14
        assert decoded["zero"] == 0.0
        assert decoded["negative"] == -2.5

    def test_empty_strings(self, json_primitive):
        """Should handle empty strings."""
        data = {"empty": "", "not_empty": "value"}
        json_str = json_primitive.encode(data)
        decoded = json_primitive.decode(json_str)

        assert decoded["empty"] == ""
        assert decoded["not_empty"] == "value"

    def test_keys_with_special_chars(self, json_primitive):
        """Should handle keys with special characters."""
        data = {
            "key-with-dash": 1,
            "key.with.dot": 2,
            "key_with_underscore": 3,
            "key with space": 4
        }
        json_str = json_primitive.encode(data)
        decoded = json_primitive.decode(json_str)

        assert decoded["key-with-dash"] == 1
        assert decoded["key.with.dot"] == 2
        assert decoded["key with space"] == 4


class TestJsonRepr:
    """Tests for __repr__()"""

    def test_repr_format(self, json_primitive):
        """Should show JsonPrimitive in repr."""
        assert repr(json_primitive) == "JsonPrimitive()"

    def test_repr_consistent(self, json_primitive):
        """Should return consistent repr."""
        repr1 = repr(json_primitive)
        repr2 = repr(json_primitive)
        assert repr1 == repr2


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
