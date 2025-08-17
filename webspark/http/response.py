import mimetypes
import os
from typing import Any

from ..constants import STATUS_CODE
from ..http.cookie import Cookie
from ..utils import cached_property, serialize_json


class Response:
    """Base HTTP Response class for WebSpark applications.

    This class provides the foundation for all HTTP responses in WebSpark.
    It handles status codes, headers, cookies, and body serialization to bytes.

    Example:
        # Create a simple response
        response = Response("Hello, World!", status=200)

        # Create a response with custom headers
        response = Response(
            body="<h1>Hello</h1>",
            status=200,
            headers={"X-Custom": "value"},
            content_type="text/html"
        )

        # Add cookies
        response.set_cookie("session_id", "abc123")

        # Convert to WSGI format
        status, headers, body_iter = response.as_wsgi()

    Attributes:
        body: The response body (bytes, string, or any object).
        status: HTTP status code.
        charset: Character set for string encoding.
        headers: Response headers dictionary.
    """

    def __init__(
        self,
        body: bytes | str | Any = b"",
        status: int = 200,
        headers: dict[str, str] | None = None,
        content_type: str | None = None,
        charset="utf-8",
    ):
        """Initialize a Response object.

        Args:
            body: Response body (bytes, string, or any object).
            status: HTTP status code (default: 200).
            headers: Response headers dictionary.
            content_type: Content-Type header value.
            charset: Character set for string encoding (default: "utf-8").

        Raises:
            ValueError: If status code is invalid (not between 100-599).
        """
        if not 100 <= status <= 599:
            raise ValueError(f"Invalid HTTP status code: {status}.")

        self.body = body
        self.status = status
        self.charset = charset
        self.headers = {k.lower(): v for k, v in headers.items()} if headers else {}
        self._cookies: list[str] = []

        if content_type:
            self.headers["content-type"] = content_type

    def set_cookie(
        self,
        name: str,
        value: Any,
        options: dict[str, Any] | None = None,
        overrides: dict[str, Any] | None = None,
    ):
        """Set a cookie in the response.

        Args:
            name: Cookie name.
            value: Cookie value.
            options: Cookie options (see Cookie class for available options).
            overrides: Options that override default cookie options.
        """
        cookie = Cookie(name, options)
        self._cookies.append(cookie.serialize(value, overrides))

    def delete_cookie(self, name: str, options: dict[str, Any] | None = None):
        """Delete a cookie by setting its expiration to the past.

        Args:
            name: Name of the cookie to delete.
            options: Additional cookie options.
        """
        options = options or {}
        options["max_age"] = -1
        options["expires"] = 0
        self.set_cookie(name, "", options)

    def set_header(self, name: str, value: str):
        """Set a response header.

        Args:
            name: Header name.
            value: Header value.
        """
        self.headers[name.lower()] = value
        self.__dict__.pop("_body_bytes", None)

    def get_header(self, name: str) -> str | None:
        """Get a response header value.

        Args:
            name: Header name.

        Returns:
            str | None: Header value or None if not set.
        """
        return self.headers.get(name.lower())

    def delete_header(self, name: str):
        """Delete a response header.

        Args:
            name: Header name to delete.
        """
        self.headers.pop(name.lower(), None)
        self.__dict__.pop("_body_bytes", None)

    @cached_property
    def _body_bytes(self) -> bytes:
        """Convert response body to bytes.

        Returns:
            bytes: The response body as bytes.
        """
        return self._to_bytes(self.body)

    def as_wsgi(self):
        """Convert response to WSGI format.

        Returns:
            tuple: A tuple of (status_string, headers_list, body_iterator).
        """
        status_str = STATUS_CODE.get(self.status, f"{self.status} Unknown")
        body_bytes = self._body_bytes
        headers_list = list(self.headers.items())

        if "content-length" not in self.headers:
            headers_list.append(("Content-Length", str(len(body_bytes))))

        for cookie in self._cookies:
            headers_list.append(("Set-Cookie", cookie))

        return status_str, headers_list, [body_bytes]

    def _to_bytes(self, body: Any) -> bytes:
        """Convert body to bytes.

        Args:
            body: Response body (bytes, string, or any object).

        Returns:
            bytes: The body converted to bytes.
        """
        if isinstance(body, bytes):
            return body
        if isinstance(body, str):
            return body.encode(self.charset)
        if hasattr(body, "__bytes__"):
            return bytes(body)
        return str(body).encode(self.charset)


class TextResponse(Response):
    """Plain text HTTP response.

    This class creates a response with Content-Type set to text/plain.

    Example:
        response = TextResponse("Hello, World!")
    """

    def __init__(
        self,
        text: str,
        status: int = 200,
        headers: dict[str, str] | None = None,
    ):
        """Initialize a TextResponse.

        Args:
            text: The plain text content.
            status: HTTP status code (default: 200).
            headers: Additional headers.
        """
        super().__init__(text, status, headers, "text/plain; charset=utf-8")


class JsonResponse(Response):
    """JSON HTTP response.

    This class creates a response with Content-Type set to application/json
    and automatically serializes Python objects to JSON.

    Example:
        response = JsonResponse({"message": "Hello, World!", "status": "success"})
    """

    def __init__(
        self, data: Any, status: int = 200, headers: dict[str, str] | None = None
    ):
        """Initialize a JsonResponse.

        Args:
            data: Python object to serialize to JSON.
            status: HTTP status code (default: 200).
            headers: Additional headers.
        """
        json_body = serialize_json(data)
        super().__init__(json_body, status, headers, "application/json; charset=utf-8")


class HTMLResponse(Response):
    """HTML HTTP response.

    This class creates a response with Content-Type set to text/html.

    Example:
        response = HTMLResponse("<html><body><h1>Hello, World!</h1></body></html>")
    """

    def __init__(
        self,
        html: str,
        status: int = 200,
        headers: dict[str, str] | None = None,
    ):
        """Initialize an HTMLResponse.

        Args:
            html: The HTML content.
            status: HTTP status code (default: 200).
            headers: Additional headers.
        """
        super().__init__(html, status, headers, "text/html; charset=utf-8")


class StreamResponse(Response):
    """Streaming HTTP response for large files or data.

    This class handles streaming responses, particularly useful for serving
    large files without loading them entirely into memory.

    Example:
        # Stream a file
        response = StreamResponse("/path/to/large/file.mp4")

        # Stream generated content
        def content_generator():
            for i in range(1000):
                yield f"Line {i}\n".encode()
        response = StreamResponse(content_generator())
    """

    def __init__(
        self,
        content: Any,
        status: int = 200,
        headers: dict[str, str] | None = None,
        content_type: str | None = None,
        chunk_size: int = 4096,
    ):
        """Initialize a StreamResponse.

        Args:
            content: Content to stream (bytes, file path, or iterable).
            status: HTTP status code (default: 200).
            headers: Additional headers.
            content_type: Content-Type header.
            chunk_size: Size of chunks for file streaming (default: 4096).
        """
        self.chunk_size = chunk_size
        self.content_type = content_type

        if isinstance(content, str | os.PathLike):
            self.file_path = str(content)
            content_type = (
                content_type
                or mimetypes.guess_type(self.file_path)[0]
                or "application/octet-stream"
            )
            super().__init__(self.file_iterator(), status, headers, content_type)
            self.set_content_length()
        elif isinstance(content, bytes):
            content_type = content_type or "application/octet-stream"
            super().__init__([content], status, headers, content_type)
            self.headers["content-length"] = str(len(content))
        else:
            content_type = content_type or "application/octet-stream"
            super().__init__(content, status, headers, content_type)

    def set_content_length(self):
        """Set the Content-Length header based on file size.

        This method attempts to determine the file size and set the appropriate
        Content-Length header. It silently ignores errors if the file doesn't exist
        or cannot be accessed.
        """
        try:
            file_size = os.path.getsize(self.file_path)
            self.headers["content-length"] = str(file_size)
        except (AttributeError, OSError):
            pass

    def file_iterator(self):
        """Iterator that yields file content in chunks.

        Yields:
            bytes: File content chunks.
        """
        with open(self.file_path, "rb") as f:
            while True:
                chunk = f.read(self.chunk_size)
                if not chunk:
                    break
                yield chunk

    def as_wsgi(self):
        """Convert streaming response to WSGI format.

        Returns:
            tuple: A tuple of (status_string, headers_list, body_iterator).
        """
        status_str = STATUS_CODE.get(self.status, f"{self.status} Unknown")
        headers_list = list(self.headers.items())
        return status_str, headers_list, self.body


def SuccessResponse(
    data: Any, status: int = 200, headers: dict[str, str] | None = None
) -> JsonResponse:
    """Create a standardized success JSON response.

    This utility function creates a JsonResponse with a standardized
    success format that includes a success flag and wrapped data.

    Example:
        response = SuccessResponse({"user_id": 123, "username": "john_doe"})
        # Creates JSON: {"success": true, "data": {"user_id": 123, "username": "john_doe"}}

    Args:
        data: The data to wrap in the success response.
        status: HTTP status code (default: 200).
        headers: Additional headers.

    Returns:
        JsonResponse: A JSON response with success structure.
    """
    return JsonResponse(
        {
            "success": True,
            "data": data,
        },
        status=status,
        headers=headers,
    )
