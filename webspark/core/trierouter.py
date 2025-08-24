from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Callable
    from typing import Any

    from ..http.context import Context
    from .plugin import Plugin


class _TrieNode:
    """Internal trie node used by TrieRouter.

    Attributes:
        children: Mapping of static path segment to child _TrieNode.
        path: The path class.
        handler: Optional callable stored at terminal nodes.
        param_child: Child node to match a single dynamic segment (':name').
        param_name: The parameter name for the param_child.
        wildcard_child: Child node to match the remainder of the path ('*name').
        wildcard_name: The parameter name for the wildcard_child.
    """

    def __init__(self):
        """Initialize an empty trie node."""
        self.children = {}
        self.path = None
        self.param_child = None
        self.param_name = None
        self.wildcard_child = None
        self.wildcard_name = None


class TrieRouter:
    """A trie-backed router supporting static segments, ':param' segments, and '*wildcard'."""

    def __init__(self):
        """Initialize the router with an empty root node."""
        self.root = _TrieNode()

    def add_route(self, path_: path):
        """Register a handler for the given route pattern.

        Args:
            path: Route pattern. Supports:
                  - static segments: '/users/list'
                  - parameter segments: '/users/:id'
                  - wildcard segments: '/assets/*path' (captures the remainder)
            handler: The callable to associate with this route.

        Raises:
            ValueError: If duplicate parameter names are used within a route or
                        if conflicting parameter/wildcard names occur at the same position.
        """
        node = self.root
        segments = self._split_path(path_.pattern)
        seen_params = set()

        for segment in segments:
            if segment.startswith("*"):
                wc_name = segment[1:] if len(segment) > 1 else "path"
                if wc_name in seen_params:
                    raise ValueError(
                        f"Duplicate parameter name '{wc_name}' within route '{path}'."
                    )

                if node.wildcard_child is None:
                    wc_node = _TrieNode()
                    wc_node.wildcard_name = wc_name
                    node.wildcard_child = wc_node
                else:
                    if node.wildcard_child.wildcard_name != wc_name:
                        raise ValueError(
                            f"Conflicting wildcard names at '{path}': "
                            f"{node.wildcard_child.wildcard_name} vs {wc_name}."
                        )
                node.wildcard_child.path = path_
                return

            if segment.startswith(":"):
                pname = segment[1:]
                if pname in seen_params:
                    raise ValueError(
                        f"Duplicate parameter name '{pname}' within route '{path}'."
                    )
                seen_params.add(pname)

                if node.param_child is None:
                    new_node = _TrieNode()
                    new_node.param_name = pname
                    node.param_child = new_node
                else:
                    if node.param_child.param_name != pname:
                        raise ValueError(
                            f"Conflicting param names at same position for '{path}': "
                            f"{node.param_child.param_name} vs {pname}."
                        )
                node = node.param_child
                continue

            if segment not in node.children:
                node.children[segment] = _TrieNode()
            node = node.children[segment]

        node.path = path_

    def search(self, path_: str) -> tuple[None | path, dict[str, str]]:
        """Find a handler for a concrete request path.

        Args:
            path: A concrete path like '/users/42/profile'.

        Returns:
            A tuple of (handler, params), where handler is the matched callable
            or None if no match exists, and params is a dict of extracted
            parameters for ':param' and '*wildcard' segments.
        """
        node = self.root
        segments = self._split_path(path_)
        params = {}

        i = 0
        while i < len(segments):
            seg = segments[i]

            child = node.children.get(seg)
            if child is not None:
                node = child
                i += 1
                continue

            if node.param_child is not None:
                pname = node.param_child.param_name
                params[pname] = seg
                node = node.param_child
                i += 1
                continue

            if node.wildcard_child is not None:
                remaining = "/".join(segments[i:])
                params[node.wildcard_child.wildcard_name] = remaining
                return node.wildcard_child.path, params

            return None, {}

        if node.path:
            return node.path, params

        if node.wildcard_child is not None:
            params[node.wildcard_child.wildcard_name] = ""
            return node.wildcard_child.path, params

        return None, {}

    def _split_path(self, path: str):
        """Split a path into non-empty segments, ignoring leading/trailing slashes."""
        return [seg for seg in path.split("/") if seg]


class path:
    """Route path class for organizing routes hierarchically.

    The path class allows you to organize routes in a hierarchical structure,
    making it easy to create RESTful APIs with nested resources. It supports
    applying plugins and views to path groups.

    Example:
        # Simple path
        app.add_paths([
            path("/api/users/", view=UserView.as_view())
        ])

        # Nested paths with plugins
        auth_plugin = AuthPlugin()

        app.add_paths([
            path("/api/", plugins=[auth_plugin], children=[
                path("users/", view=UserView.as_view(), children=[
                    path(":id/posts/", view=PostView.as_view())
                ])
            ])
        ])

    Attributes:
        pattern (str|Pattern): URL pattern for this path.
        view (Callable): View class or function to handle requests.
        children (list): List of nested path objects.
        plugins (list): List of plugins applied to this path.
        cached_view: The view with plugins applied, cached for performance.
    """

    __slots__ = (
        "pattern",
        "view",
        "children",
        "plugins",
        "cached_view",
    )

    def __init__(
        self,
        pattern: str,
        *,
        view: Callable[[Context, ...], Any] = None,
        children: list[path] = None,
        plugins: list[Plugin] = None,
    ):
        """Initialize a path object.

        Args:
            pattern: URL pattern for this path.
            view: View class or function to handle requests at this path.
            children: List of nested path objects.
            plugins: List of plugins to apply to this path and children.
        """
        self.pattern = pattern
        self.view = view
        self.cached_view = None
        self.children = children or []
        self.plugins = plugins or []

        self.prefix_children(self.children)

    def prefix_children(self, children: list, prefix: str = None, plugins: list = None):
        """Prefix children with this path's pattern.

        Args:
            children: List of children objects to prefix.
            prefix: Prefix to apply (defaults to this path's pattern).
            plugins: List of plugins to apply to the children paths.
        """
        prefix = prefix or self.pattern
        plugins = plugins or self.plugins

        for p in self.extract_paths(children):
            p.pattern = prefix + p.pattern
            p.plugins = plugins + p.plugins
            if p.children:
                self.prefix_children(p.children, prefix, plugins)

    @classmethod
    def extract_paths(cls, nested_list):
        """Extract path objects from a nested list structure.

        Args:
            nested_list: List that may contain path objects or nested lists.

        Returns:
            list: Flattened list of path objects.
        """
        paths = []
        for item in nested_list:
            if isinstance(item, path):
                paths.append(item)
            elif isinstance(item, list):
                paths.extend(cls.extract_paths(item))
        return paths

    def __repr__(self):
        """String representation of the path.

        Returns:
            str: Human-readable representation of the path.
        """
        if self.view:
            return f"<path pattern={self.pattern} view={self.view}>"
        return f"<path pattern={self.pattern} children={self.children}>"
