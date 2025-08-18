# WebSpark Examples

This directory contains several self-contained examples demonstrating different features of the WebSpark framework.

## Examples

1. **[basic_api.py](basic_api.py)** - A simple REST API with CRUD operations
   - Basic routing
   - GET and POST methods
   - JSON responses
   - Simple in-memory data storage

2. **[schema_example.py](schema_example.py)** - Data validation with schemas
   - Using ObjectSchema for request body validation
   - Field validation with different data types
   - Automatic error responses for invalid data

3. **[plugins_example.py](plugins_example.py)** - Middleware and exception handling
   - Creating and using plugins (middleware)
   - Custom exception handlers
   - Advanced routing with nested paths

4. **[cookies_example.py](cookies_example.py)** - Session management with cookies
   - Setting and reading cookies
   - Simple session management
   - HTML responses

5. **[config_example.py](config_example.py)** - Configuration, proxy, and security
   - Application configuration
   - Proxy configuration for production deployments
   - Allowed hosts security feature
   - Environment variable usage

6. **[file_upload_example.py](file_upload_example.py)** - Handling file uploads
   - Handling multipart form data
   - Saving uploaded files
   - Returning file information

7. **[database_example.py](database_example.py)** - Database integration
   - Using SQLite with direct connections
   - CRUD operations with database models
   - Error handling for database operations

## Running the Examples

To run any of these examples, use a WSGI server like Gunicorn:

```bash
# Install dependencies first (if not already done)
pip install git+https://github.com/lsfratel/webspark.git

# Run an example
gunicorn examples.basic_api:app
gunicorn examples.schema_example:app
gunicorn examples.plugins_example:app
gunicorn examples.cookies_example:app
gunicorn examples.config_example:app
gunicorn examples.file_upload_example:app
gunicorn examples.database_example:app
```

Or with PDM (if developing locally):

```bash
# Install dependencies
pdm install

# Run an example
pdm run gunicorn examples.basic_api:app
```

Each example will run on `http://127.0.0.1:8000` by default.
