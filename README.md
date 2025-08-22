# WebSpark ✨

**A lightweight, minimalist Python web framework for building WSGI applications and APIs.**

[![Code Coverage](https://img.shields.io/codecov/c/github/lsfratel/webspark?style=for-the-badge)](https://codecov.io/gh/lsfratel/webspark)
[![License](https://img.shields.io/github/license/lsfratel/webspark?style=for-the-badge)](https://github.com/lsfratel/webspark/blob/main/LICENSE)

WebSpark provides a simple yet powerful architecture for handling HTTP requests and responses, featuring a robust routing system, class-based views, middleware support, and a powerful data validation engine. It's designed for developers who want speed and flexibility without the overhead of a larger framework.

## Features

-   **Zero Runtime Dependencies**: A pure WSGI framework with no external dependencies required.
-   **Powerful Routing**: Flexible, parameterized routing with support for nesting and wildcards.
-   **Class-Based Views**: Intuitive request handling with automatic dispatching based on HTTP methods.
-   **Data Validation**: A declarative schema system for validating request bodies and query parameters.
-   **Middleware via Plugins**: A simple plugin system for request/response processing and cross-cutting concerns.
-   **Modern HTTP Toolkit**: Clean abstractions for Requests, Responses, and Cookies.
-   **Optimized JSON Handling**: Automatically uses the fastest available JSON library (`orjson`, `ujson`, or `json`).
-   **Built-in File Uploads**: Seamlessly handle multipart form data and file uploads.
-   **Comprehensive Error Handling**: A simple `HTTPException` system for clear and consistent error responses.

## Installation

Install WebSpark directly from GitHub using `pip`:

```bash
pip install git+https://github.com/lsfratel/webspark.git
```

Or, if you are developing locally with [PDM](https://pdm-project.org/):

```bash
# Clone the repository
git clone https://github.com/lsfratel/webspark.git
cd webspark

# Install dependencies with PDM
pdm install
```

## Quick Start

Create a file named `app.py` and get a server running in under a minute.

```python
# app.py
from webspark.core import WebSpark, View, path
from webspark.http import JsonResponse

# 1. Define a View
class HelloView(View):
    """A view to handle requests to the root URL."""
    def handle_get(self, request):
        # The `handle_get` method is automatically called for GET requests.
        return JsonResponse({"message": "Hello, from WebSpark! ✨"})

# 2. Create the application instance
app = WebSpark()

# 3. Add the route to the application
app.add_paths([
    path("/", view=HelloView.as_view())
])

# 4. To run, use a WSGI server like Gunicorn:
# gunicorn app:app
```

Now, run your application with a WSGI server:

```bash
gunicorn app:app
```

Open your browser to `http://127.0.0.1:8000`, and you should see the JSON response!

---

## Core Concepts

### 1. Routing

WebSpark's router is powerful and flexible. Use the `path` helper to define routes and add them to your application with `app.add_paths()`.

#### Parameterized Routes

Capture parts of the URL by defining parameters with a colon (`:`).

```python
# Route for /users/123
path("/users/:id", view=UserDetailView.as_view())

# Optional parameter (matches /users/123 and /users/123/profile)
path("/users/:id/profile?", view=UserProfileView.as_view())

# Wildcard route (matches /files/path/to/your/file.txt)
path("/files/*path", view=FileView.as_view())
```

#### Nested Routes

Organize your routes by nesting `path` objects. The parent path's pattern is automatically prefixed to its children.

```python
app.add_paths([
    path("/api/v1", children=[
        path("/users", view=UsersView.as_view()),
        path("/posts", view=PostsView.as_view()),
    ])
])
# Registers /api/v1/users and /api/v1/posts
```

### 2. Class-Based Views

Views handle the logic for your routes. They are classes that inherit from `webspark.core.views.View`.

-   **Method Dispatch**: Requests are automatically routed to `handle_<method>` methods (e.g., `handle_get`, `handle_post`).
-   **Request Object**: Each handler method receives a `Request` object with all the request details.

```python
from webspark.core import View
from webspark.http import JsonResponse, HTMLResponse

class UserView(View):
    def handle_get(self, request):
        """Handles GET /users/:id"""
        user_id = request.path_params.get('id')
        page = request.query_params.get('page', 1) # Access query params with a default

        return JsonResponse({"user_id": user_id, "page": page})

    def handle_post(self, request):
        """Handles POST /users"""
        data = request.body # Access parsed JSON body
        # ... create a new user ...
        return JsonResponse({"created": True, "data": data}, status=201)
```

### 3. Schema Validation

Ensure your incoming data is valid by defining schemas. If validation fails, WebSpark automatically returns a `400 Bad Request` response.

Define a schema by inheriting from `ObjectSchema` and adding fields.

```python
from webspark.schema import ObjectSchema, StringField, IntegerField, EmailField

class UserSchema(ObjectSchema):
    name = StringField(required=True, max_length=100)
    age = IntegerField(min_value=18)
    email = EmailField(required=True)
```

Attach the schema to a view using the `body_schema` or `query_params_schema` attributes.

```python
class CreateUserView(View):
    body_schema = UserSchema  # Validate the request body

    def handle_post(self, request):
        # This method is only called if the body is valid.
        # Access the validated data:
        validated_data = self.validated_body()

        # ... process the data ...
        return JsonResponse({"user": validated_data})
```

#### Available Fields

WebSpark offers a rich set of fields for comprehensive validation: `StringField`, `IntegerField`, `FloatField`, `BooleanField`, `ListField`, `SerializerField` (for nested objects), `DateTimeField`, `UUIDField`, `EmailField`, `URLField`, `EnumField`, `DecimalField`, `MethodField` and `RegexField`.

### 4. Responses

WebSpark provides convenient `Response` subclasses for common content types.

```python
from webspark.http import JsonResponse, HTMLResponse, TextResponse, StreamResponse, RedirectResponse

# JSON response (most common for APIs)
return JsonResponse({"message": "Success"})

# HTML response
return HTMLResponse("<h1>Hello, World!</h1>")

# Plain text response
return TextResponse("OK")

# Stream a large file without loading it all into memory
return StreamResponse("/path/to/large/video.mp4")

# Redirect response
return RedirectResponse("/new-url")
```

### 5. Cookies

Easily set and delete cookies on the `Response` object.

```python
class AuthView(View):
    def handle_post(self, request):
        # Set a cookie on login
        response = JsonResponse({"logged_in": True})
        response.set_cookie("session_id", "abc123", path="/", max_age=3600, httponly=True, secure=True)
        return response

    def handle_delete(self, request):
        # Delete a cookie on logout
        response = JsonResponse({"logged_out": True})
        response.delete_cookie("session_id")
        return response
```

### 6. Middleware (Plugins)

Plugins allow you to hook into the request-response lifecycle. A plugin is a class that implements an `apply` method, which wraps a view handler.

Here is a simple logging plugin:

```python
from webspark.core import Plugin

class LoggingPlugin(Plugin):
    def apply(self, handler):
        # This method returns a new handler that wraps the original one.
        def wrapped_handler(request):
            print(f"Request: {request.method} {request.path}")
            response = handler(request) # The original view handler is called here
            print(f"Response: {response.status}")
            return response
        return wrapped_handler

# Register the plugin globally
app = WebSpark(plugins=[LoggingPlugin()])

# Or apply it to a specific path
app.add_paths([
    path("/admin", view=AdminView.as_view(), plugins=[AuthPlugin()])
])
```

### 7. Error Handling

Gracefully handle errors using `HTTPException`. When raised, the framework will catch it and generate a standardized JSON error response.

```python
from webspark.utils import HTTPException

class UserView(View):
    def handle_get(self, request):
        user_id = request.path_params.get('id')
        user = find_user_by_id(user_id) # Your database logic

        if not user:
            # This will generate a 404 Not Found response
            raise HTTPException("User not found", status_code=404)

        return JsonResponse({"user": user.serialize()})
```

### 8. Custom Exception Handlers

WebSpark allows you to define custom handlers for specific HTTP status codes using the `@app.handle_exception(status_code)` decorator. This is useful for overriding the default JSON error response and providing custom error pages or formats.

The handler function receives the `request` and the `exception` object and must return a `Response` object.

```python
from webspark.http import HTMLResponse, TextResponse

app = WebSpark(debug=True)

@app.handle_exception(404)
def handle_not_found(request, exc):
    """Custom handler for 404 Not Found errors."""
    return HTMLResponse("<h1>Oops! Page not found.</h1>", status=404)

@app.handle_exception(500)
def handle_server_error(request, exc):
    """Custom handler for 500 Internal Server Error."""
    if app.debug:
        # In debug mode, show the full exception
        return TextResponse(str(exc), status=500)
    return HTMLResponse("<h1>A server error occurred.</h1>", status=500)
```

### 9. Proxy Configuration

If your WebSpark application is running behind a reverse proxy (like Nginx or a load balancer), you'll need to configure it to correctly handle headers like `X-Forwarded-For` and `X-Forwarded-Proto`. This ensures that `request.ip`, `request.scheme`, and `request.host` reflect the original client information, not the proxy's.

Proxy support is configured on the `WebSpark` application instance via a configuration object.

```python
class AppConfig:
    TRUST_PROXY = True
    # For more granular control, you can also specify:
    # TRUSTED_PROXY_LIST = ["192.168.1.1", "10.0.0.1"] # List of trusted proxy IPs
    # TRUSTED_PROXY_COUNT = 1 # Number of trusted proxies in the chain

app = WebSpark(config=AppConfig())
```

-   **`TRUST_PROXY`**: (bool) Set to `True` to enable proxy header processing. Defaults to `False`.
-   **`TRUSTED_PROXY_LIST`**: (list) A list of trusted proxy IP addresses. If set, only requests from these IPs will have their proxy headers processed.
-   **`TRUSTED_PROXY_COUNT`**: (int) The number of reverse proxies that are trusted in the chain. This is useful when you have a known number of proxies.

The framework checks for the following headers when `TRUST_PROXY` is enabled:
-   `X-Forwarded-For` and `X-Real-IP` for the client's IP address.
-   `X-Forwarded-Proto` for the request scheme (`http` or `https`).
-   `X-Forwarded-Host` for the original host.

### 10. Allowed Hosts

To prevent HTTP Host header attacks, WebSpark checks the request's `Host` header against a list of allowed hostnames. This is configured via the `ALLOWED_HOSTS` setting on the configuration object.

```python
class AppConfig:
    # Allow requests only to "mydomain.com" and any subdomain of "api.mydomain.com"
    ALLOWED_HOSTS = ["mydomain.com", ".api.mydomain.com"]

app = WebSpark(config=AppConfig())
```

-   **Behavior**:
    -   If `debug=True`, `ALLOWED_HOSTS` defaults to `["*"]` (allowing all hosts).
    -   If `debug=False` and `ALLOWED_HOSTS` is not set, all requests will be rejected with a `400 Bad Request` error.
-   **Matching**:
    -   `"mydomain.com"`: Matches the exact domain.
    -   `".mydomain.com"`: Matches `mydomain.com` and any subdomain (e.g., `api.mydomain.com`).
    -   `"*"`: Matches any host.

### 11. Environment Variable Helper

WebSpark includes a convenient `env` helper function in `webspark.utils` to simplify reading and parsing environment variables.

```python
from webspark.utils import env

# Get a string value with a default
DATABASE_URL = env("DATABASE_URL", default="sqlite:///default.db")

# Get an integer, raising an error if not set
PORT = env("PORT", parser=int, raise_exception=True)

# Get a boolean value (handles "true", "1", "yes", "on")
DEBUG = env("DEBUG", default=False, parser=bool)
```

This helper streamlines configuration management, making it easy to handle different data types and required settings.

## Development

### Running Tests

This project uses `pdm` and `pytest`.

```bash
# Run all tests
pdm run pytest
```

### Code Quality

We use `ruff` for linting and formatting.

```bash
# Check for linting errors
pdm run ruff check .

# Format the code
pdm run ruff format .
```

## Project Structure

```
webspark/
├── core/          # Core components (WSGI app, router, views, schemas)
├── http/          # HTTP abstractions (request, response, cookies)
├── utils/         # Utilities (exceptions, JSON handling)
└── constants.py   # HTTP constants and error codes
```

## Contributing

Contributions are welcome! Please feel free to fork the repository, make your changes, and submit a pull request.

1.  Fork the repository.
2.  Create your feature branch (`git checkout -b feature/AmazingFeature`).
3.  Commit your changes (`git commit -m 'Add some AmazingFeature'`).
4.  Push to the branch (`git push origin feature/AmazingFeature`).
5.  Open a pull request.

## License

This project is licensed under the MIT License. See the [LICENSE](LICENSE) file for details.
