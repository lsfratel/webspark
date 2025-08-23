"""
Example demonstrating how to use the CORS plugin with WebSpark.
"""

from webspark.contrib.plugins import CORSPlugin
from webspark.core import View, WebSpark, path
from webspark.http import Context


class APIView(View):
    """A simple API view for demonstration purposes."""

    def handle_get(self, ctx: Context):
        ctx.json({"message": "Hello from the API!"})

    def handle_post(self, ctx: Context):
        # Echo back the request data
        ctx.json({"received": ctx.body}, status=201)


# Create the CORS plugin with a specific configuration
cors_plugin = CORSPlugin(
    allow_origins=["https://mydomain.com", "https://api.mydomain.com"],
    allow_methods=["GET", "POST", "PUT", "DELETE"],
    allow_headers=["Content-Type", "Authorization", "X-Requested-With"],
    allow_credentials=True,
    max_age=86400,  # 24 hours
    expose_headers=["X-Custom-Header"],
)

# Create the WebSpark application with the CORS plugin
app = WebSpark(debug=True, plugins=[cors_plugin])

# Add routes
app.add_paths([path("/api/", view=APIView.as_view())])

# To run this example:
# 1. Save this file as 'cors_example.py'
# 2. Run with a WSGI server like Gunicorn:
#    gunicorn cors_example:app

if __name__ == "__main__":
    # For development purposes, you can run this with a WSGI server like:
    # gunicorn examples.cors_example:app
    print("CORS Example")
    print("Run with: gunicorn examples.cors_example:app")
    print("Try curl -H 'Origin: https://mydomain.com' http://localhost:8000/api/")
