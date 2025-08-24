from unittest.mock import Mock, create_autospec

import pytest

from webspark.contrib.plugins.schema import SchemaPlugin
from webspark.core.views import View
from webspark.utils import HTTPException
from webspark.utils.decorators import apply
from webspark.validation import Schema
from webspark.validation.fields import IntegerField, StringField


# Sample schema for testing
class UserSchema(Schema):
    name = StringField(required=True, max_length=100)
    age = IntegerField(min_value=0, max_value=150)


def test_apply_single_plugin():
    """Test applying a single plugin using the apply decorator."""

    def mock_handler(view, validated_data=None):
        return "success"

    # Create a plugin
    plugin = SchemaPlugin(schema=UserSchema, prop="body", kw="validated_data")

    # Apply the plugin using the apply decorator
    decorated_handler = apply(plugin)(mock_handler)

    # Verify that the handler was wrapped
    assert decorated_handler != mock_handler

    # Create a mock view with valid data
    mock_view = create_autospec(View)
    mock_context = Mock()
    mock_context.body = {"name": "John", "age": 30}
    mock_view.ctx = mock_context
    mock_view.build_ctx.return_value = {}

    # Execute the decorated handler
    result = decorated_handler(mock_view)

    assert result == "success"


def test_apply_multiple_plugins():
    """Test applying multiple plugins using the apply decorator."""

    call_order = []

    # Create mock plugins that track call order
    class TrackingPlugin:
        def __init__(self, name):
            self.name = name

        def apply(self, handler):
            def wrapper(*args, **kwargs):
                call_order.append(f"enter_{self.name}")
                result = handler(*args, **kwargs)
                call_order.append(f"exit_{self.name}")
                return result

            return wrapper

    def mock_handler(view):
        call_order.append("handler")
        return "success"

    # Apply multiple plugins
    plugin1 = TrackingPlugin("plugin1")
    plugin2 = TrackingPlugin("plugin2")

    decorated_handler = apply(plugin1, plugin2)(mock_handler)

    # Execute the decorated handler
    mock_view = create_autospec(View)
    result = decorated_handler(mock_view)

    assert result == "success"
    # Verify the order of execution:
    # plugin1 is applied first, then plugin2, so plugin2 wrapper is outermost
    assert call_order == [
        "enter_plugin2",
        "enter_plugin1",
        "handler",
        "exit_plugin1",
        "exit_plugin2",
    ]


def test_apply_plugin_validation_failure():
    """Test that apply correctly handles plugin validation failures."""

    def mock_handler(view, validated_data=None):
        # This should not be called
        raise AssertionError("Handler should not be called when validation fails")

    # Create a plugin
    plugin = SchemaPlugin(schema=UserSchema, prop="body", kw="validated_data")

    # Apply the plugin using the apply decorator
    decorated_handler = apply(plugin)(mock_handler)

    # Create a mock view with invalid data
    mock_view = create_autospec(View)
    mock_context = Mock()
    mock_context.body = {"name": "John", "age": -5}  # Invalid age
    mock_view.ctx = mock_context
    mock_view.build_ctx.return_value = {}

    # Execute the decorated handler and expect an exception
    with pytest.raises(HTTPException) as exc_info:
        decorated_handler(mock_view)

    # Verify the exception details
    assert exc_info.value.status_code == 400
    assert "age" in exc_info.value.details


def test_apply_no_plugins():
    """Test applying the apply decorator with no plugins."""

    def mock_handler(view):
        return "success"

    # Apply no plugins (this should just return the original function)
    decorated_handler = apply()(mock_handler)

    # Should be the same function since no plugins were applied
    assert decorated_handler == mock_handler

    # Execute the handler
    mock_view = create_autospec(View)
    result = decorated_handler(mock_view)

    assert result == "success"
