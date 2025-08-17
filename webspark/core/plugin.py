from __future__ import annotations

from collections import abc
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from ..http import Request, Response


class Plugin:
    """Base class for WebSpark plugins/middleware.

    Plugins provide a way to modify request handling behavior globally or per-route.
    They can be used for authentication, logging, request preprocessing, response
    postprocessing, and other cross-cutting concerns.

    Example:
        class LoggingPlugin(Plugin):
            def apply(self, handler):
                def wrapped_handler(request):
                    print(f"Handling request: {request.path}")
                    response = handler(request)
                    print(f"Response status: {response.status}")
                    return response
                return wrapped_handler

        # Apply globally
        app = WebSpark(global_plugins=[LoggingPlugin()])

        # Apply to specific routes
        app.add_paths([
            path("/api/", view=APIView.as_view(), plugins=[LoggingPlugin()])
        ])

    Attributes:
        None
    """

    def apply(
        self,
        handler: abc.Callable[[Request], Response],
    ):
        """Apply the plugin to a request handler.

        This method should return a new handler function that wraps the original
        handler with the plugin's behavior.

        Args:
            handler: The original request handler function.

        Returns:
            Callable: A wrapped handler function with plugin behavior applied.
        """
        return handler
