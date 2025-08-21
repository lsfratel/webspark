from __future__ import annotations

import re
from collections import abc, defaultdict
from typing import TYPE_CHECKING, Any, Literal

if TYPE_CHECKING:
    from ..http.request import Request
    from ..http.response import Response
    from .plugin import Plugin

from ..utils import HTTPException

Methods = Literal[
    "get",
    "head",
    "post",
    "put",
    "delete",
    "connect",
    "options",
    "trace",
    "patch",
]


class Route:
    """Represents a single route in the WebSpark routing system.

    A Route associates an HTTP method and URL pattern with a view handler.
    It handles pattern matching, parameter extraction, and view instantiation.

    Example:
        # Create a route manually
        route = Route(
            method="get",
            pattern="/users/:id",
            compiled_pattern=re.compile(r"^/users/([^/]+)/?$"),
            keys=["id"],
            view=UserView
        )

        # The route can be called like a function
        response = route(request)

    Attributes:
        method (str): The HTTP method this route responds to.
        pattern (str|Pattern): The original URL pattern.
        compiled_pattern (Pattern): Compiled regex pattern for matching.
        keys (list|False): List of parameter names extracted from pattern.
        view (Callable): The view class or function to handle requests.
        cached_view (Callable): Cached view instance for performance.
    """

    def __init__(
        self,
        method: Methods,
        pattern: str | re.Pattern,
        compiled_pattern: re.Pattern,
        keys: list[str] | Literal[False],
        view: abc.Callable,
        cached_view: abc.Callable = None,
        plugins: list[Plugin] | None = None,
    ):
        """Initialize a Route.

        Args:
            method: HTTP method this route responds to.
            pattern: Original URL pattern string or regex.
            compiled_pattern: Compiled regex pattern for matching.
            keys: List of parameter names from pattern, or False if static.
            view: View class or function to handle requests.
            cached_view: Pre-instantiated view for performance optimization.
        """
        self.method = method
        self.pattern = pattern
        self.compiled_pattern = compiled_pattern
        self.keys = keys
        self.view = view
        self.cached_view = cached_view
        self.plugins = plugins or []

    def __call__(self, *args, **kwds):
        """Call the route's view handler.

        Args:
            *args: Positional arguments to pass to the view.
            **kwds: Keyword arguments to pass to the view.

        Returns:
            Response: HTTP response from the view handler.
        """
        handler = self.cached_view or self.view
        return handler(*args, **kwds)

    def __repr__(self) -> str:
        """String representation of the Route.

        Returns:
            str: Human-readable representation of the route.
        """
        return f"<Route m={self.method} i={self.compiled_pattern} p={self.pattern} k={self.keys}>"


class Router:
    """URL router for the WebSpark framework.

    The Router handles URL pattern matching, route registration, and request
    dispatching to appropriate view handlers. It supports both static and
    dynamic routes with parameter extraction.

    Example:
        router = Router()

        # Add a simple route
        router.add_route("/users", UserListView)

        # Add a dynamic route with parameters
        router.add_route("/users/:id", UserDetailView)

        # Match a request
        params, route = router.match("get", "/users/123")
        # params = {"id": "123"}
        # route = matched Route object

        # Call the matched route
        response = route(request, **params)

    Attributes:
        routes (defaultdict): Dictionary mapping HTTP methods to lists of routes.
        REVERSE_REGEX (Pattern): Regex pattern for URL reversal.
    """

    REVERSE_REGEX = re.compile(r"(/|^)([:*][^/]*?)(\?)?(?=[/.]|$)")

    def __init__(self):
        """Initialize the Router."""
        self.routes: defaultdict[str, list[Route]] = defaultdict(list)

    def add_route(self, path: path):
        """Add a route to the router.

        Args:
            pattern: URL pattern (supports :param and *param syntax).
            view: View class or function to handle requests.
            plugins: List of plugins to apply to this route.
        """
        view = path.view
        pattern = path.pattern
        plugins = path.plugins

        for http_method in view.http_methods:
            keys, compiled_pattern = self.parse(pattern)
            self.routes[http_method].append(
                Route(
                    method=http_method,
                    pattern=pattern,
                    compiled_pattern=compiled_pattern,
                    keys=keys,
                    view=view,
                    cached_view=None,
                    plugins=plugins,
                )
            )

    def parse(
        self,
        input_pattern: str | re.Pattern,
    ) -> tuple[Literal[False] | list, re.Pattern]:
        """Parse a URL pattern into keys and compiled regex.

        Args:
            input_pattern: URL pattern string or pre-compiled regex.

        Returns:
            tuple: (keys_list_or_False, compiled_pattern)
        """
        if isinstance(input_pattern, re.Pattern):
            return False, input_pattern

        keys = []
        pattern_parts = []
        segments = [s for s in input_pattern.split("/") if s]

        for segment in segments:
            if not segment:
                continue
            first_char = segment[0]
            if first_char == "*":
                keys.append("*")
                pattern_parts.append(
                    "(?:/(.*))?" if len(segment) > 1 and segment[1] == "?" else "/(.*)"
                )
            elif first_char == ":":
                q_pos = segment.find("?", 1)
                dot_pos = segment.find(".", 1)
                key_end = min(
                    q_pos if q_pos > 0 else len(segment),
                    dot_pos if dot_pos > 0 else len(segment),
                )
                keys.append(segment[1:key_end])
                base_pattern = "/([^/]+?)"
                if q_pos > 0 and dot_pos < 0:
                    pattern_parts.append(f"(?:{base_pattern})?")
                else:
                    pattern_parts.append(base_pattern)

                if dot_pos > 0:
                    pattern_parts.append(
                        rf"?\{segment[dot_pos:]}"
                        if q_pos > 0
                        else rf"\{segment[dot_pos:]}"
                    )
            else:
                pattern_parts.append(f"/{segment}")

        pattern_str = f"^{''.join(pattern_parts)}/?$"
        return keys, re.compile(pattern_str, re.IGNORECASE)

    def reverse(self, route: str, values: dict[str, Any]) -> str:
        """Generate URL from route pattern and parameter values.

        Args:
            route: Route pattern string.
            values: Dictionary of parameter values.

        Returns:
            str: Generated URL.
        """

        def replacer(match: re.Match[str]):
            lead, key, optional = match.groups()

            if key == "*":
                actual_key = "*"
            else:
                actual_key = key[1:]

            value = values.get(actual_key)

            if value:
                return f"/{value}"
            elif optional or key == "*":
                return ""
            else:
                return f"/{key}"

        return Router.REVERSE_REGEX.sub(replacer, route)

    def match(self, method: Methods, path_info: str) -> tuple[dict[str, Any], Route]:
        """Match a request method and path to a registered route.

        Args:
            method: HTTP method to match.
            path_info: Request path to match against routes.

        Returns:
            tuple: (parameters_dict, matched_route)

        Raises:
            HTTPException: If no matching route is found.
        """
        if method not in self.routes:
            raise HTTPException(
                f"No route found for {method} {path_info}.", status_code=404
            )

        for route in self.routes[method]:
            if not (match_obj := route.compiled_pattern.match(path_info)):
                continue

            if route.keys is False:
                return {"groups": match_obj.groups()}, route

            result = {}
            groups = match_obj.groups()

            for i, key in enumerate(route.keys):
                if i < len(groups) and groups[i] is not None:
                    result[key] = groups[i]

            return result, route

        raise HTTPException(f"No matching route for {path_info}.", status_code=404)


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
    """

    __slots__ = (
        "pattern",
        "view",
        "children",
        "plugins",
    )

    def __init__(
        self,
        pattern: str | re.Pattern,
        *,
        view: abc.Callable[[Request], Response] = None,
        children: list[path] = None,
        plugins: list[Plugin] = None,
    ):
        """Initialize a path object.

        Args:
            pattern: URL pattern for this path.
            view: View class or function to handle requests at this path.
            children: List of nested path objects.
            plugins: List of plugins to apply to this path and sub-paths.
        """
        self.pattern = pattern
        self.view = view
        self.children = children or []
        self.plugins = plugins or []

        self.prefix_subpaths(self.children)

    def prefix_subpaths(self, children: list, prefix: str = None):
        """Prefix sub-paths with this path's pattern.

        Args:
            children: List of sub-path objects to prefix.
            prefix: Prefix to apply (defaults to this path's pattern).
        """
        if isinstance(self.pattern, re.Pattern):
            return

        prefix = prefix or self.pattern

        for p in self.extract_paths(children):
            p.pattern = prefix + p.pattern
            if p.children:
                self.prefix_subpaths(p.children, prefix)

    def extract_paths(self, nested_list):
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
                paths.extend(self.extract_paths(item))
        return paths

    def __repr__(self):
        """String representation of the path.

        Returns:
            str: Human-readable representation of the path.
        """
        if self.view:
            return f"<path pattern={self.pattern} view={self.view}>"
        return f"<path pattern={self.pattern} children={self.children}>"
