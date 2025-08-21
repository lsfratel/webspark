import mimetypes
import os
import time
from datetime import datetime
from email.utils import formatdate
from typing import Any

from ..constants import STATUS_CODE
from ..http.cookie import serialize_cookie
from ..utils import HTTPException, cached_property, serialize_json


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
        data: Any,
        *,
        path: str = "/",
        max_age: int = 3600,
        same_site: str = "Lax",
        secrets: list[str] | None = None,
        secure: bool = False,
        http_only: bool = True,
        expires: datetime | int | None = None,
    ):
        self._cookies.append(
            serialize_cookie(
                name,
                data,
                path=path,
                max_age=max_age,
                same_site=same_site,
                secrets=secrets,
                secure=secure,
                http_only=http_only,
                expires=expires,
            )
        )

    def delete_cookie(self, name: str):
        """Delete a cookie by setting its expiration to the past.

        Args:
            name: Name of the cookie to delete.
        """
        self.set_cookie(name, "", max_age=-1, expires=0)

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
        self,
        data: Any,
        status: int = 200,
        headers: dict[str, str] | None = None,
    ):
        """Initialize a JsonResponse.

        Args:
            data: Python object to serialize to JSON.
            status: HTTP status code (default: 200).
            headers: Additional headers.
        """
        super().__init__(data, status, headers, "application/json; charset=utf-8")

    @cached_property
    def _body_bytes(self) -> bytes:
        """Convert response body to bytes.

        Returns:
            bytes: The response body as bytes.
        """
        if isinstance(self.body, bytes):
            return self.body
        if isinstance(self.body, str):
            return self.body.encode(self.charset)
        if hasattr(self.body, "__bytes__"):
            return bytes(self.body)

        return serialize_json(self.body)


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


class RedirectResponse(Response):
    """HTTP redirect response.

    This class creates a response that redirects the client to a new URL.
    By default, it issues a temporary redirect (302), but can be configured
    for permanent redirects (301).

    Example:
        # Temporary redirect
        response = RedirectResponse("/new-location")

        # Permanent redirect
        response = RedirectResponse("/new-home", permanent=True)
    """

    def __init__(
        self,
        url: str,
        permanent: bool = False,
        headers: dict[str, str] | None = None,
    ):
        """Initialize a RedirectResponse.

        Args:
            url: The URL to redirect to.
            permanent: If True, issues a 301 permanent redirect.
                       Otherwise, issues a 302 temporary redirect.
            headers: Additional headers.
        """
        status = 301 if permanent else 302
        headers = {**(headers or {}), "Location": url}
        super().__init__(b"", status, headers, None)


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
        download: str | None = None,
    ):
        """Initialize a StreamResponse.

        Args:
            content: Content to stream (bytes, file path, or iterable).
            status: HTTP status code (default: 200).
            headers: Additional headers.
            content_type: Content-Type header.
            chunk_size: Size of chunks for file streaming (default: 4096).
            download: Name of attachment file for download (optional).
        """
        self.chunk_size = chunk_size
        self.content_type = content_type
        headers = headers or {}

        if isinstance(content, bytes):
            content_type = content_type or "application/octet-stream"
            headers["content-length"] = str(len(content))
            super().__init__([content], status, headers, content_type)
        elif isinstance(content, str | os.PathLike):
            if not os.path.exists(content) or not os.path.isfile(content):
                raise HTTPException("File does not exist.", status_code=404)
            if not os.access(content, os.R_OK):
                raise HTTPException(
                    "You do not have permission to access this file.", status_code=403
                )
            self.file_path = content
            if content_type:
                headers["content-type"] = content_type
            else:
                content_type, encoding = mimetypes.guess_type(content)
                if encoding == "gzip":
                    content_type = "application/gzip"
                elif encoding:
                    content_type = f"application/x-{encoding}"
            if content_type and "charset=" not in content_type:
                if (
                    content_type.startswith("text/")
                    or content_type == "application/javascript"
                ):
                    content_type += "; charset=utf-8"

            content_type = content_type or "application/octet-stream"
            stats = os.stat(content)
            headers["content-length"] = str(stats.st_size)
            headers["last-modified"] = formatdate(stats.st_mtime, usegmt=True)
            headers["date"] = formatdate(time.time(), usegmt=True)
            if download:
                headers["content-disposition"] = f'attachment; filename="{download}"'
            super().__init__(self.file_iterator(), status, headers, content_type)
        else:
            content_type = content_type or "application/octet-stream"
            super().__init__(content, status, headers, content_type)

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
