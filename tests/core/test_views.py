import pytest

from webspark.core.views import DEFAULT_ACTIONS, View


class MockContext:
    def __init__(self, method="GET", query_params=None, body=None, env=None):
        self.method = method
        self.query_params = query_params or {}
        self.body = body or {}
        self.environ = env or {}
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

    def is_valid(self):
        return self._is_valid

    @property
    def validated_data(self):
        return self._validated_data

    @property
    def errors(self):
        return self._errors


def test_view_default_actions():
    assert "get" in DEFAULT_ACTIONS
    assert DEFAULT_ACTIONS["get"] == "handle_get"
    assert "post" in DEFAULT_ACTIONS
    assert DEFAULT_ACTIONS["post"] == "handle_post"
    assert len(DEFAULT_ACTIONS) == 9


def test_view_ctx_property():
    view = View()
    ctx = MockContext()

    view.ctx = ctx
    assert view.ctx is ctx
    assert view.__ctx__ is ctx


def test_view_as_view_default_actions():
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
    assert "head" in view_func.http_methods


def test_view_as_view_custom_actions():
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
    assert "head" in view_func.http_methods


def test_view_as_view_no_actions():
    class TestView(View):
        pass

    view_func = TestView.as_view()

    assert callable(view_func)
    assert hasattr(view_func, "http_methods")
    assert len(view_func.http_methods) == 0


def test_view_as_view_head_automatically_added():
    class TestView(View):
        def handle_get(self, request):
            return MockResponse("get_response")

    actions = {"get": "handle_get"}
    view_func = TestView.as_view(actions=actions)

    assert "head" in view_func.http_methods


def test_view_dispatch():
    class TestView(View):
        def handle_get(self, ctx, *args, **kwargs):
            return MockResponse(f"get_response_{args}_{kwargs}")

    view = TestView()
    view.action_map = {"get": "handle_get"}
    ctx = MockContext(method="get")

    response = view.dispatch(ctx, "arg1", "arg2", kwarg1="value1")

    assert isinstance(response, MockResponse)
    assert hasattr(view, "args")
    assert hasattr(view, "kwargs")
    assert hasattr(view, "ctx")
    assert view.ctx is ctx


def test_view_dispatch_with_custom_action():
    class TestView(View):
        def custom_handler(self, request):
            return MockResponse("custom_response")

    view = TestView()
    view.action_map = {"post": "custom_handler"}
    request = MockContext(method="post")

    response = view.dispatch(request)

    assert isinstance(response, MockResponse)
    assert response.data == "custom_response"


def test_view_build_ctx():
    view = View()
    view.args = ("arg1", "arg2")
    view.kwargs = {"kwarg1": "value1"}
    view.ctx = MockContext()

    ctx = view.build_ctx()

    assert isinstance(ctx, dict)
    assert ctx["view"] is view
    assert ctx["args"] == ("arg1", "arg2")
    assert ctx["kwargs"] == {"kwarg1": "value1"}
    assert ctx["ctx"] is view.ctx


def test_view_validated_query_params_no_schema():
    view = View()
    query_params = {"key": "value"}
    view.ctx = MockContext(query_params=query_params)

    result = view.validated_query_params()

    assert result == query_params


def test_view_validated_body_no_schema():
    view = View()
    body = {"key": "value"}
    view.ctx = MockContext(body=body)

    result = view.validated_body()

    assert result == body


def test_view_with_no_schema_methods():
    class SimpleView(View):
        def handle_get(self, request):
            params = self.validated_query_params()
            body = self.validated_body()
            return MockResponse({"params": params, "body": body})

    view_func = SimpleView.as_view()
    request = MockContext(
        method="get", query_params={"q": "search"}, body={"data": "test"}
    )

    response = view_func(request)
    assert isinstance(response, MockResponse)
    assert response.data["params"] == {"q": "search"}
    assert response.data["body"] == {"data": "test"}


def test_view_as_view_function_attributes():
    class TestView(View):
        def handle_get(self, request):
            return MockResponse("get_response")

    view_func = TestView.as_view()

    assert hasattr(view_func, "__name__")
    assert hasattr(view_func, "http_methods")
    assert "get" in view_func.http_methods


def test_view_as_view_update_wrapper():
    class TestView(View):
        def handle_get(self, request):
            return MockResponse("get_response")

    view_func = TestView.as_view()

    assert hasattr(view_func, "http_methods")


def test_view_validate_schema_integration():
    class SchemaView(View):
        def handle_get(self, request):
            self.args = ()
            self.kwargs = {}
            return MockResponse("success")

        def handle_post(self, request):
            self.args = ()
            self.kwargs = {}
            return MockResponse("success")

    view_func = SchemaView.as_view()
    env = {}
    request = MockContext(method="get", env=env)

    response = view_func(request)
    assert isinstance(response, MockResponse)
    assert response.data == "success"

    request = MockContext(method="post")
    response = view_func(request)
    assert isinstance(response, MockResponse)
    assert response.data == "success"


def test_view_full_integration():
    class UserView(View):
        def handle_get(self, request):
            return MockResponse({"action": "get"})

        def handle_post(self, request):
            return MockResponse({"action": "post"})

    view_func = UserView.as_view()
    env = {}
    request = MockContext(method="get", env=env)

    response = view_func(request)
    assert isinstance(response, MockResponse)
    assert response.data["action"] == "get"

    request = MockContext(method="post")
    response = view_func(request)
    assert isinstance(response, MockResponse)
    assert response.data["action"] == "post"


def test_view_dispatch_sets_attributes():
    class TestView(View):
        def handle_get(self, ctx):
            assert hasattr(self, "args")
            assert hasattr(self, "kwargs")
            assert hasattr(self, "ctx")
            return MockResponse("success")

    view_func = TestView.as_view()
    env = {}
    request = MockContext(method="get", env=env)

    response = view_func(request)
    assert isinstance(response, MockResponse)
    assert response.data == "success"


def test_view_as_view_with_initkwargs():
    class TestView(View):
        def __init__(self, custom_param=None):
            super().__init__()
            self.custom_param = custom_param

        def handle_get(self, request):
            return MockResponse(f"response_{getattr(self, 'custom_param', 'none')}")

    view_func = TestView.as_view(custom_param="test_value")

    env = {}
    request = MockContext(method="get", env=env)

    response = view_func(request)

    assert isinstance(response, MockResponse)


def test_view_as_view_with_hasattr_check():
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


def test_view_query_params_schema_none():
    class TestView(View):
        query_params_schema = None

    view = TestView()
    query_params = {"key": "value"}
    view.ctx = MockContext(query_params=query_params)

    result = view.validated_query_params()

    assert result == query_params


def test_view_body_schema_none():
    class TestView(View):
        body_schema = None

    view = TestView()
    body = {"key": "value"}
    view.ctx = MockContext(body=body)

    result = view.validated_body()

    assert result == body


def test_view_schema_validation_methods_exist():
    view = View()
    assert hasattr(view, "_validate_schema")
    assert callable(view._validate_schema)
    assert hasattr(view, "validated_query_params")
    assert callable(view.validated_query_params)
    assert hasattr(view, "validated_body")
    assert callable(view.validated_body)


def test_view_as_view_no_actions_default_behavior():
    class TestView(View):
        def handle_get(self, request):
            return MockResponse("get_response")

    view_func = TestView.as_view()

    assert callable(view_func)
    assert hasattr(view_func, "http_methods")
    assert "get" in view_func.http_methods
    assert "head" in view_func.http_methods


def test_view_as_view_empty_actions():
    class TestView(View):
        pass

    view_func = TestView.as_view(actions={})

    assert callable(view_func)
    assert hasattr(view_func, "http_methods")
    assert len(view_func.http_methods) == 0


def test_view_as_view_with_head_action():
    class TestView(View):
        def handle_get(self, request):
            return MockResponse("get_response")

        def handle_head(self, request):
            return MockResponse("head_response")

    actions = {"get": "handle_get", "head": "handle_head"}

    view_func = TestView.as_view(actions=actions)

    assert "get" in view_func.http_methods
    assert "head" in view_func.http_methods


def test_view_request_setter():
    view = View()
    ctx = MockContext()

    view.ctx = ctx
    assert view.ctx is ctx
    assert view.__ctx__ is ctx

    assert view.ctx is ctx


def test_view_request_property_getter():
    view = View()
    ctx = MockContext()

    view.__ctx__ = ctx
    assert view.ctx is ctx


def test_view_dispatch_handler_not_found():
    class TestView(View):
        pass

    view = TestView()
    view.action_map = {"get": "nonexistent_handler"}
    request = MockContext(method="get")

    with pytest.raises(AttributeError):
        view.dispatch(request)


def test_view_build_ctx_with_empty_args():
    view = View()
    view.args = ()
    view.kwargs = {}
    view.ctx = MockContext()

    ctx = view.build_ctx()

    assert ctx["args"] == ()
    assert ctx["kwargs"] == {}
    assert ctx["ctx"] is view.ctx


def test_view_build_ctx_with_populated_args():
    view = View()
    view.args = ("arg1", "arg2")
    view.kwargs = {"kwarg1": "value1", "kwarg2": "value2"}
    view.ctx = MockContext()

    ctx = view.build_ctx()

    assert ctx["args"] == ("arg1", "arg2")
    assert ctx["kwargs"] == {"kwarg1": "value1", "kwarg2": "value2"}


def test_view_validate_schema_method_exists():
    view = View()
    assert hasattr(view, "_validate_schema")
    assert callable(view._validate_schema)


def test_view_validated_query_params_method_exists():
    view = View()
    assert hasattr(view, "validated_query_params")
    assert callable(view.validated_query_params)


def test_view_validated_body_method_exists():
    view = View()
    assert hasattr(view, "validated_body")
    assert callable(view.validated_body)
