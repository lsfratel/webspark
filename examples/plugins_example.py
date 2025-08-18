"""
Plugins and Exception Handling Example
This example demonstrates:
- Creating and using plugins (middleware)
- Custom exception handlers
- Advanced routing with nested paths
"""

import time

from webspark.core import Plugin, View, WebSpark, path
from webspark.http import JsonResponse, TextResponse
from webspark.utils import HTTPException


# Simple logging plugin
class LoggingPlugin(Plugin):
    def apply(self, handler):
        def wrapped_handler(request):
            start_time = time.time()
            print(f"[LOG] {request.method} {request.path} - Start")
            try:
                response = handler(request)
                duration = time.time() - start_time
                print(
                    f"[LOG] {request.method} {request.path} - Completed in {duration:.4f}s with status {response.status}"
                )
                return response
            except Exception as e:
                duration = time.time() - start_time
                print(
                    f"[LOG] {request.method} {request.path} - Failed in {duration:.4f}s with error: {e}"
                )
                raise

        return wrapped_handler


# Authentication plugin (simulated)
class AuthPlugin(Plugin):
    def apply(self, handler):
        def wrapped_handler(request):
            # In a real app, you would check a token or session
            auth_header = request.headers.get("Authorization")
            if not auth_header or not auth_header.startswith("Bearer "):
                raise HTTPException("Unauthorized", status_code=401)

            # Extract token (in a real app, you would validate it)
            token = auth_header[7:]  # Remove "Bearer "
            if token != "secret-token":
                raise HTTPException("Invalid token", status_code=401)

            # Add user info to request for use in views
            request.user = {"id": 1, "username": "admin"}
            return handler(request)

        return wrapped_handler


# Views
class PublicView(View):
    def handle_get(self, request):
        return JsonResponse(
            {"message": "This is a public endpoint", "timestamp": time.time()}
        )


class ProtectedView(View):
    def handle_get(self, request):
        return JsonResponse(
            {
                "message": "This is a protected endpoint",
                "user": getattr(request, "user", None),
                "timestamp": time.time(),
            }
        )


class ErrorView(View):
    def handle_get(self, request):
        # Simulate an error
        raise HTTPException("Something went wrong", status_code=500)


# Create the app with global plugins
app = WebSpark(debug=True, global_plugins=[LoggingPlugin()])


# Add custom exception handler
@app.handle_exception(500)
def handle_server_error(request, exc):
    """Custom handler for 500 Internal Server Error."""
    if app.debug:
        return TextResponse(f"Server Error: {str(exc)}", status=500)
    return JsonResponse({"error": "Internal server error"}, status=500)


@app.handle_exception(401)
def handle_unauthorized(request, exc):
    """Custom handler for 401 Unauthorized."""
    return JsonResponse({"error": "Unauthorized access"}, status=401)


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
