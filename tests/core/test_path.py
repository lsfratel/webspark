from unittest.mock import Mock

import pytest

from webspark.core import path


class Request:
    pass


class Response:
    pass


class Plugin:
    pass


class View:
    @staticmethod
    def as_view():
        return lambda req: Response()


@pytest.fixture
def simple_view():
    return View.as_view()


@pytest.fixture
def auth_plugin():
    return Plugin()


def test_path_initialization(simple_view, auth_plugin):
    p = path("/api/", view=simple_view, plugins=[auth_plugin])
    assert p.pattern == "/api/"
    assert p.view is simple_view
    assert p.plugins == [auth_plugin]
    assert p.children == []
    assert p.cached_view is None


def test_path_with_children():
    child = path("users/", view=lambda req: Response())
    parent = path("/api/", children=[child])

    assert len(parent.children) == 1
    assert parent.children[0].pattern == "/api/users/"
    assert parent.children[0].view is not None


def test_nested_paths_prefixing():
    post_path = path(":id/posts/", view=lambda req: Response())
    user_path = path("users/", children=[post_path])
    api_path = path("/api/", children=[user_path])

    assert api_path.children[0].pattern == "/api/users/"
    assert api_path.children[0].children[0].pattern == "/api/users/:id/posts/"


def test_plugin_inheritance():
    auth_plugin = "auth_plugin"
    logging_plugin = "logging_plugin"

    post_view = Mock()
    user_view = Mock()

    post_path = path(":id/posts/", view=post_view)
    user_path = path(
        "users/", view=user_view, plugins=[logging_plugin], children=[post_path]
    )
    api_path = path("/api/", plugins=[auth_plugin], children=[user_path])

    assert api_path.plugins == [auth_plugin]
    assert api_path.children[0].plugins == [auth_plugin, logging_plugin]
    assert api_path.children[0].children[0].plugins == [auth_plugin, logging_plugin]


def test_extract_paths_with_nested_lists():
    p1 = path("a/")
    p2 = path("b/")
    p3 = path("c/")

    nested = [[p1, p2], [p3]]
    extracted = path.extract_paths(nested)

    assert extracted == [p1, p2, p3]


def test_repr_with_view():
    def view_func(req):
        return Response()
    p = path("/test/", view=view_func)
    assert repr(p) == f"<path pattern=/test/ view={view_func}>"


def test_repr_without_view():
    child = path("child/")
    p = path("/parent/", children=[child])
    assert repr(p) == f"<path pattern=/parent/ children=[{child}]>"


def test_prefix_subpaths_explicit_prefix():
    child = path("users/")
    p = path("")
    p.prefix_children([child], prefix="/api/")

    assert child.pattern == "/api/users/"
