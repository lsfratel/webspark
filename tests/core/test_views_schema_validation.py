from unittest.mock import Mock, patch

import pytest

from webspark.core.views import View
from webspark.utils import HTTPException


class MockRequest:
    """Mock request for testing."""

    def __init__(self, method="GET", query_params=None, body=None, env=None):
        self.method = method
        self.query_params = query_params or {}
        self.body = body or {}
        self.ENV = env or {}
        self.args = ()
        self.kwargs = {}


class MockResponse:
    """Mock response for testing."""

    def __init__(self, data="response"):
        self.data = data


class MockSchema:
    """Mock schema for testing."""

    def __init__(self, data=None, context=None):
        self.data = data
        self.context = context or {}
        self._is_valid = True
        self._validated_data = {"validated": True}
        self._errors = {}
        self.called_with = None

    def is_valid(self):
        return self._is_valid

    @property
    def validated_data(self):
        return self._validated_data

    @property
    def errors(self):
        return self._errors


def test_view_validate_schema_success():
    """Test View._validate_schema method with valid data."""

    class TestView(View):
        pass

    view = TestView()
    view.args = ()
    view.kwargs = {}
    view.request = MockRequest()

    # Create a mock schema that returns valid data
    mock_schema_cls = Mock()
    mock_schema_instance = MockSchema()
    mock_schema_cls.return_value = mock_schema_instance
    mock_schema_instance._is_valid = True
    mock_schema_instance._validated_data = {"key": "value"}

    validated_data, errors = view._validate_schema(mock_schema_cls, {"data": "test"})

    assert validated_data == {"key": "value"}
    assert errors == {}
    mock_schema_cls.assert_called_once_with(
        data={"data": "test"}, context=view.build_ctx()
    )


def test_view_validate_schema_failure():
    """Test View._validate_schema method with invalid data."""

    class TestView(View):
        pass

    view = TestView()
    view.args = ()
    view.kwargs = {}
    view.request = MockRequest()

    # Create a mock schema that returns invalid data
    mock_schema_cls = Mock()
    mock_schema_instance = MockSchema()
    mock_schema_cls.return_value = mock_schema_instance
    mock_schema_instance._is_valid = False
    mock_schema_instance._errors = {"field": ["error"]}

    with pytest.raises(HTTPException) as exc_info:
        view._validate_schema(mock_schema_cls, {"data": "test"})

    assert exc_info.value.status_code == 400
    assert exc_info.value.details == {"field": ["error"]}


def test_view_validate_schema_failure_no_raise():
    """Test View._validate_schema method with invalid data and raise_=False."""

    class TestView(View):
        pass

    view = TestView()
    view.args = ()
    view.kwargs = {}
    view.request = MockRequest()

    # Create a mock schema that returns invalid data
    mock_schema_cls = Mock()
    mock_schema_instance = MockSchema()
    mock_schema_cls.return_value = mock_schema_instance
    mock_schema_instance._is_valid = False
    mock_schema_instance._errors = {"field": ["error"]}
    mock_schema_instance._validated_data = {}

    validated_data, errors = view._validate_schema(
        mock_schema_cls, {"data": "test"}, raise_=False
    )

    assert validated_data == {}
    assert errors == {"field": ["error"]}


def test_view_validated_query_params_with_schema():
    """Test View.validated_query_params with schema."""

    class TestView(View):
        query_params_schema = MockSchema

    view = TestView()
    view.args = ()
    view.kwargs = {}
    query_params = {"key": "value"}
    view.request = MockRequest(query_params=query_params)

    # Test the actual _validate_schema call by not mocking it
    # Instead, let's test that the method calls _validate_schema correctly
    with patch.object(view, "_validate_schema") as mock_validate_schema:
        mock_validate_schema.return_value = ({"validated_key": "validated_value"}, {})

        _ = view.validated_query_params()

        # Check that _validate_schema was called with the right arguments
        mock_validate_schema.assert_called_once_with(
            TestView.query_params_schema, query_params, False
        )


def test_view_validated_query_params_with_schema_raise():
    """Test View.validated_query_params with schema and raise_=True."""

    class TestView(View):
        query_params_schema = MockSchema

    view = TestView()
    view.args = ()
    view.kwargs = {}
    query_params = {"key": "value"}
    view.request = MockRequest(query_params=query_params)

    # Patch the _validate_schema method to raise an exception
    with patch.object(view, "_validate_schema") as mock_validate_schema:
        mock_validate_schema.side_effect = HTTPException(
            {"field": ["error"]}, status_code=400
        )

        with pytest.raises(HTTPException) as exc_info:
            view.validated_query_params(raise_=True)

        assert exc_info.value.status_code == 400
        assert exc_info.value.details == {"field": ["error"]}


def test_view_validated_body_with_schema():
    """Test View.validated_body with schema."""

    class TestView(View):
        body_schema = MockSchema

    view = TestView()
    view.args = ()
    view.kwargs = {}
    body = {"key": "value"}
    view.request = MockRequest(body=body)

    # Test the actual _validate_schema call by not mocking it
    # Instead, let's test that the method calls _validate_schema correctly
    with patch.object(view, "_validate_schema") as mock_validate_schema:
        mock_validate_schema.return_value = ({"validated_key": "validated_value"}, {})

        _ = view.validated_body()

        # Check that _validate_schema was called with the right arguments
        mock_validate_schema.assert_called_once_with(TestView.body_schema, body, False)


def test_view_validated_body_with_schema_raise():
    """Test View.validated_body with schema and raise_=True."""

    class TestView(View):
        body_schema = MockSchema

    view = TestView()
    view.args = ()
    view.kwargs = {}
    body = {"key": "value"}
    view.request = MockRequest(body=body)

    # Patch the _validate_schema method to raise an exception
    with patch.object(view, "_validate_schema") as mock_validate_schema:
        mock_validate_schema.side_effect = HTTPException(
            {"field": ["error"]}, status_code=400
        )

        with pytest.raises(HTTPException) as exc_info:
            view.validated_body(raise_=True)

        assert exc_info.value.status_code == 400
        assert exc_info.value.details == {"field": ["error"]}
