import pytest

from webspark.core.views import DEFAULT_ACTIONS, View


class MockRequest:
    """Mock request for testing."""

    def __init__(self, method="GET", query_params=None, body=None, env=None):
        self.method = method
        self.query_params = query_params or {}
        self.body = body or {}
        self.ENV = env or {}
        # These will be set by the dispatch method
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

    def is_valid(self):
        return self._is_valid

    @property
    def validated_data(self):
        return self._validated_data

    @property
    def errors(self):
        return self._errors


def test_view_default_actions():
    """Test DEFAULT_ACTIONS mapping."""
    assert "get" in DEFAULT_ACTIONS
    assert DEFAULT_ACTIONS["get"] == "handle_get"
    assert "post" in DEFAULT_ACTIONS
    assert DEFAULT_ACTIONS["post"] == "handle_post"
    assert len(DEFAULT_ACTIONS) == 9  # All HTTP methods


def test_view_request_property():
    """Test View request property."""
    view = View()
    request = MockRequest()

    view.request = request
    assert view.request is request
    assert view.__request__ is request


def test_view_as_view_default_actions():
    """Test View.as_view with default actions."""

    class TestView(View):
        def handle_get(self, request):
            return MockResponse("get_response")

        def handle_post(self, request):
            return MockResponse("post_response")

    view_func = TestView.as_view()

    assert callable(view_func)
    assert hasattr(view_func, "http_methods")
    assert "get" in view_func.http_methods
    assert "post" in view_func.http_methods
    assert (
        "head" in view_func.http_methods
    )  # Should be added automatically when get is present


def test_view_as_view_custom_actions():
    """Test View.as_view with custom actions."""

    class TestView(View):
        def custom_get_handler(self, request):
            return MockResponse("custom_get")

        def custom_post_handler(self, request):
            return MockResponse("custom_post")

    actions = {"get": "custom_get_handler", "post": "custom_post_handler"}

    view_func = TestView.as_view(actions=actions)

    assert callable(view_func)
    assert hasattr(view_func, "http_methods")
    assert "get" in view_func.http_methods
    assert "post" in view_func.http_methods
    assert "head" in view_func.http_methods  # Should be added automatically


def test_view_as_view_no_actions():
    """Test View.as_view with no actions."""

    class TestView(View):
        pass

    view_func = TestView.as_view()

    assert callable(view_func)
    assert hasattr(view_func, "http_methods")
    assert len(view_func.http_methods) == 0


def test_view_as_view_head_automatically_added():
    """Test that HEAD is automatically added when GET is present."""

    class TestView(View):
        def handle_get(self, request):
            return MockResponse("get_response")

    actions = {"get": "handle_get"}
    view_func = TestView.as_view(actions=actions)

    assert "head" in view_func.http_methods
    # Since http_methods is a dict_keys object, we just check if it contains the key


def test_view_dispatch():
    """Test View.dispatch method."""

    class TestView(View):
        def handle_get(self, request, *args, **kwargs):
            return MockResponse(f"get_response_{args}_{kwargs}")

    view = TestView()
    view.action_map = {"get": "handle_get"}
    request = MockRequest(method="GET")

    response = view.dispatch(request, "arg1", "arg2", kwarg1="value1")

    assert isinstance(response, MockResponse)
    assert hasattr(view, "args")
    assert hasattr(view, "kwargs")
    assert hasattr(view, "request")
    assert view.request is request


def test_view_dispatch_with_custom_action():
    """Test View.dispatch with custom action mapping."""

    class TestView(View):
        def custom_handler(self, request):
            return MockResponse("custom_response")

    view = TestView()
    view.action_map = {"post": "custom_handler"}
    request = MockRequest(method="POST")

    response = view.dispatch(request)

    assert isinstance(response, MockResponse)
    assert response.data == "custom_response"


def test_view_build_ctx():
    """Test View.build_ctx method."""
    view = View()
    view.args = ("arg1", "arg2")
    view.kwargs = {"kwarg1": "value1"}
    view.request = MockRequest()

    ctx = view.build_ctx()

    assert isinstance(ctx, dict)
    assert ctx["view"] is view
    assert ctx["args"] == ("arg1", "arg2")
    assert ctx["kwargs"] == {"kwarg1": "value1"}
    assert ctx["request"] is view.request


def test_view_validated_query_params_no_schema():
    """Test View.validated_query_params with no schema."""
    view = View()
    query_params = {"key": "value"}
    view.request = MockRequest(query_params=query_params)

    result = view.validated_query_params()

    assert result == query_params


def test_view_validated_body_no_schema():
    """Test View.validated_body with no schema."""
    view = View()
    body = {"key": "value"}
    view.request = MockRequest(body=body)

    result = view.validated_body()

    assert result == body


def test_view_with_no_schema_methods():
    """Test View methods when no schemas are defined."""

    class SimpleView(View):
        def handle_get(self, request):
            params = self.validated_query_params()
            body = self.validated_body()
            return MockResponse({"params": params, "body": body})

    view_func = SimpleView.as_view()
    request = MockRequest(
        method="GET", query_params={"q": "search"}, body={"data": "test"}
    )

    response = view_func(request)
    assert isinstance(response, MockResponse)
    assert response.data["params"] == {"q": "search"}
    assert response.data["body"] == {"data": "test"}


def test_view_as_view_function_attributes():
    """Test that view function has correct attributes."""

    class TestView(View):
        def handle_get(self, request):
            return MockResponse("get_response")

    view_func = TestView.as_view()

    # Check that the function has the right attributes
    assert hasattr(view_func, "__name__")
    assert hasattr(view_func, "http_methods")
    assert "get" in view_func.http_methods


def test_view_as_view_update_wrapper():
    """Test that update_wrapper is called correctly."""

    class TestView(View):
        def handle_get(self, request):
            """This is a test handler."""
            return MockResponse("get_response")

    view_func = TestView.as_view()

    # Check that the function has http_methods attribute
    assert hasattr(view_func, "http_methods")


# Schema-related tests that require proper setup
def test_view_validate_schema_integration():
    """Test View schema validation integration."""

    class SchemaView(View):
        def handle_get(self, request):
            # Set required attributes for build_ctx
            self.args = ()
            self.kwargs = {}
            return MockResponse("success")

        def handle_post(self, request):
            # Set required attributes for build_ctx
            self.args = ()
            self.kwargs = {}
            return MockResponse("success")

    # Test GET with query params validation - no schema
    view_func = SchemaView.as_view()
    env = {}
    request = MockRequest(method="GET", env=env)

    response = view_func(request)
    assert isinstance(response, MockResponse)
    assert response.data == "success"

    # Test POST with body validation - no schema
    request = MockRequest(method="POST")
    response = view_func(request)
    assert isinstance(response, MockResponse)
    assert response.data == "success"


def test_view_full_integration():
    """Test View full integration flow."""

    class UserView(View):
        def handle_get(self, request):
            return MockResponse({"action": "get"})

        def handle_post(self, request):
            return MockResponse({"action": "post"})

    # Test GET request
    view_func = UserView.as_view()
    env = {}
    request = MockRequest(method="GET", env=env)

    response = view_func(request)
    assert isinstance(response, MockResponse)
    assert response.data["action"] == "get"

    # Test POST request
    request = MockRequest(method="POST")
    response = view_func(request)
    assert isinstance(response, MockResponse)
    assert response.data["action"] == "post"


def test_view_dispatch_sets_attributes():
    """Test that dispatch properly sets required attributes."""

    class TestView(View):
        def handle_get(self, request):
            # These should be set by dispatch
            assert hasattr(self, "args")
            assert hasattr(self, "kwargs")
            assert hasattr(self, "request")
            return MockResponse("success")

    view_func = TestView.as_view()
    env = {}
    request = MockRequest(method="GET", env=env)

    response = view_func(request)
    assert isinstance(response, MockResponse)
    assert response.data == "success"


def test_view_as_view_with_initkwargs():
    """Test View.as_view with initialization kwargs."""

    class TestView(View):
        def __init__(self, custom_param=None):
            super().__init__()
            self.custom_param = custom_param

        def handle_get(self, request):
            return MockResponse(f"response_{getattr(self, 'custom_param', 'none')}")

    view_func = TestView.as_view(custom_param="test_value")

    # Create a mock environment
    env = {}
    request = MockRequest(method="GET", env=env)

    response = view_func(request)

    assert isinstance(response, MockResponse)


def test_view_as_view_with_hasattr_check():
    """Test View.as_view with hasattr check for default actions."""

    class TestView(View):
        def handle_get(self, request):
            return MockResponse("get_response")

        def handle_post(self, request):
            return MockResponse("post_response")

    # This test ensures the hasattr check in as_view works correctly
    view_func = TestView.as_view()

    assert callable(view_func)
    assert hasattr(view_func, "http_methods")
    assert "get" in view_func.http_methods
    assert "post" in view_func.http_methods


def test_view_query_params_schema_none():
    """Test View with query_params_schema set to None."""

    class TestView(View):
        query_params_schema = None

    view = TestView()
    query_params = {"key": "value"}
    view.request = MockRequest(query_params=query_params)

    result = view.validated_query_params()

    assert result == query_params


def test_view_body_schema_none():
    """Test View with body_schema set to None."""

    class TestView(View):
        body_schema = None

    view = TestView()
    body = {"key": "value"}
    view.request = MockRequest(body=body)

    result = view.validated_body()

    assert result == body


def test_view_schema_validation_methods_exist():
    """Test that schema validation methods exist."""
    view = View()
    assert hasattr(view, "_validate_schema")
    assert callable(view._validate_schema)
    assert hasattr(view, "validated_query_params")
    assert callable(view.validated_query_params)
    assert hasattr(view, "validated_body")
    assert callable(view.validated_body)


def test_view_as_view_no_actions_default_behavior():
    """Test View.as_view behavior when no actions are provided."""

    class TestView(View):
        def handle_get(self, request):
            return MockResponse("get_response")

    # Test with no actions parameter (should use defaults)
    view_func = TestView.as_view()

    assert callable(view_func)
    assert hasattr(view_func, "http_methods")
    assert "get" in view_func.http_methods
    assert "head" in view_func.http_methods


def test_view_as_view_empty_actions():
    """Test View.as_view with empty actions dict."""

    class TestView(View):
        pass

    # Test with empty actions dict
    view_func = TestView.as_view(actions={})

    assert callable(view_func)
    assert hasattr(view_func, "http_methods")
    assert len(view_func.http_methods) == 0


def test_view_as_view_with_head_action():
    """Test View.as_view when head action is explicitly provided."""

    class TestView(View):
        def handle_get(self, request):
            return MockResponse("get_response")

        def handle_head(self, request):
            return MockResponse("head_response")

    actions = {"get": "handle_get", "head": "handle_head"}

    view_func = TestView.as_view(actions=actions)

    assert "get" in view_func.http_methods
    assert "head" in view_func.http_methods
    # Should not duplicate head since it's already provided


def test_view_request_setter():
    """Test View.request setter."""
    view = View()
    request = MockRequest()

    # Test setting request
    view.request = request
    assert view.request is request
    assert view.__request__ is request

    # Test getting request
    assert view.request is request


def test_view_request_property_getter():
    """Test View.request property getter."""
    view = View()
    request = MockRequest()

    view.__request__ = request
    assert view.request is request


def test_view_dispatch_handler_not_found():
    """Test View.dispatch when handler is not found."""

    class TestView(View):
        pass

    view = TestView()
    view.action_map = {"get": "nonexistent_handler"}
    request = MockRequest(method="GET")

    with pytest.raises(AttributeError):
        view.dispatch(request)


def test_view_build_ctx_with_empty_args():
    """Test View.build_ctx with empty args and kwargs."""
    view = View()
    view.args = ()
    view.kwargs = {}
    view.request = MockRequest()

    ctx = view.build_ctx()

    assert ctx["args"] == ()
    assert ctx["kwargs"] == {}
    assert ctx["request"] is view.request


def test_view_build_ctx_with_populated_args():
    """Test View.build_ctx with populated args and kwargs."""
    view = View()
    view.args = ("arg1", "arg2")
    view.kwargs = {"kwarg1": "value1", "kwarg2": "value2"}
    view.request = MockRequest()

    ctx = view.build_ctx()

    assert ctx["args"] == ("arg1", "arg2")
    assert ctx["kwargs"] == {"kwarg1": "value1", "kwarg2": "value2"}


def test_view_validate_schema_method_exists():
    """Test that _validate_schema method exists and is callable."""
    view = View()
    assert hasattr(view, "_validate_schema")
    assert callable(view._validate_schema)


def test_view_validated_query_params_method_exists():
    """Test that validated_query_params method exists and is callable."""
    view = View()
    assert hasattr(view, "validated_query_params")
    assert callable(view.validated_query_params)


def test_view_validated_body_method_exists():
    """Test that validated_body method exists and is callable."""
    view = View()
    assert hasattr(view, "validated_body")
    assert callable(view.validated_body)
