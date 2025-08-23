from unittest.mock import Mock, patch

import pytest

from webspark.core.views import View
from webspark.utils import HTTPException


class MockRequest:
    def __init__(self, method="GET", query_params=None, body=None, env=None):
        self.method = method
        self.query_params = query_params or {}
        self.body = body or {}
        self.ENV = env or {}
        self.args = ()
        self.kwargs = {}


class MockResponse:
    def __init__(self, data="response"):
        self.data = data


class MockSchema:
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
    class TestView(View):
        pass

    view = TestView()
    view.args = ()
    view.kwargs = {}
    view.ctx = MockRequest()

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
    class TestView(View):
        pass

    view = TestView()
    view.args = ()
    view.kwargs = {}
    view.ctx = MockRequest()

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
    class TestView(View):
        pass

    view = TestView()
    view.args = ()
    view.kwargs = {}
    view.ctx = MockRequest()

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
    class TestView(View):
        query_params_schema = MockSchema

    view = TestView()
    view.args = ()
    view.kwargs = {}
    query_params = {"key": "value"}
    view.ctx = MockRequest(query_params=query_params)

    with patch.object(view, "_validate_schema") as mock_validate_schema:
        mock_validate_schema.return_value = ({"validated_key": "validated_value"}, {})

        _ = view.validated_query_params()

        mock_validate_schema.assert_called_once_with(
            TestView.query_params_schema, query_params, False
        )


def test_view_validated_query_params_with_schema_raise():
    class TestView(View):
        query_params_schema = MockSchema

    view = TestView()
    view.args = ()
    view.kwargs = {}
    query_params = {"key": "value"}
    view.ctx = MockRequest(query_params=query_params)

    with patch.object(view, "_validate_schema") as mock_validate_schema:
        mock_validate_schema.side_effect = HTTPException(
            {"field": ["error"]}, status_code=400
        )

        with pytest.raises(HTTPException) as exc_info:
            view.validated_query_params(raise_=True)

        assert exc_info.value.status_code == 400
        assert exc_info.value.details == {"field": ["error"]}


def test_view_validated_body_with_schema():
    class TestView(View):
        body_schema = MockSchema

    view = TestView()
    view.args = ()
    view.kwargs = {}
    body = {"key": "value"}
    view.ctx = MockRequest(body=body)

    with patch.object(view, "_validate_schema") as mock_validate_schema:
        mock_validate_schema.return_value = ({"validated_key": "validated_value"}, {})

        _ = view.validated_body()

        mock_validate_schema.assert_called_once_with(TestView.body_schema, body, False)


def test_view_validated_body_with_schema_raise():
    class TestView(View):
        body_schema = MockSchema

    view = TestView()
    view.args = ()
    view.kwargs = {}
    body = {"key": "value"}
    view.ctx = MockRequest(body=body)

    with patch.object(view, "_validate_schema") as mock_validate_schema:
        mock_validate_schema.side_effect = HTTPException(
            {"field": ["error"]}, status_code=400
        )

        with pytest.raises(HTTPException) as exc_info:
            view.validated_body(raise_=True)

        assert exc_info.value.status_code == 400
        assert exc_info.value.details == {"field": ["error"]}
