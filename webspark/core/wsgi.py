from __future__ import annotations

import traceback
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Callable

    from .plugin import Plugin
    from .router import path

from ..constants import ERROR_CONVENTIONS
from ..http.request import Request
from ..http.response import JsonResponse, Response
from ..utils import HTTPException
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
        self.router = Router()
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
        request = self.creat_request(env)
        try:
            self.check_allowed_hosts(request)
            response = self.dispatch_request(request)
        except Exception as exc:
            if self.debug:
                env["wsgi.errors"].write(traceback.format_exc())
                env["wsgi.errors"].flush()
            exc_handler = self.exceptions.get(
                getattr(exc, "status_code", 500), self.default_exception_handler
            )
            response = exc_handler(request, exc)

        status_str, headers, body_iter = response.as_wsgi()

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

        def wrapper(func: Callable[[Request, Exception], Response]):
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

    def check_allowed_hosts(self, request: Request):
        """Check if the request host is allowed based on configuration.

        Validates the incoming request's host header against the configured
        ALLOWED_HOSTS setting. Supports exact matches and subdomain patterns.

        Args:
            request (Request): The incoming HTTP request object containing
                             the host header to validate.

        Raises:
            HTTPException: If the host header is missing, invalid, or not
                          in the allowed hosts list (status code 400).

        Note:
            - If ALLOWED_HOSTS is None, defaults to ["*"] in debug mode
              or empty list in production mode.
            - "*" allows all hosts.
            - Patterns starting with "." match subdomains (e.g., ".example.com"
              matches "sub.example.com" and "example.com").
        """
        allowed_hosts = getattr(self.config, "ALLOWED_HOSTS", None)

        if allowed_hosts is None:
            allowed_hosts = ["*"] if self.debug else []

        host = request.host.split(":")[0] if request.host else ""

        if not host:
            raise HTTPException("Invalid or missing host header.", status_code=400)

        if "*" in allowed_hosts:
            return

        for pattern in allowed_hosts:
            if pattern.startswith("."):
                if host.endswith(pattern) or host == pattern[1:]:
                    return
            elif host == pattern:
                return

        raise HTTPException(f"Host '{host}' not allowed.", status_code=400)

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

    def dispatch_request(self, request: Request):
        """Dispatch a request to the appropriate route handler.

        This method performs URL routing, creates a Request object, and calls
        the matched route's view handler. It also validates that the handler
        returns a valid Response object.

        Args:
            request: The request object.

        Returns:
            Response: Response object from the view handler.

        Raises:
            HTTPException: If no route matches or handler returns invalid response.
        """
        http_method = request.method
        path_info = request.path

        params, route = self.router.match(http_method, path_info)

        request.path_params = params

        if not route.cached_view and (route.plugins or self.plugins):
            route.cached_view = self.cache_plugins(self.plugins + route.plugins)

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
