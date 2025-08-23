from __future__ import annotations

import traceback
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Callable

    from .plugin import Plugin
    from .trierouter import path

from ..http import Context
from ..utils import HTTPException
from .trierouter import TrieRouter


class WebSpark:
    """Main WSGI application class for WebSpark framework.

    WebSpark is a lightweight WSGI framework for building web applications and APIs.
    It provides routing, request/response handling, middleware support, and error
    handling in a simple, intuitive interface.

    Example:
        # Create a simple WebSpark application
        app = WebSpark(debug=True)

        # Define a view
        class HelloWorldView(View):
            def handle_get(self, ctx: Context):
                ctx.json({"message": "Hello, World!"})

        # Add routes
        app.add_paths([
            path("/", view=HelloWorldView.as_view())
        ])

        # Run with a WSGI server
        if __name__ == "__main__":
            from wsgiref.simple_server import make_server
            server = make_server('localhost', 8000, app)
            server.serve_forever()

    Attributes:
        router (Router): URL router for handling request dispatching.
        plugins (list): Global plugins/middleware applied to all routes.
        exceptions (dict): Custom exception handlers mapped by status code.
        debug (bool): Debug mode flag for detailed error reporting.
        config (object): Configuration object for the application.
    """

    def __init__(
        self,
        plugins: list[Plugin] = None,
        config: object = None,
        debug: bool = False,
    ):
        self.router = TrieRouter()
        self.plugins = plugins or []
        self.exceptions = {}
        self.debug = debug
        self.config = config or object()

    def __call__(self, env: dict, start_response: Callable):
        """WSGI application entry point.

        This method implements the WSGI callable interface, handling incoming
        HTTP requests and returning appropriate responses. It performs request
        routing, exception handling, and response conversion to WSGI format.

        Args:
            env: WSGI environment dictionary.
            start_response: WSGI start_response callable.

        Returns:
            Iterable: Response body iterable for WSGI server.
        """
        ctx = self.creat_context(env)
        try:
            self.dispatch_request(ctx)
        except Exception as exc:
            if self.debug:
                env["wsgi.errors"].write(traceback.format_exc())
                env["wsgi.errors"].flush()
            exc_handler = self.exceptions.get(
                getattr(exc, "status_code", 500), self.default_exception_handler
            )
            exc_handler(ctx, exc)

        status_str, headers, body_iter = ctx.as_wsgi()

        start_response(status_str, headers)
        return body_iter

    def add_paths(self, paths: list[path | list]):
        """Add routes to the application from path objects.

        This method registers routes defined using the path class with the
        application's router.

        Args:
            paths: List of path objects or nested lists of path objects.
        """
        for path in paths:
            if isinstance(path, list):
                self.add_paths(path)
            elif path.view is None:
                self.add_paths(path.children)
            else:
                self.router.add_route(path)

    def add_plugins(self, plugin: Plugin):
        """Add a plugin to the global plugin list.

        Args:
            plugin (Plugin): The plugin instance to add to the global plugins.
        """
        self.plugins.append(plugin)

    def handle_exception(self, status: int):
        """Decorator for registering custom exception handlers.

        This decorator registers a custom exception handler for a specific
        HTTP status code. The handler function receives the request and
        exception as arguments and should return a Response object.

        Args:
            status: HTTP status code to handle.

        Example:
            @app.handle_exception(404)
            def not_found_handler(request, exc):
                return HTMLResponse("<h1>Page Not Found</h1>", status=404)

            @app.handle_exception(500)
            def server_error_handler(request, exc):
                if app.debug:
                    return TextResponse(str(exc), status=500)
                return HTMLResponse("<h1>Internal Server Error</h1>", status=500)
        """

        def wrapper(func: Callable[[Context, Exception], None]):
            self.exceptions[status] = func

        return wrapper

    def cache_plugins(self, view: Callable, plugins: list[Plugin]):
        """Apply plugins to a view.

        Args:
            view: View class or function to apply plugins to.
            plugins: List of plugins to apply.

        Returns:
            Callable: View with plugins applied.
        """
        for plugin in plugins:
            view = plugin.apply(view)

        return view

    def default_exception_handler(self, ctx: Context, exc: Exception):
        message = getattr(exc, "details", "Internal error. Please try again.")
        satus = getattr(exc, "status_code", 400)
        ctx.text(
            content=str(message) if not isinstance(message, str) else message,
            status=satus,
        )

    def dispatch_request(self, ctx: Context):
        """Dispatch a request to the appropriate route handler.

        This method performs URL routing and calls the matched
        route's view handler. It also validates that the handler
        returns a valid Response object.

        Args:
            ctx: The context of the request being processed.

        Returns:
            Response: Response object from the view handler.

        Raises:
            HTTPException: If no route matches or handler returns invalid response.
        """
        path_info = ctx.path

        path_, params = self.router.search(path_info)

        if path_ is None:
            raise HTTPException("Route not found.", status_code=404)

        ctx.path_params = params

        if path_.cached_view  is None and (path_.plugins or self.plugins):
            path_.cached_view = self.cache_plugins(path_.view, self.plugins + path_.plugins)

        return (path_.cached_view or path_.view)(ctx)

    def creat_context(self, env: dict):
        """Create a Context object from the WSGI environment.

        Args:
            env: WSGI environment dictionary.

        Returns:
            Context: The created Context object.
        """

        env["webspark.instance"] = self
        return Context(env)
