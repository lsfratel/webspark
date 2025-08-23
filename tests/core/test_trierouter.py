import pytest

from webspark.core import path
from webspark.core.trierouter import TrieRouter


def h(name):
    return lambda: f"handler:{name}"


@pytest.fixture
def router():
    return TrieRouter()


def test_static_route(router):
    router.add_route(path("/about", view=h("about")))
    path_, params = router.search("/about")
    assert path_.view() == "handler:about"
    assert params == {}


def test_root_route(router):
    router.add_route(path("/", view=h("root")))
    path_, params = router.search("/")
    assert path_.view() == "handler:root"
    assert params == {}


def test_param_route(router):
    router.add_route(path("/users/:id", view=h("user")))
    path_, params = router.search("/users/42")
    assert path_.view() == "handler:user"
    assert params == {"id": "42"}


def test_multiple_params(router):
    router.add_route(path("/posts/:year/:slug", view=h("post")))
    path_, params = router.search("/posts/2025/hello-world")
    assert path_.view() == "handler:post"
    assert params == {"year": "2025", "slug": "hello-world"}


def test_wildcard_route(router):
    router.add_route(path("/files/*path", view=h("files")))
    path_, params = router.search("/files/images/2025/logo.png")
    assert path_.view() == "handler:files"
    assert params == {"path": "images/2025/logo.png"}


def test_wildcard_empty_tail(router):
    router.add_route(path("/files/*path", view=h("files")))
    path_, params = router.search("/files")
    assert path_.view() == "handler:files"
    assert params == {"path": ""}


def test_mixed_static_and_param(router):
    router.add_route(path("/users/:id/profile", view=h("profile")))
    path_, params = router.search("/users/123/profile")
    assert path_.view() == "handler:profile"
    assert params == {"id": "123"}


def test_mixed_static_and_wildcard(router):
    router.add_route(path("/assets/*rest", view=h("assets")))
    path_, params = router.search("/assets/css/styles/main.css")
    assert path_.view() == "handler:assets"
    assert params == {"rest": "css/styles/main.css"}


def test_priority_static_over_param(router):
    router.add_route(path("/users/profile", view=h("static-profile")))
    router.add_route(path("/users/:id", view=h("param-user")))
    path_, params = router.search("/users/profile")
    assert path_.view() == "handler:static-profile"
    assert params == {}


def test_priority_param_over_wildcard(router):
    router.add_route(path("/users/:id", view=h("param-user")))
    router.add_route(path("/users/*rest", view=h("wildcard")))
    path_, params = router.search("/users/123")
    assert path_.view() == "handler:param-user"
    assert params == {"id": "123"}


def test_priority_wildcard_when_no_other_match(router):
    router.add_route(path("/users/*rest", view=h("wildcard")))
    path_, params = router.search("/users/123/settings")
    assert path_.view() == "handler:wildcard"
    assert params == {"rest": "123/settings"}


def test_duplicate_param_same_route(router):
    with pytest.raises(ValueError, match="Duplicate parameter name 'id'"):
        router.add_route(path("/users/:id/profile/:id", view=h("dup")))


def test_param_and_wildcard_same_name(router):
    with pytest.raises(ValueError, match="Duplicate parameter name 'path'"):
        router.add_route(path("/files/:path/*path", view=h("bad")))


def test_conflicting_param_names_same_position(router):
    router.add_route(path("/users/:id", view=h("user")))
    with pytest.raises(ValueError, match="Conflicting param names"):
        router.add_route(path("/users/:user_id", view=h("user2")))


def test_conflicting_wildcard_names(router):
    router.add_route(path("/media/*path", view=h("media")))
    with pytest.raises(ValueError, match="Conflicting wildcard names"):
        router.add_route(path("/media/*rest", view=h("media2")))
