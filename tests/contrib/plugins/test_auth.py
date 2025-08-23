from unittest.mock import Mock

import pytest

from webspark.contrib.plugins.token_auth import TokenAuthPlugin
from webspark.utils import HTTPException


@pytest.fixture
def mock_handler():
    """Fixture for a mock view handler."""
    return Mock()


@pytest.fixture
def mock_context():
    """Fixture for a mock request context."""
    mock = Mock()
    mock.headers = {}
    mock.state = {}
    return mock


@pytest.fixture
def user_record():
    """Fixture for a sample user record."""
    return {"id": 1, "name": "Test User"}


def test_auth_plugin_success(mock_handler, mock_context, user_record):
    """
    Test that the plugin successfully authenticates a valid token
    and calls the handler.
    """
    token_loader = Mock(return_value=user_record)
    plugin = TokenAuthPlugin(token_loader=token_loader)
    mock_context.headers = {"authorization": "Token valid_token"}
    mock_context.state = {}

    wrapped_handler = plugin.apply(mock_handler)
    wrapped_handler(mock_context)

    token_loader.assert_called_once_with("valid_token")
    assert mock_context.state["user"] == user_record
    mock_handler.assert_called_once_with(mock_context)


def test_auth_plugin_missing_token(mock_handler, mock_context):
    """
    Test that the plugin raises a 401 HTTPException if the header is missing.
    """
    token_loader = Mock()
    plugin = TokenAuthPlugin(token_loader=token_loader)

    wrapped_handler = plugin.apply(mock_handler)

    with pytest.raises(HTTPException) as exc_info:
        wrapped_handler(mock_context)

    assert exc_info.value.status_code == 401
    assert "Authentication credentials were not provided" in exc_info.value.details
    mock_context.set_header.assert_called_once_with("WWW-Authenticate", plugin.scheme)
    mock_handler.assert_not_called()


def test_auth_plugin_wrong_scheme(mock_handler, mock_context):
    """
    Test that the plugin raises a 401 HTTPException if the scheme is wrong.
    """
    token_loader = Mock()
    plugin = TokenAuthPlugin(token_loader=token_loader)
    mock_context.headers = {"authorization": "Bearer sometoken"}

    wrapped_handler = plugin.apply(mock_handler)

    with pytest.raises(HTTPException) as exc_info:
        wrapped_handler(mock_context)

    assert exc_info.value.status_code == 401
    assert "Invalid authentication scheme" in exc_info.value.details
    mock_context.set_header.assert_called_once_with("WWW-Authenticate", plugin.scheme)
    mock_handler.assert_not_called()


def test_auth_plugin_invalid_token(mock_handler, mock_context):
    """
    Test that the plugin raises a 401 HTTPException if the token is invalid.
    """
    token_loader = Mock(return_value=None)
    plugin = TokenAuthPlugin(token_loader=token_loader)
    mock_context.headers = {"authorization": "Token invalid_token"}

    wrapped_handler = plugin.apply(mock_handler)

    with pytest.raises(HTTPException) as exc_info:
        wrapped_handler(mock_context)

    assert exc_info.value.status_code == 401
    assert "Invalid token" in exc_info.value.details
    mock_context.set_header.assert_called_once_with("WWW-Authenticate", plugin.scheme)
    mock_handler.assert_not_called()


def test_auth_plugin_custom_scheme(mock_handler, mock_context, user_record):
    """
    Test that the plugin respects custom authentication schemes.
    """
    token_loader = Mock(return_value=user_record)
    plugin = TokenAuthPlugin(
        token_loader=token_loader,
        scheme="Bearer",
    )
    mock_context.headers = {"authorization": "Bearer custom_token"}

    wrapped_handler = plugin.apply(mock_handler)
    wrapped_handler(mock_context)

    token_loader.assert_called_once_with("custom_token")
    assert mock_context.state["user"] == user_record
    mock_handler.assert_called_once_with(mock_context)

    # Missing Authorization header
    mock_context.headers = {}
    with pytest.raises(HTTPException) as exc_info:
        wrapped_handler(mock_context)

    assert exc_info.value.status_code == 401
    mock_context.set_header.assert_called_with("WWW-Authenticate", plugin.scheme)
