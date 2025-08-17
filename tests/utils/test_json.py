import sys

import pytest

from webspark.utils.json import JSONHandler, deserialize_json, serialize_json


def test_json_serialization_deserialization():
    """Test that serialize_json and deserialize_json work correctly."""
    data = {
        "name": "John",
        "age": 30,
        "isStudent": False,
        "courses": ["Math", "Science"],
    }

    serialized_data = serialize_json(data)
    assert isinstance(serialized_data, bytes)

    deserialized_data = deserialize_json(serialized_data)
    assert deserialized_data == data


def test_deserialize_json_from_string():
    """Test deserialize_json with a string input."""
    json_string = '{"message": "Hello, World!"}'
    data = deserialize_json(json_string)
    assert data == {"message": "Hello, World!"}


def test_serialize_non_serializable():
    """Test serialize_json with a non-serializable object."""

    class NonSerializable:
        pass

    obj = NonSerializable()
    # It should fall back to str(obj)
    serialized = serialize_json(obj)
    deserialized = deserialize_json(serialized)
    assert isinstance(deserialized, str)
    assert str(obj) in deserialized


def test_deserialize_invalid_json_raises_error():
    """Test deserialize_json with invalid json raises an exception."""
    invalid_json_bytes = b'{"key": "value"'
    with pytest.raises(
        ValueError
    ):  # orjson/ujson raise ValueError, json raises JSONDecodeError (subclass)
        deserialize_json(invalid_json_bytes)

    invalid_json_string = '{"key": "value"'
    with pytest.raises(ValueError):
        deserialize_json(invalid_json_string)


def test_json_handler_orjson():
    """Test JSONHandler uses orjson if available."""
    try:
        import orjson  # noqa
    except ImportError:
        pytest.skip("orjson not installed")

    handler = JSONHandler()
    serializer = handler._get_serializer()
    assert "orjson" in serializer.__module__

    deserializer = handler._get_deserializer()
    assert "orjson" in deserializer.__module__


def test_json_handler_ujson(monkeypatch):
    """Test JSONHandler falls back to ujson."""
    monkeypatch.setitem(sys.modules, "orjson", None)
    try:
        import ujson  # noqa
    except ImportError:
        pytest.skip("ujson not installed")

    handler = JSONHandler()
    serializer = handler._get_serializer()
    assert "ujson" in serializer.__module__

    deserializer = handler._get_deserializer()
    assert "ujson" in deserializer.__module__


def test_json_handler_json(monkeypatch):
    """Test JSONHandler falls back to standard json."""
    monkeypatch.setitem(sys.modules, "orjson", None)
    monkeypatch.setitem(sys.modules, "ujson", None)

    handler = JSONHandler()
    serializer = handler._get_serializer()
    assert "json" in serializer.__module__

    deserializer = handler._get_deserializer()
    assert "json" in deserializer.__module__
