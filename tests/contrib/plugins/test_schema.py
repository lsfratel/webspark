from unittest.mock import Mock, create_autospec

import pytest

from webspark.contrib.plugins.schema import SchemaPlugin
from webspark.core.views import View
from webspark.http.context import Context
from webspark.utils import HTTPException
from webspark.validation import Schema
from webspark.validation.fields import IntegerField, StringField


# Sample schema for testing
class UserSchema(Schema):
    name = StringField(required=True, max_length=100)
    age = IntegerField(min_value=0, max_value=150)


@pytest.fixture
def schema_plugin():
    return SchemaPlugin(
        schema=UserSchema,
        prop="body",
    )


@pytest.fixture
def mock_context():
    return create_autospec(Context)


@pytest.fixture
def mock_view():
    view = create_autospec(View)
    view.build_ctx.return_value = {}
    view.ctx = Mock()
    return view


def test_schema_plugin_initialization():
    """Test SchemaPlugin initialization with various parameters."""
    # Basic initialization
    plugin = SchemaPlugin(
        schema=UserSchema,
        prop="body",
    )
    assert plugin.schema == UserSchema
    assert plugin.prop == "body"
    assert plugin.kwargs == {}
    assert plugin.param is None

    # Initialization with all parameters
    plugin = SchemaPlugin(
        schema=UserSchema,
        prop="query_params",
        kwargs={"partial": True},
        param="validated_data",
    )
    assert plugin.schema == UserSchema
    assert plugin.prop == "query_params"
    assert plugin.kwargs == {"partial": True}
    assert plugin.param == "validated_data"


def test_schema_plugin_apply_success(schema_plugin, mock_view):
    """Test successful validation and data injection."""

    def mock_handler(view, body=None):
        assert body == {"name": "John", "age": 30}
        return "success"

    # Mock the context with valid data
    mock_context = Mock()
    mock_context.body = {"name": "John", "age": 30}
    mock_view.ctx = mock_context
    mock_view.build_ctx.return_value = {}

    # Apply the plugin
    wrapped_handler = schema_plugin.apply(mock_handler)

    # Execute the wrapped handler
    result = wrapped_handler(mock_view)

    assert result == "success"


def test_schema_plugin_apply_validation_failure(schema_plugin, mock_view):
    """Test that HTTPException is raised on validation failure."""

    def mock_handler(view, validated_data=None):
        # This should not be called
        raise AssertionError("Handler should not be called when validation fails")

    # Mock the context with invalid data
    mock_context = Mock()
    mock_context.body = {"name": "John", "age": -5}  # Invalid age
    mock_view.ctx = mock_context
    mock_view.build_ctx.return_value = {}

    # Apply the plugin
    wrapped_handler = schema_plugin.apply(mock_handler)

    # Execute the wrapped handler and expect an exception
    with pytest.raises(HTTPException) as exc_info:
        wrapped_handler(mock_view)

    # Verify the exception details
    assert exc_info.value.status_code == 400
    assert "age" in exc_info.value.details


def test_schema_plugin_apply_with_custom_kw(schema_plugin, mock_view):
    """Test that data is injected with the correct keyword argument."""

    def mock_handler(view, custom_data=None):
        assert custom_data == {"name": "Alice", "age": 35}
        return "success"

    # Create a plugin with a custom kw
    custom_plugin = SchemaPlugin(schema=UserSchema, prop="body", param="custom_data")

    # Mock the context with valid data
    mock_context = Mock()
    mock_context.body = {"name": "Alice", "age": 35}
    mock_view.ctx = mock_context
    mock_view.build_ctx.return_value = {}

    # Apply the plugin
    wrapped_handler = custom_plugin.apply(mock_handler)

    # Execute the wrapped handler
    result = wrapped_handler(mock_view)

    assert result == "success"


def test_schema_plugin_apply_no_data(schema_plugin, mock_view):
    """Test validation failure when no data is provided."""

    def mock_handler(view, body=None):
        # This should not be called
        raise AssertionError("Handler should not be called when validation fails")

    # Mock the context with no data
    mock_context = Mock()
    mock_context.body = None
    mock_view.ctx = mock_context
    mock_view.build_ctx.return_value = {}

    # Apply the plugin
    wrapped_handler = schema_plugin.apply(mock_handler)

    # Execute the wrapped handler and expect an exception
    with pytest.raises(HTTPException) as exc_info:
        wrapped_handler(mock_view)

    # Verify the exception details
    assert exc_info.value.status_code == 400
    # When data is None, the schema validation will fail on the first required field
    assert "name" in exc_info.value.details


def test_schema_plugin_apply_missing_required_field(schema_plugin, mock_view):
    """Test validation failure when a required field is missing."""

    def mock_handler(view, validated_data=None):
        # This should not be called
        raise AssertionError("Handler should not be called when validation fails")

    # Mock the context with missing required field
    mock_context = Mock()
    mock_context.body = {"age": 30}  # Missing name
    mock_view.ctx = mock_context
    mock_view.build_ctx.return_value = {}

    # Apply the plugin
    wrapped_handler = schema_plugin.apply(mock_handler)

    # Execute the wrapped handler and expect an exception
    with pytest.raises(HTTPException) as exc_info:
        wrapped_handler(mock_view)

    # Verify the exception details
    assert exc_info.value.status_code == 400
    assert "name" in exc_info.value.details
