from unittest.mock import Mock

import pytest

from webspark.contrib.plugins.allowed_hosts import AllowedHostsPlugin
from webspark.utils import HTTPException


@pytest.fixture
def mock_handler():
    """Fixture for a mock handler."""
    return Mock()


@pytest.fixture
def mock_context():
    """Fixture for a mock context."""
    return Mock()


def test_allowed_hosts_valid_host(mock_handler, mock_context):
    plugin = AllowedHostsPlugin(allowed_hosts=["test.com"])
    mock_context.host = "test.com"
    wrapped_handler = plugin.apply(mock_handler)

    wrapped_handler(mock_context)

    mock_handler.assert_called_once_with(mock_context)


def test_allowed_hosts_invalid_host(mock_handler, mock_context):
    plugin = AllowedHostsPlugin(allowed_hosts=["test.com"])
    mock_context.host = "invalid.com"
    wrapped_handler = plugin.apply(mock_handler)

    with pytest.raises(HTTPException) as exc_info:
        wrapped_handler(mock_context)

    assert exc_info.value.status_code == 400
    assert "Host not allowed" in exc_info.value.details
    mock_handler.assert_not_called()


def test_allowed_hosts_wildcard_subdomain(mock_handler, mock_context):
    plugin = AllowedHostsPlugin(allowed_hosts=[".test.com"])
    mock_context.host = "sub.test.com"
    wrapped_handler = plugin.apply(mock_handler)

    wrapped_handler(mock_context)

    mock_handler.assert_called_once_with(mock_context)


def test_allowed_hosts_wildcard_root_domain(mock_handler, mock_context):
    plugin = AllowedHostsPlugin(allowed_hosts=[".test.com"])
    mock_context.host = "test.com"
    wrapped_handler = plugin.apply(mock_handler)

    wrapped_handler(mock_context)

    mock_handler.assert_called_once_with(mock_context)


def test_allowed_hosts_wildcard_invalid_domain(mock_handler, mock_context):
    plugin = AllowedHostsPlugin(allowed_hosts=[".test.com"])
    mock_context.host = "invalid.com"
    wrapped_handler = plugin.apply(mock_handler)

    with pytest.raises(HTTPException) as exc_info:
        wrapped_handler(mock_context)

    assert exc_info.value.status_code == 400
    assert "Host not allowed" in exc_info.value.details
    mock_handler.assert_not_called()


def test_allowed_hosts_star_allows_all(mock_handler, mock_context):
    plugin = AllowedHostsPlugin(allowed_hosts=["*"])
    mock_context.host = "any.host.com"
    wrapped_handler = plugin.apply(mock_handler)

    wrapped_handler(mock_context)

    mock_handler.assert_called_once_with(mock_context)


def test_allowed_hosts_missing_host_header(mock_handler, mock_context):
    plugin = AllowedHostsPlugin(allowed_hosts=["example.com"])
    mock_context.host = ""
    wrapped_handler = plugin.apply(mock_handler)

    with pytest.raises(HTTPException) as exc_info:
        wrapped_handler(mock_context)

    assert exc_info.value.status_code == 400
    assert "Invalid or missing host header" in exc_info.value.details
    mock_handler.assert_not_called()


def test_allowed_hosts_strips_port(mock_handler, mock_context):
    plugin = AllowedHostsPlugin(allowed_hosts=["test.com"])
    mock_context.host = "test.com:8000"
    wrapped_handler = plugin.apply(mock_handler)

    wrapped_handler(mock_context)

    mock_handler.assert_called_once_with(mock_context)
