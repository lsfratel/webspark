"""
Plugins and Exception Handling Example
This example demonstrates:
- Creating and using plugins (middleware)
- Custom exception handlers
- Advanced routing with nested paths
"""

import time

from webspark.core import Plugin, View, WebSpark, path
from webspark.http import Context
from webspark.utils import HTTPException


# Simple logging plugin
class LoggingPlugin(Plugin):
    def apply(self, handler):
        def wrapped_handler(ctx: Context):
            start_time = time.time()
            print(f"[LOG] {ctx.method} {ctx.path} - Start")
            try:
                handler(ctx)
                duration = time.time() - start_time
                print(
                    f"[LOG] {ctx.method} {ctx.path} - Completed in {duration:.4f}s with status {ctx.status}"
                )
            except Exception as e:
                duration = time.time() - start_time
                print(
                    f"[LOG] {ctx.method} {ctx.path} - Failed in {duration:.4f}s with error: {e}"
                )
                raise

        return wrapped_handler


# Authentication plugin (simulated)
class AuthPlugin(Plugin):
    def apply(self, handler):
        def wrapped_handler(ctx: Context):
            # In a real app, you would check a token or session
            auth_header = ctx.headers.get("Authorization")
            if not auth_header or not auth_header.startswith("Bearer "):
                raise HTTPException("Unauthorized", status_code=401)

            # Extract token (in a real app, you would validate it)
            token = auth_header[7:]  # Remove "Bearer "
            if token != "secret-token":
                raise HTTPException("Invalid token", status_code=401)

            # Add user info to request for use in views
            ctx.state["user"] = {"id": 1, "username": "admin"}
            handler(ctx)

        return wrapped_handler


# Views
class PublicView(View):
    def handle_get(self, ctx: Context):
        ctx.json({"message": "This is a public endpoint", "timestamp": time.time()})


class ProtectedView(View):
    def handle_get(self, ctx: Context):
        ctx.json(
            {
                "message": "This is a protected endpoint",
                "user": ctx.state.get("user"),
                "timestamp": time.time(),
            }
        )


class ErrorView(View):
    def handle_get(self, request):
        # Simulate an error
        raise HTTPException("Something went wrong", status_code=500)


# Create the app with global plugins
app = WebSpark(debug=True, plugins=[LoggingPlugin()])


# Add custom exception handler
@app.handle_exception(500)
def handle_server_error(ctx: Context, exc):
    """Custom handler for 500 Internal Server Error."""
    if app.debug:
        ctx.text(f"Server Error: {str(exc)}", status=500)
    else:
        ctx.json({"error": "Internal server error"}, status=500)


@app.handle_exception(401)
def handle_unauthorized(ctx: Context, exc):
    """Custom handler for 401 Unauthorized."""
    ctx.json({"error": "Unauthorized access"}, status=401)


# Add routes with nested paths and specific plugins
app.add_paths(
    [
        path("/", view=PublicView.as_view()),
        path(
            "/api",
            children=[
                path("/public", view=PublicView.as_view()),
                path(
                    "/protected", view=ProtectedView.as_view(), plugins=[AuthPlugin()]
                ),
                path("/error", view=ErrorView.as_view()),
            ],
        ),
    ]
)

if __name__ == "__main__":
    # For development purposes, you can run this with a WSGI server like:
    # gunicorn examples.plugins_example:app
    print("Plugins and Exception Handling Example")
    print("Run with: gunicorn examples.plugins_example:app")
