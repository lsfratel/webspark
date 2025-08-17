from collections.abc import Callable
from typing import Any


class JSONHandler:
    """Handler for JSON serialization and deserialization with automatic library fallback.

    This class automatically detects and uses the fastest available JSON library:
    1. orjson (fastest, Rust-based)
    2. ujson (fast C implementation)
    3. json (standard library fallback)

    The handler caches the serializer/deserializer functions for optimal performance.
    """

    def __init__(self):
        """Initialize the JSONHandler with no cached serializers."""
        self._serializer_func = None
        self._deserializer_func = None

    def _get_serializer(self) -> Callable[[Any], bytes]:
        """Get the fastest available JSON serializer function.

        Returns:
            A function that serializes Python objects to JSON bytes.
            The function tries libraries in order: orjson -> ujson -> json
        """
        if self._serializer_func is not None:
            return self._serializer_func

        try:
            import orjson

            def serialize(obj: Any) -> bytes:
                return orjson.dumps(obj)

            self._serializer_func = serialize
            return self._serializer_func
        except ImportError:
            pass

        try:
            import ujson

            def serialize(obj: Any) -> bytes:
                return ujson.dumps(obj).encode("utf-8")

            self._serializer_func = serialize
            return self._serializer_func
        except ImportError:
            pass

        import json

        def serialize(obj: Any) -> bytes:
            return json.dumps(obj, separators=(",", ":")).encode("utf-8")

        self._serializer_func = serialize
        return self._serializer_func

    def _get_deserializer(self) -> Callable[[bytes | str], Any]:
        """Get the fastest available JSON deserializer function.

        Returns:
            A function that deserializes JSON data to Python objects.
            The function tries libraries in order: orjson -> ujson -> json
        """
        if self._deserializer_func is not None:
            return self._deserializer_func

        try:
            import orjson

            def deserialize(data: bytes | str) -> Any:
                return orjson.loads(data)

            self._deserializer_func = deserialize
            return self._deserializer_func
        except ImportError:
            pass

        try:
            import ujson

            def deserialize(data: bytes | str) -> Any:
                return ujson.loads(data)

            self._deserializer_func = deserialize
            return self._deserializer_func
        except ImportError:
            pass

        import json

        def deserialize(data: bytes | str) -> Any:
            return json.loads(data)

        self._deserializer_func = deserialize
        return self._deserializer_func


_json_handler = JSONHandler()


def serialize_json(obj: Any) -> bytes:
    """Serialize a Python object to JSON bytes.

    Automatically uses the fastest available JSON library (orjson > ujson > json).
    Falls back to string representation for non-serializable objects.

    Args:
        obj: The Python object to serialize.

    Returns:
        bytes: The JSON-serialized object as bytes.

    Example:
        data = {"name": "John", "age": 30}
        json_bytes = serialize_json(data)
        print(json_bytes)  # b'{"name":"John","age":30}'
    """
    try:
        serializer = _json_handler._get_serializer()
        return serializer(obj)
    except (TypeError, ValueError):
        import json

        return json.dumps(str(obj), separators=(",", ":")).encode("utf-8")


def deserialize_json(data: bytes | str) -> Any:
    """Deserialize JSON data (bytes or string) to Python objects.

    Automatically uses the fastest available JSON library (orjson > ujson > json).
    Handles both bytes and string inputs, with UTF-8 decoding for bytes.

    Args:
        data: The JSON data to deserialize (bytes or string).

    Returns:
        Any: The deserialized Python object.

    Example:
        # From bytes
        json_bytes = b'{"name":"John","age":30}'
        data = deserialize_json(json_bytes)
        print(data)  # {"name": "John", "age": 30}

        # From string
        json_string = '{"name":"John","age":30}'
        data = deserialize_json(json_string)
        print(data)  # {"name": "John", "age": 30}
    """
    try:
        deserializer = _json_handler._get_deserializer()
        return deserializer(data)
    except (TypeError, ValueError):
        import json

        if isinstance(data, bytes):
            data = data.decode("utf-8")
        return json.loads(data)
