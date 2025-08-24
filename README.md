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
-   **Proxy Support**: Built-in support for running behind a reverse proxy.
-   **Environment Configuration**: Helper utilities for managing configuration via environment variables.
-   **Extensive Testing**: 90% test coverage ensuring reliability and stability.

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
from webspark.http import Context

# 1. Define a View
class HelloView(View):
    """A view to handle requests to the root URL."""
    def handle_get(self, ctx: Context):
        # The `handle_get` method is automatically called for GET requests.
        ctx.json({"message": "Hello, from WebSpark! ✨"})

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

## More Examples

Check out the [examples](examples/) directory for more comprehensive examples:

1. **[Basic API](examples/basic_api.py)** - A simple REST API with CRUD operations
2. **[Schema Validation](examples/schema_example.py)** - Data validation with schemas
3. **[Plugins/Middleware](examples/plugins_example.py)** - Middleware and exception handling
4. **[Cookies](examples/cookies_example.py)** - Session management with cookies
5. **[Configuration](examples/config_example.py)** - Proxy configuration and security
6. **[File Uploads](examples/file_upload_example.py)** - Handling multipart form data
7. **[Database Integration](examples/database_example.py)** - Working with databases
8. **[CORS](examples/cors_example.py)** - Cross-Origin Resource Sharing configuration
9. **[Token Auth](examples/auth_example.py)** - Token-based authentication
10. **[Schema Plugin](examples/schema_plugin_example.py)** - Schema validation with the SchemaPlugin

---

## Core Concepts

### 1. Routing

WebSpark's router is powerful and flexible. Use the `path` helper to define routes and add them to your application with `app.add_paths()`.

#### Parameterized Routes

Capture parts of the URL by defining parameters with a colon (`:`).

```python
# Route for /users/123
path("/users/:id", view=UserDetailView.as_view())

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
-   **Context Object**: Each handler method receives a `Context` object with all the request details.

```python
from webspark.core import View
from webspark.http import Context

class UserView(View):
    def handle_get(self, ctx: Context):
        """Handles GET /users/:id"""
        user_id = ctx.path_params.get('id')
        page = ctx.query_params.get('page', 1) # Access query params with a default

        ctx.json({"user_id": user_id, "page": page})

    def handle_post(self, ctx):
        """Handles POST /users"""
        data = ctx.body # Access parsed JSON body
        # ... create a new user ...
        ctx.json({"created": True, "data": data}, status=201)
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


class CreateUserView(View):

    def handle_post(self, ctx: Context):
        # This method is only called if the body is valid.
        # Access the validated data:

        schema_instance = UserSchema(data=ctx.body)

        if not schema_instance.is_valid():
            raise HTTPException(schema_instance.errors, status_code=400)

        # ... process the data ...
        ctx.json({"user": schema_instance.validated_data})
```

#### Available Fields

WebSpark offers a rich set of fields for comprehensive validation:

- `StringField` - String validation with min/max length
- `IntegerField` - Integer validation with min/max value
- `FloatField` - Float validation with min/max value
- `BooleanField` - Boolean value validation
- `ListField` - List validation with item type specification
- `SerializerField` - Nested object validation
- `DateTimeField` - ISO format datetime validation
- `UUIDField` - UUID validation
- `EmailField` - Email format validation
- `URLField` - URL format validation
- `EnumField` - Enumeration value validation
- `DecimalField` - Decimal number validation
- `MethodField` - Custom validation method
- `RegexField` - Regular expression validation

### 4. Responses

WebSpark provides convenient `Context` that simplifies request handling and response generation.

```python
from webspark.http import Context

# JSON response (most common for APIs)
ctx.json({"message": "Success"})

# HTML response
ctx.html("<h1>Hello, World!</h1>")

# Plain text response
ctx.text("OK")

# Stream a large file without loading it all into memory
ctx.stream("/path/to/large/video.mp4")

# Redirect response
ctx.redirect("/new-url")
```

### 5. Cookies

Easily set and delete cookies on the `Context` object.

```python
class AuthView(View):
    def handle_post(self, ctx: Context):
        # Set a cookie on login
        ctx.set_cookie("session_id", "abc123", path="/", max_age=3600, httponly=True, secure=True)
        ctx.json({"logged_in": True})

    def handle_delete(self, ctx: Context):
        # Delete a cookie on logout
        ctx.delete_cookie("session_id")
        ctx.json({"logged_out": True})
```

### 6. Middleware (Plugins)

Plugins allow you to hook into the request-response lifecycle. A plugin is a class that implements an `apply` method, which wraps a view handler.

Here is a simple logging plugin:

```python
from webspark.core import Plugin

class LoggingPlugin(Plugin):
    def apply(self, handler):
        # This method returns a new handler that wraps the original one.
        def wrapped_handler(ctx):
            print(f"Request: {ctx.method} {ctx.path}")
            handler(ctx) # The original view handler is called here
            print(f"Response: {ctx.status}")
        return wrapped_handler

# Register the plugin globally
app = WebSpark(plugins=[LoggingPlugin()])

# Or apply it to a specific path
app.add_paths([
    path("/admin", view=AdminView.as_view(), plugins=[AuthPlugin()])
])
```

#### CORS Plugin

WebSpark includes a CORS (Cross-Origin Resource Sharing) plugin that implements the full CORS specification. It supports both simple and preflighted requests with configurable origins, methods, headers, and credentials.

```python
from webspark.contrib.plugins import CORSPlugin

# Create a CORS plugin with a specific configuration
cors_plugin = CORSPlugin(
    allow_origins=["https://mydomain.com", "https://api.mydomain.com"],
    allow_methods=["GET", "POST", "PUT", "DELETE"],
    allow_headers=["Content-Type", "Authorization", "X-Requested-With"],
    allow_credentials=True,
    max_age=86400,  # 24 hours
    expose_headers=["X-Custom-Header"]
)

# Register the plugin globally
app = WebSpark(plugins=[cors_plugin])

# Or apply it to specific paths
app.add_paths([
    path("/api/", view=APIView.as_view(), plugins=[cors_plugin])
])
```

The CORS plugin supports the following configuration options:

- `allow_origins` - List of allowed origins. Use `["*"]` to allow all origins (not recommended for production with credentials).
- `allow_methods` - List of allowed HTTP methods.
- `allow_headers` - List of allowed headers.
- `allow_credentials` - Whether to allow credentials (cookies, authorization headers).
- `max_age` - How long the preflight response should be cached (in seconds).
- `expose_headers` - List of headers that browsers are allowed to access.
- `vary_header` - Whether to add Vary header for preflight requests.

#### AllowedHosts Plugin

To prevent HTTP Host header attacks, WebSpark provides an `AllowedHostsPlugin`. This plugin checks the request's `Host` header against a list of allowed hostnames.

```python
from webspark.contrib.plugins import AllowedHostsPlugin

# Allow requests only to "mydomain.com" and any subdomain of "api.mydomain.com"
allowed_hosts_plugin = AllowedHostsPlugin(
    allowed_hosts=["mydomain.com", ".api.mydomain.com"]
)

# Register the plugin globally
app = WebSpark(plugins=[allowed_hosts_plugin])
```

-   **Behavior**:
    -   If `allowed_hosts` is not set, all requests will be rejected with a `400 Bad Request` error, ensuring that only requests from specified hosts are processed.
-   **Matching**:
    -   `"mydomain.com"`: Matches the exact domain.
    -   `".mydomain.com"`: Matches `mydomain.com` and any subdomain (e.g., `api.mydomain.com`).
    -   `"*"`: Matches any host.

#### TokenAuth Plugin

WebSpark provides a `TokenAuthPlugin` for implementing token-based authentication, typically used for APIs.
This plugin can check for a token either in the **Authorization header** or in a **cookie**, and then validates it using a provided function.

```python
from webspark.contrib.plugins import TokenAuthPlugin

# A simple function to validate a token and return a user object.
# In a real application, this would check a database or cache.
def get_user_from_token(token: str):
    if token == "secret-token":
        return {"username": "admin"}
    return None

# Create a token auth plugin (header-based by default)
token_auth_plugin = TokenAuthPlugin(token_loader=get_user_from_token)

# Or configure it to read from a cookie instead:
cookie_auth_plugin = TokenAuthPlugin(
    token_loader=get_user_from_token,
    cookie_name="auth_token",   # will look for Cookie: auth_token=<token>
)

# Apply the plugin to a protected view
app.add_paths([
    path("/protected", view=ProtectedView.as_view(), plugins=[token_auth_plugin])
])
```

-   **Behavior**:
    -   By default, the plugin expects an **Authorization** header in the format `Authorization: Token <your-token>`, the scheme (`Token`) can be customized when instantiating the plugin.
    -   If `cookie_name` is provided, the plugin will first check for a cookie with that name `Cookie: auth_token=<your-token>`, if not found, it falls back to the Authorization header.
    -   If no valid token is found, the plugin returns a `401 Unauthorized` response with a `WWW-Authenticate` header.
    -   If the token is successfully validated by the `token_loader` function, the returned user object is attached to the context as `ctx.state["user"]` and the request proceeds to the view.

#### Schema Validation Plugin

WebSpark provides a `SchemaPlugin` for validating data from the request context using an `ObjectSchema`. This plugin can validate any data accessible through the context object, such as the request body, query parameters, or path parameters.

The plugin reads a value from the view context using `ctx_prop`. If that value is callable, it is invoked with `ctx_args` to obtain the data. The data is then validated using the provided `schema`. If validation succeeds, the validated data is injected into the handler's keyword arguments. If validation fails, an HTTPException with status code 400 is raised.

You can apply the SchemaPlugin using the `@apply` decorator from `webspark.utils.decorators`:

```python
from webspark.contrib.plugins import SchemaPlugin
from webspark.core import View
from webspark.http import Context
from webspark.schema import ObjectSchema, StringField, IntegerField
from webspark.utils import apply

# Define a schema for validation
class UserSchema(ObjectSchema):
    name = StringField(required=True, max_length=100)
    age = IntegerField(min_value=1, max_value=120)

class UserView(View):
    @apply(
        SchemaPlugin(UserSchema, ctx_prop="body", kw="validated_body"),
    )
    def handle_post(self, ctx: Context, validated_body: dict):
        # The validated_body parameter contains the validated data
        ctx.json({"received": validated_body}, status=201)
```

In this example:
- `ctx_prop="body"` tells the plugin to read data from `ctx.body`
- `kw="validated_body"` specifies that the validated data should be passed to the handler as the `validated_body` keyword argument
- If validation fails, an HTTP 400 error is automatically returned with details about the validation errors

You can also apply the plugin to a specific path when registering routes:

```python
app.add_paths([
    path("/users", view=UserView.as_view(), plugins=[
        SchemaPlugin(UserSchema, ctx_prop="body", kw="validated_body")
    ])
])
```

### 7. Error Handling

Gracefully handle errors using `HTTPException`. When raised, the framework will catch it and generate a standardized JSON error response.

```python
from webspark.utils import HTTPException

class UserView(View):
    def handle_get(self, ctx):
        user_id = ctx.path_params.get('id')
        user = find_user_by_id(user_id) # Your database logic

        if not user:
            # This will generate a 404 Not Found response
            raise HTTPException("User not found", status_code=404)

        ctx.json({"user": user.serialize()})
```

### 8. Custom Exception Handlers

WebSpark allows you to define custom handlers for specific HTTP status codes using the `@app.handle_exception(status_code)` decorator. This is useful for overriding the default JSON error response and providing custom error pages or formats.

The handler function receives the `request` and the `exception` object and must return a `Response` object.

```python
from webspark.http import Context

app = WebSpark(debug=True)

@app.handle_exception(404)
def handle_not_found(ctx: Context, exc: Exception):
    """Custom handler for 404 Not Found errors."""
    ctx.html("<h1>Oops! Page not found.</h1>", status=404)

@app.handle_exception(500)
def handle_server_error(ctx: Context, exc: Exception):
    """Custom handler for 500 Internal Server Error."""
    if app.debug:
        # In debug mode, show the full exception
        ctx.text(str(exc), status=500)
    else:
      ctx.html("<h1>A server error occurred.</h1>", status=500)
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

### 10. Environment Variable Helper

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

### 11. File Uploads

WebSpark makes handling file uploads simple with built-in multipart form data parsing. Uploaded files are accessible through the `ctx.files` attribute.

```python
class FileUploadView(View):
    def handle_post(self, ctx: Context):
        # Check if request has files
        if not ctx.files:
            raise HTTPException("No files uploaded", status_code=400)

        # Process each uploaded file
        for field_name, file_list in ctx.files.items():
            # file_list can be a single file dict or list of file dicts
            files = file_list if isinstance(file_list, list) else [file_list]

            for file_info in files:
                # file_info contains:
                # - filename: original filename
                # - content_type: MIME type
                # - file: file-like object with read() method

                # Save the file
                with open(f"/uploads/{file_info['filename']}", "wb") as f:
                    f.write(file_info["file"].read())
```

---

## Development

### Running Tests

This project uses `pdm` and `pytest`.

```bash
# Run all tests
pdm run pytest

# Run tests with coverage
pdm run tests
```

### Code Quality

We use `ruff` for linting and formatting.

```bash
# Check for linting errors
pdm run ruff check .

# Format the code
pdm run ruff format .
```

---

## Project Structure

```
webspark/
├── core/          # Core components (WSGI app, router, views, schemas)
├── contrib/       # Optional plugins (CORS, AllowedHosts)
├── http/          # HTTP abstractions (request, response, cookies)
├── schema/        # Data validation schemas and fields
├── utils/         # Utilities (exceptions, JSON handling, env vars)
├── examples/      # Comprehensive usage examples
├── tests/         # Test suite for all components
├── constants.py   # HTTP constants and error codes
└── __init__.py    # Package metadata
```

### Core Modules

- **core/** - Contains the fundamental building blocks:
  - `WebSpark` - The main WSGI application class
  - `View` - Base class for request handlers
  - `path` - Routing helper function
  - `Plugin` - Base class for middleware

- **contrib/plugins/** - Optional plugins:
  - `CORSPlugin` - Handles Cross-Origin Resource Sharing.
  - `AllowedHostsPlugin` - Validates incoming Host headers.
  - `TokenAuthPlugin` - Token-based authentication middleware for securing endpoints.
  - `SchemaPlugin` - Validates data from the request context using ObjectSchema.

- **http/** - HTTP abstractions:
  - `Context` - Request/response context object
  - `Cookie` - Cookie handling utilities
  - `multipart` - File upload handling

- **schema/** - Data validation:
  - `ObjectSchema` - Base class for validation schemas
  - `fields` - Validation field types

- **utils/** - Utility functions:
  - `HTTPException` - Standardized error handling
  - `env` - Environment variable helper
  - `json` - Optimized JSON handling

## Contributing

Contributions are welcome! Please feel free to fork the repository, make your changes, and submit a pull request.

1.  Fork the repository.
2.  Create your feature branch (`git checkout -b feature/AmazingFeature`).
3.  Commit your changes (`git commit -m 'Add some AmazingFeature'`).
4.  Push to the branch (`git push origin feature/AmazingFeature`).
5.  Open a pull request.

Please ensure your code follows the project's style guidelines and includes appropriate tests.

## License

This project is licensed under the MIT License. See the [LICENSE](LICENSE) file for details.
