from __future__ import annotations

import traceback
from collections.abc import Callable
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .plugin import Plugin
    from .router import path

from ..constants import ERROR_CONVENTIONS
from ..http.request import Request
from ..http.response import JsonResponse, Response
from .router import Router


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
            def handle_get(self, request):
                return JsonResponse({"message": "Hello, World!"})

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
        _router (Router): URL router for handling request dispatching.
        _plugins (list): Global plugins/middleware applied to all routes.
        _exceptions (dict): Custom exception handlers mapped by status code.
        debug (bool): Debug mode flag for detailed error reporting.
        config (object): Configuration object for the application.
    """

    def __init__(
        self,
        global_plugins: list[Plugin] = None,
        config: object = None,
        debug: bool = False,
    ):
        """Initialize the WebSpark application.

        Args:
            global_plugins: List of plugins to apply globally to all routes.
            debug: Enable debug mode for detailed error reporting.
        """
        self._router = Router()
        self._plugins = global_plugins or []
        self._exceptions = {}
        self.debug = debug
        self.config = config or object()

    def add_paths(self, paths: list[path | list]):
        """Add routes to the application from path objects.

        This method registers routes defined using the path class with the
        application's router. It handles nested path structures and applies
        both global and route-specific plugins.

        Args:
            paths: List of path objects or nested lists of path objects.
        """
        for path in paths:
            if isinstance(path, list):
                self.add_paths(path)
            elif path.view is None:
                self.add_paths(path.children)
            else:
                self._router.add_route(
                    path.pattern, path.view, self._plugins + path.plugins
                )

        self._router.sort_routes()

    def add_plugins(self, plugin: Plugin):
        """Add a plugin to the global plugin list.

        Args:
            plugin (Plugin): The plugin instance to add to the global plugins.
        """
        self._plugins.append(plugin)

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

        def wrapper(func: Callable[[Request, Exception], Response]):
            self._exceptions[status] = func

        return wrapper

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
        try:
            response = self.dispatch_request(env)
        except Exception as exc:
            if self.debug:
                env["wsgi.errors"].write(traceback.format_exc())
                env["wsgi.errors"].flush()
            exc_handler = self._exceptions.get(
                getattr(exc, "status_code", 500), self.default_exception_handler
            )
            response = exc_handler(self.creat_request(env), exc)

        status_str, headers, body_iter = response.as_wsgi()

        start_response(status_str, headers)
        return body_iter

    def default_exception_handler(self, _: Request, exc: Exception):
        """Default exception handler for unhandled exceptions.

        This method generates a standardized JSON error response for any
        unhandled exceptions that occur during request processing. It uses
        the framework's error conventions to provide consistent error messages.

        Args:
            _: Request object (unused).
            exc: Exception that occurred.

        Returns:
            JsonResponse: Standardized error response.
        """
        status_code = getattr(exc, "status_code", 500)
        details = getattr(exc, "details", None)

        base = ERROR_CONVENTIONS.get(
            status_code,
            {"code": "UNKNOWN_ERROR", "message": "An unknown error occurred."},
        )

        error = {"code": base["code"], "message": base["message"]}

        if details:
            if isinstance(details, dict):
                error["details"] = details
            else:
                error["message"] = details

        return JsonResponse(
            {
                "success": False,
                "error": error,
            },
            status=status_code,
        )

    def dispatch_request(self, env: dict):
        """Dispatch a request to the appropriate route handler.

        This method performs URL routing, creates a Request object, and calls
        the matched route's view handler. It also validates that the handler
        returns a valid Response object.

        Args:
            env: WSGI environment dictionary.

        Returns:
            Response: Response object from the view handler.

        Raises:
            HTTPException: If no route matches or handler returns invalid response.
        """
        http_method = env.get("REQUEST_METHOD", "GET").lower()
        path_info = env.get("PATH_INFO", "/")

        params, route = self._router.match(http_method, path_info)

        request = self.creat_request(env)
        request.path_params = params

        resp = route(request)

        if not isinstance(resp, Response):
            raise ValueError("Route handler did not return a valid Response object.")

        return resp

    def creat_request(self, env: dict):
        """Create a Request object from the WSGI environment.

        Args:
            env: WSGI environment dictionary.

        Returns:
            Request: The created Request object.
        """

        env["webspark.instance"] = self
        return Request(env)
