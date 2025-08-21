import sys
from functools import partial

import pytest

from webspark.utils.json import JSONHandler, deserialize_json, serialize_json


def test_json_serialization_deserialization():
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
    json_string = '{"message": "Hello, World!"}'
    data = deserialize_json(json_string)
    assert data == {"message": "Hello, World!"}


def test_serialize_non_serializable():
    class NonSerializable:
        pass

    obj = NonSerializable()
    serialized = serialize_json(obj)
    deserialized = deserialize_json(serialized)
    assert isinstance(deserialized, str)
    assert str(obj) in deserialized


def test_deserialize_invalid_json_raises_error():
    invalid_json_bytes = b'{"key": "value"'
    with pytest.raises(ValueError):
        deserialize_json(invalid_json_bytes)

    invalid_json_string = '{"key": "value"'
    with pytest.raises(ValueError):
        deserialize_json(invalid_json_string)


def test_json_handler_orjson():
    try:
        import orjson
    except ImportError:
        pytest.skip("orjson not installed")

    handler = JSONHandler()
    serializer = handler._get_serializer()
    assert "orjson" in serializer.__module__

    deserializer = handler._get_deserializer()
    assert "orjson" in deserializer.__module__


def test_json_handler_ujson(monkeypatch):
    monkeypatch.setitem(sys.modules, "orjson", None)
    try:
        import ujson
    except ImportError:
        pytest.skip("ujson not installed")

    handler = JSONHandler()
    serializer = handler._get_serializer()
    assert "ujson" in serializer.__module__

    deserializer = handler._get_deserializer()
    assert "ujson" in deserializer.__module__


def test_json_handler_json(monkeypatch):
    monkeypatch.setitem(sys.modules, "orjson", None)
    monkeypatch.setitem(sys.modules, "ujson", None)

    handler = JSONHandler()
    serializer = handler._get_serializer()
    assert isinstance(serializer, partial)
    assert "json" in serializer.func.__module__

    deserializer = handler._get_deserializer()
    assert "json" in deserializer.__module__
