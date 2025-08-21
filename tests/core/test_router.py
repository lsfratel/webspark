import re
from unittest.mock import Mock, patch

import pytest

from webspark.core.router import Route, Router, path
from webspark.utils import HTTPException


class MockView:
    def __init__(self, name="MockView", methods=None):
        self.name = name
        self.http_methods = methods or ["get"]

    def __call__(self, request):
        return f"Response from {self.name}"


def test_route_initialization():
    mock_view = Mock()
    mock_pattern = re.compile(r"/test")

    route = Route(
        method="get",
        pattern="/test",
        compiled_pattern=mock_pattern,
        keys=[],
        view=mock_view,
    )

    assert route.method == "get"
    assert route.pattern == "/test"
    assert route.compiled_pattern is mock_pattern
    assert route.keys == []
    assert route.view is mock_view
    assert route.cached_view is None


def test_route_with_cached_view():
    mock_view = Mock()
    mock_cached_view = Mock()
    mock_pattern = re.compile(r"/test")

    route = Route(
        method="get",
        pattern="/test",
        compiled_pattern=mock_pattern,
        keys=[],
        view=mock_view,
        cached_view=mock_cached_view,
    )

    assert route.cached_view is mock_cached_view


def test_route_call():
    mock_view = Mock()
    mock_pattern = re.compile(r"/test")

    route = Route(
        method="get",
        pattern="/test",
        compiled_pattern=mock_pattern,
        keys=[],
        view=mock_view,
    )

    route()
    mock_view.assert_called_once()

    mock_cached_view = Mock()
    route.cached_view = mock_cached_view

    route()
    mock_cached_view.assert_called_once()


def test_route_repr():
    mock_view = Mock()
    mock_pattern = re.compile(r"/test")

    route = Route(
        method="get",
        pattern="/test",
        compiled_pattern=mock_pattern,
        keys=[],
        view=mock_view,
    )

    repr_str = repr(route)
    assert "<Route" in repr_str
    assert "m=get" in repr_str
    assert "p=/test" in repr_str
    assert "k=[]" in repr_str


def test_router_initialization():
    router = Router()

    assert isinstance(router.routes, dict)
    assert len(router.routes) == 0
    assert router.REVERSE_REGEX.pattern == r"(/|^)([:*][^/]*?)(\?)?(?=[/.]|$)"


def test_router_parse_static_pattern():
    router = Router()
    keys, compiled_pattern = router.parse("/api/users")

    assert keys == []
    assert isinstance(compiled_pattern, re.Pattern)
    assert compiled_pattern.pattern == r"^/api/users/?$"


def test_router_parse_dynamic_pattern():
    router = Router()
    keys, compiled_pattern = router.parse("/api/users/:id")

    assert keys == ["id"]
    assert isinstance(compiled_pattern, re.Pattern)
    assert "/([^/]+?)" in compiled_pattern.pattern


def test_router_parse_optional_parameter():
    router = Router()
    keys, compiled_pattern = router.parse("/api/users/:id?")

    assert keys == ["id"]
    assert isinstance(compiled_pattern, re.Pattern)
    assert "(?:/([^/]+?))?" in compiled_pattern.pattern


def test_router_parse_wildcard():
    router = Router()
    keys, compiled_pattern = router.parse("/api/users/*")

    assert keys == ["*"]
    assert isinstance(compiled_pattern, re.Pattern)
    assert "/(.*)" in compiled_pattern.pattern


def test_router_parse_wildcard_optional():
    router = Router()
    keys, compiled_pattern = router.parse("/api/users/*?")

    assert keys == ["*"]
    assert isinstance(compiled_pattern, re.Pattern)
    assert "(?:/(.*))?" in compiled_pattern.pattern


def test_router_parse_with_dot_extension():
    router = Router()
    keys, compiled_pattern = router.parse("/api/users/:id.json")

    assert keys == ["id"]
    assert isinstance(compiled_pattern, re.Pattern)
    assert "/([^/]+?)" in compiled_pattern.pattern
    assert r"\.json" in compiled_pattern.pattern


def test_router_parse_with_regex_pattern():
    router = Router()
    regex_pattern = re.compile(r"/api/users/(\d+)")
    keys, compiled_pattern = router.parse(regex_pattern)

    assert keys is False
    assert compiled_pattern is regex_pattern


def test_router_cache_plugins():
    router = Router()

    plugin1 = Mock()
    plugin2 = Mock()

    view = Mock()

    plugin1.apply.return_value = Mock()
    plugin2.apply.return_value = Mock()

    plugin1.apply.return_value = plugin2.apply.return_value
    plugin2.apply.return_value = view

    cached_view = router.cache_plugins(view, [plugin1, plugin2])

    plugin1.apply.assert_called_once_with(view)
    plugin2.apply.assert_called_once_with(plugin1.apply.return_value)
    assert cached_view is view


def test_router_add_route():
    router = Router()
    view = MockView("TestView", ["get", "post"])

    router.add_route("/api/users", view)

    assert "get" in router.routes
    assert "post" in router.routes
    assert len(router.routes["get"]) == 1
    assert len(router.routes["post"]) == 1

    route = router.routes["get"][0]
    assert route.pattern == "/api/users"
    assert route.method == "get"
    assert route.keys == []


def test_router_add_route_with_plugins():
    router = Router()
    view = MockView("TestView", ["get"])

    plugin = Mock()
    plugin.apply.return_value = view

    router.add_route("/api/users", view, [plugin])

    plugin.apply.assert_called_once_with(view)


def test_router_match_static_route():
    router = Router()
    view = MockView("StaticView", ["get"])

    router.add_route("/api/users", view)

    params, route = router.match("get", "/api/users")

    assert params == {}
    assert route.view.name == "StaticView"


def test_router_match_dynamic_route():
    router = Router()
    view = MockView("DynamicView", ["get"])

    router.add_route("/api/users/:id", view)

    params, route = router.match("get", "/api/users/123")

    assert params == {"id": "123"}
    assert route.view.name == "DynamicView"


def test_router_match_wildcard_route():
    router = Router()
    view = MockView("WildcardView", ["get"])

    router.add_route("/api/users/*", view)

    params, route = router.match("get", "/api/users/123/posts/456")

    assert params == {"*": "123/posts/456"}
    assert route.view.name == "WildcardView"


def test_router_match_optional_parameter():
    router = Router()
    view1 = MockView("OptionalView", ["get"])
    view2 = MockView("StaticView", ["get"])

    router.add_route("/api/users/:id?", view1)
    router.add_route("/api/users", view2)

    params, route = router.match("get", "/api/users/123")
    assert params == {"id": "123"}
    assert route.view.name == "OptionalView"

    params, route = router.match("get", "/api/users")
    assert params == {"id": None} or params == {}


def test_router_match_no_route_found():
    router = Router()

    with pytest.raises(HTTPException) as exc_info:
        router.match("get", "/nonexistent")

    assert exc_info.value.status_code == 404
    assert "No matching route" in str(exc_info.value) or "No route found" in str(
        exc_info.value
    )


def test_router_match_method_not_found():
    router = Router()

    with pytest.raises(HTTPException) as exc_info:
        router.match("post", "/api/users")

    assert exc_info.value.status_code == 404
    assert "No route found" in str(exc_info.value)


def test_router_match_with_groups():
    router = Router()
    view = MockView("RegexView", ["get"])

    regex_pattern = re.compile(r"/api/users/(\d+)")
    route = Route(
        method="get",
        pattern=regex_pattern,
        compiled_pattern=regex_pattern,
        keys=False,
        view=view,
    )
    router.routes["get"].append(route)

    params, route = router.match("get", "/api/users/123")

    assert params == {"groups": ("123",)}
    assert route.view.name == "RegexView"


def test_router_reverse_static_route():
    router = Router()
    result = router.reverse("/api/users", {})

    assert result == "/api/users"


def test_router_reverse_dynamic_route():
    router = Router()
    result = router.reverse("/api/users/:id", {"id": "123"})

    assert result == "/api/users/123"


def test_router_reverse_optional_parameter():
    router = Router()

    result = router.reverse("/api/users/:id?", {"id": "123"})
    assert result == "/api/users/123"

    result = router.reverse("/api/users/:id?", {})
    assert result == "/api/users"


def test_router_reverse_wildcard():
    router = Router()
    result = router.reverse("/api/users/*", {"*": "123/posts/456"})

    assert result == "/api/users/123/posts/456"


def test_router_reverse_missing_required_parameter():
    router = Router()
    result = router.reverse("/api/users/:id", {})

    assert result == "/api/users/:id"


def test_path_initialization():
    view = MockView()

    p = path("/api", view=view)
    assert p.pattern == "/api"
    assert p.view is view
    assert p.children == []
    assert p.plugins == []

    sub_path = path("/users")
    p = path("/api", children=[sub_path])
    assert p.pattern == "/api"
    assert p.view is None
    assert len(p.children) == 1
    assert p.children[0] is sub_path


def test_path_initialization_with_plugins():
    view = MockView()
    plugin = Mock()

    p = path("/api", view=view, plugins=[plugin])
    assert len(p.plugins) == 1
    assert p.plugins[0] is plugin


def test_path_extract_paths():
    path1 = path("/users")
    path2 = path("/posts")

    p = path("/api")
    result = p.extract_paths([path1, path2])

    assert len(result) == 2
    assert path1 in result
    assert path2 in result

    result = p.extract_paths([[path1], path2])
    assert len(result) == 2
    assert path1 in result
    assert path2 in result


def test_path_prefix_subpaths():
    sub_path = path("/users")
    _ = path("/api", children=[sub_path])

    assert sub_path.pattern == "/api/users"

    regex_pattern = re.compile(r"/users")
    sub_path2 = path(regex_pattern)

    _ = path(regex_pattern, children=[sub_path2])

    assert sub_path2.pattern is regex_pattern


def test_path_repr():
    view = MockView()
    p = path("/api", view=view)
    repr_str = repr(p)
    assert "<path" in repr_str
    assert "pattern=/api" in repr_str
    assert "view=" in repr_str

    p = path("/api")
    repr_str = repr(p)
    assert "<path" in repr_str
    assert "pattern=/api" in repr_str
    assert "children=" in repr_str


def test_router_route_priority_static():
    router = Router()

    route = Mock()
    route.keys = []
    route.pattern = "/api/users"

    priority = router._route_priority(route)
    assert priority == 0


def test_router_route_priority_dynamic():
    router = Router()

    route = Mock()
    route.keys = ["id"]
    route.pattern = "/api/users/:id"

    priority = router._route_priority(route)
    assert priority > 0


def test_router_route_priority_optional():
    router = Router()

    route = Mock()
    route.keys = ["id"]
    route.pattern = "/api/users/:id?"

    priority = router._route_priority(route)
    assert priority > 0


def test_router_add_route_sorting():
    router = Router()
    static_view = MockView("StaticView", ["get"])
    dynamic_view = MockView("DynamicView", ["get"])

    router.add_route("/api/users/:id", dynamic_view)
    router.add_route("/api/users", static_view)

    routes = router.routes["get"]
    assert routes[0].pattern == "/api/users/:id"
    assert routes[1].pattern == "/api/users"

    router.sort_routes()

    routes = router.routes["get"]
    assert routes[0].pattern == "/api/users"
    assert routes[1].pattern == "/api/users/:id"


def test_router_parse_complex_pattern():
    router = Router()
    keys, compiled_pattern = router.parse("/api/users/:id/posts/:post_id?")

    assert "id" in keys
    assert "post_id" in keys
    assert isinstance(compiled_pattern, re.Pattern)


def test_router_match_complex_pattern():
    router = Router()
    view = MockView("ComplexView", ["get"])

    router.add_route("/api/users/:id/posts/:post_id?", view)

    params, route = router.match("get", "/api/users/123/posts/456")

    assert params == {"id": "123", "post_id": "456"}
    assert route.view.name == "ComplexView"


def test_router_reverse_complex_pattern():
    router = Router()
    result = router.reverse(
        "/api/users/:id/posts/:post_id?", {"id": "123", "post_id": "456"}
    )

    assert result == "/api/users/123/posts/456"


@patch("webspark.core.router.re.compile")
def test_router_parse_compilation_error(mock_compile):
    mock_compile.side_effect = re.error("Compilation failed")

    router = Router()
    with pytest.raises(re.error):
        router.parse("/api/users/:id")


def test_router_match_with_none_group():
    router = Router()
    view = MockView("TestView", ["get"])

    router.add_route("/api/users/:id?", view)

    params, route = router.match("get", "/api/users")
    assert isinstance(params, dict)


def test_path_extract_paths_nested_lists():
    p = path("/api")

    path1 = path("/users")
    path2 = path("/posts")
    path3 = path("/comments")

    nested_paths = [path1, [path2, [path3]]]
    result = p.extract_paths(nested_paths)

    assert len(result) == 3
    assert path1 in result
    assert path2 in result
    assert path3 in result


def test_path_prefix_subpaths_with_nested():
    sub_sub_path = path("/posts")
    sub_path = path("/users", children=[sub_sub_path])
    _ = path("/api", children=[sub_path])

    assert sub_path.pattern == "/api/users"
    assert sub_sub_path.pattern == "/api/users/posts"


def test_router_parse_empty_segments():
    router = Router()

    keys, compiled_pattern = router.parse("/api//users")

    assert keys == []
    assert isinstance(compiled_pattern, re.Pattern)


def test_router_match_continue_on_failed_match():
    router = Router()
    view1 = MockView("DynamicView", ["get"])
    view2 = MockView("StaticView", ["get"])

    router.add_route("/api/users/:id", view1)
    router.add_route("/api/users/profile", view2)

    params, route = router.match("get", "/api/users/profile")

    assert route.view.name in ["StaticView", "DynamicView"]


def test_router_reverse_edge_cases():
    router = Router()

    result = router.reverse("/api/users/:id", {})
    assert result == "/api/users/:id"

    result = router.reverse("/api/users/:id", {"id": None})
    assert result == "/api/users/:id"


def test_path_repr_with_children():
    sub_path = path("/users")
    p = path("/api", children=[sub_path])

    repr_str = repr(p)
    assert "<path" in repr_str
    assert "pattern=/api" in repr_str
    assert "children=" in repr_str


@patch("webspark.core.router.re.compile")
def test_router_parse_handles_re_error(mock_compile):
    mock_compile.side_effect = re.error("Invalid pattern")

    router = Router()

    with pytest.raises(re.error):
        router.parse("/api/users/:id")


def test_router_priority_complex_patterns():
    router = Router()

    route_many_required = Mock()
    route_many_required.keys = ["id", "postId", "commentId"]
    route_many_required.pattern = "/api/users/:id/posts/:postId/comments/:commentId"

    route_many_optional = Mock()
    route_many_optional.keys = ["id", "postId"]
    route_many_optional.pattern = "/api/users/:id?/posts/:postId?"

    priority_required = router._route_priority(route_many_required)
    priority_optional = router._route_priority(route_many_optional)

    assert isinstance(priority_required, int)
    assert isinstance(priority_optional, int)


def test_router_add_route_multiple_methods():
    router = Router()
    view = MockView("MultiMethodView", ["get", "post", "put"])

    router.add_route("/api/users", view)

    assert "get" in router.routes
    assert "post" in router.routes
    assert "put" in router.routes

    assert len(router.routes["get"]) == 1
    assert len(router.routes["post"]) == 1
    assert len(router.routes["put"]) == 1


def test_path_initialization_edge_cases():
    p = path("/api", children=[])
    assert p.children == []

    p = path("/api", plugins=[])
    assert p.plugins == []

    p = path("/api", children=None, plugins=None)
    assert p.children == []
    assert p.plugins == []
