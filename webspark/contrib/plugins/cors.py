from __future__ import annotations

import re
from collections.abc import Callable
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from ...http import Context

from ...core.plugin import Plugin
from ...utils import HTTPException


class CORSPlugin(Plugin):
    """A CORS (Cross-Origin Resource Sharing) plugin for WebSpark.

    This plugin implements the full CORS specification, allowing fine-grained control
    over cross-origin requests. It supports both simple and preflighted requests,
    with configurable origins, methods, headers, and credentials.

    Example:
        # Allow all origins (not recommended for production)
        cors_plugin = CORSPlugin(allow_origins=["*"])

        # More secure configuration
        cors_plugin = CORSPlugin(
            allow_origins=["https://mydomain.com", "https://api.mydomain.com"],
            allow_methods=["GET", "POST", "PUT", "DELETE"],
            allow_headers=["Content-Type", "Authorization"],
            allow_credentials=True,
            max_age=86400  # 24 hours
        )

        # Add to application
        app = WebSpark(plugins=[cors_plugin])

        # Or add to specific routes
        app.add_paths([
            path("/api/", view=APIView.as_view(), plugins=[cors_plugin])
        ])

    Attributes:
        allow_origins (list): List of allowed origins. Use ["*"] to allow all.
        allow_methods (list): List of allowed HTTP methods.
        allow_headers (list): List of allowed headers.
        allow_credentials (bool): Whether to allow credentials.
        max_age (int): How long the preflight response should be cached (in seconds).
        expose_headers (list): List of headers that browsers are allowed to access.
        vary_header (bool): Whether to add Vary header for preflight requests.
    """

    def __init__(
        self,
        allow_origins: list[str] | None = None,
        allow_methods: list[str] | None = None,
        allow_headers: list[str] | None = None,
        allow_credentials: bool = False,
        max_age: int = 600,
        expose_headers: list[str] | None = None,
        vary_header: bool = True,
    ):
        """Initialize the CORS plugin.

        Args:
            allow_origins: List of allowed origins. Defaults to ["*"].
            allow_methods: List of allowed HTTP methods. Defaults to all standard methods.
            allow_headers: List of allowed headers. Defaults to common headers.
            allow_credentials: Whether to allow credentials. Defaults to False.
            max_age: How long the preflight response should be cached (in seconds).
            expose_headers: List of headers that browsers are allowed to access.
            vary_header: Whether to add Vary header for preflight requests. Defaults to True.
        """
        self.allow_origins = allow_origins or ["*"]
        self.allow_methods = allow_methods or [
            "GET",
            "POST",
            "PUT",
            "DELETE",
            "OPTIONS",
            "PATCH",
            "HEAD",
        ]
        self.allow_headers = [
            header.lower()
            for header in (
                allow_headers
                or [
                    "Accept",
                    "Accept-Language",
                    "Content-Language",
                    "Content-Type",
                ]
            )
        ]
        self.allow_credentials = allow_credentials
        self.max_age = max_age
        self.expose_headers = expose_headers or []
        self.vary_header = vary_header

        self._compiled_origins = []
        for origin in self.allow_origins:
            if origin == "*":
                self._compiled_origins.append(origin)
            elif "*" in origin:
                regex_pattern = re.escape(origin).replace("\\*", ".*")
                self._compiled_origins.append(re.compile(f"^{regex_pattern}$"))
            else:
                self._compiled_origins.append(origin)

    def _is_origin_allowed(self, origin: str) -> bool:
        """Check if the given origin is allowed.

        Args:
            origin: The origin to check.

        Returns:
            bool: True if the origin is allowed, False otherwise.
        """
        if "*" in self.allow_origins:
            return True

        for pattern in self._compiled_origins:
            if isinstance(pattern, str):
                if pattern == "*" or origin == pattern:
                    return True
            elif pattern.match(origin):
                return True

        return False

    def _get_allow_origin_value(self, origin: str) -> str:
        """Get the value for the Access-Control-Allow-Origin header.

        Args:
            origin: The origin from the request.

        Returns:
            str: The value for the Access-Control-Allow-Origin header.
        """
        if "*" in self.allow_origins and not self.allow_credentials:
            return "*"
        return origin

    def _is_preflight_request(self, ctx: Context) -> bool:
        """Check if the request is a CORS preflight request.

        Args:
            ctx: The request context.

        Returns:
            bool: True if the request is a preflight request, False otherwise.
        """
        return (
            ctx.method == "options" and "access-control-request-method" in ctx.headers
        )

    def _handle_preflight(self, ctx: Context, origin: str):
        """Handle a CORS preflight request.

        Args:
            ctx: The request context.
            origin: The origin of the request.
        """
        requested_method = ctx.headers.get("access-control-request-method")
        if requested_method and requested_method not in self.allow_methods:
            raise HTTPException("Method not allowed.", status_code=405)

        requested_headers = ctx.headers.get("access-control-request-headers")
        if requested_headers:
            headers = [
                header.strip().lower() for header in requested_headers.split(",")
            ]
            disallowed_headers = [
                header for header in headers if header not in self.allow_headers
            ]
            if disallowed_headers:
                raise HTTPException(
                    f"Headers not allowed: {', '.join(disallowed_headers)}",
                    status_code=400,
                )

        ctx.set_header(
            "access-control-allow-origin",
            self._get_allow_origin_value(origin),
        )

        if self.allow_credentials:
            ctx.set_header("access-control-allow-credentials", "true")

        if self.max_age:
            ctx.set_header("access-control-max-age", str(self.max_age))

        if self.allow_methods:
            ctx.set_header(
                "access-control-allow-methods", ", ".join(self.allow_methods)
            )

        if self.allow_headers:
            ctx.set_header(
                "access-control-allow-headers", ", ".join(self.allow_headers)
            )

        if self.vary_header:
            ctx.set_header("vary", "origin")

        ctx.text(b"", status=204)

    def _add_cors_headers(self, ctx: Context, origin: str):
        """Add CORS headers to a response.

        Args:
            ctx: The request context.
            origin: The origin of the request.
        """
        ctx.set_header(
            "access-control-allow-origin",
            self._get_allow_origin_value(origin),
        )

        if self.allow_credentials:
            ctx.set_header("access-control-allow-credentials", "true")

        if self.expose_headers:
            ctx.set_header(
                "access-control-expose-headers", ", ".join(self.expose_headers)
            )

        if self.vary_header:
            vary = ctx.get_header("vary")
            if vary:
                if "origin" not in vary.lower():
                    vary += ", origin"
            else:
                vary = "origin"
            ctx.set_header("vary", vary)

    def apply(self, handler: Callable[[Context], None]) -> Callable[[Context], None]:
        """Apply CORS to a request handler.

        Args:
            handler: The original request handler function.

        Returns:
            Callable: A wrapped handler function with CORS behavior applied.
        """

        def wrapped_handler(ctx: Context):
            origin = ctx.headers.get("origin")
            if not origin:
                return handler(ctx)

            if not self._is_origin_allowed(origin):
                raise HTTPException("Origin not allowed.", status_code=403)

            if self._is_preflight_request(ctx):
                return self._handle_preflight(ctx, origin)

            try:
                handler(ctx)
            except Exception:
                self._add_cors_headers(ctx, origin)
                raise

            self._add_cors_headers(ctx, origin)

        return wrapped_handler
