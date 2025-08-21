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
    """
    Streaming HTTP response for large files, raw bytes, or iterables.

    Supports:
      - Streaming files in chunks (avoids loading into memory).
      - Returning raw bytes or iterables as a response.
      - Handling HTTP Range requests (`206 Partial Content`) for partial downloads.
      - Optional `Accept-Ranges` header to advertise support.

    Examples:
        >>> # Stream raw bytes
        response = StreamResponse(b"hello world")

        >>> # Stream a file
        response = StreamResponse("/path/to/file.mp4")

        >>> # Support partial download
        response = StreamResponse("/path/to/file.mp4", range_header="bytes=0-99")
    """

    def __init__(
        self,
        content: Any,
        status: int = 200,
        headers: dict[str, str] | None = None,
        content_type: str | None = None,
        chunk_size: int = 4096,
        download: str | None = None,
        range_header: str | None = None,
        accept_ranges: str | None = "bytes",
    ):
        """
        Initialize a StreamResponse.

        Args:
            content: Response body (bytes, file path, PathLike, or iterable).
            status: HTTP status code (default: 200).
            headers: Optional headers to include.
            content_type: MIME type to use (default guessed from file or binary).
            chunk_size: Chunk size when streaming files (default: 4096).
            download: Optional filename to suggest for download (adds Content-Disposition).
            range_header: Raw HTTP Range header string, e.g. "bytes=0-499".
            accept_ranges: Value for "Accept-Ranges" header (default: "bytes").
        """
        self.chunk_size = chunk_size
        self.content_type = content_type
        self.range_header = range_header
        headers = headers or {}

        body, final_status, final_headers, final_type = self._prepare_content(
            content, status, headers, content_type, download
        )

        if accept_ranges:
            final_headers["accept-ranges"] = accept_ranges

        super().__init__(body, final_status, final_headers, final_type)

    def _prepare_content(
        self,
        content: Any,
        status: int,
        headers: dict[str, str],
        content_type: str | None,
        download: str | None,
    ):
        """
        Inspect content type and delegate handling.

        Returns:
            tuple: (body, status, headers, content_type)
        """
        if isinstance(content, bytes):
            return self._handle_bytes(content, status, headers, content_type)

        if isinstance(content, str | os.PathLike):
            return self._handle_file(content, status, headers, content_type, download)

        return self._handle_iterable(content, status, headers, content_type)

    def _handle_bytes(
        self,
        content: bytes,
        status: int,
        headers: dict[str, str],
        content_type: str | None,
    ):
        """
        Handle response when `content` is raw bytes.

        Supports full responses and partial responses if `Range` header is present.

        Returns:
            tuple: (body, status, headers, content_type)
        """
        content_type = content_type or "application/octet-stream"
        total_size = len(content)

        if self.range_header:
            start, end = self._parse_range(self.range_header, total_size)
            headers["content-range"] = f"bytes {start}-{end}/{total_size}"
            headers["content-length"] = str(end - start + 1)
            return [content[start : end + 1]], 206, headers, content_type

        headers["content-length"] = str(total_size)
        return [content], status, headers, content_type

    def _handle_file(
        self,
        path: str | os.PathLike,
        status: int,
        headers: dict[str, str],
        content_type: str | None,
        download: str | None,
    ):
        """
        Handle response when `content` is a file path.

        Validates file existence and permissions, detects MIME type,
        and supports Range requests.

        Returns:
            tuple: (body_iterator, status, headers, content_type)
        """
        path = os.fspath(path)
        if not os.path.exists(path) or not os.path.isfile(path):
            raise HTTPException("File does not exist.", status_code=404)

        if not os.access(path, os.R_OK):
            raise HTTPException(
                "You do not have permission to access this file.", status_code=403
            )

        self.file_path = path
        content_type = self._detect_mimetype(path, content_type)

        stats = os.stat(path)
        file_size = stats.st_size

        headers["last-modified"] = formatdate(stats.st_mtime, usegmt=True)
        headers["date"] = formatdate(time.time(), usegmt=True)
        if download:
            headers["content-disposition"] = f'attachment; filename="{download}"'

        if self.range_header:
            start, end = self._parse_range(self.range_header, file_size)
            headers["content-range"] = f"bytes {start}-{end}/{file_size}"
            headers["content-length"] = str(end - start + 1)
            return self.file_iterator(start, end), 206, headers, content_type

        headers["content-length"] = str(file_size)
        return self.file_iterator(), status, headers, content_type

    def _handle_iterable(
        self,
        content: Any,
        status: int,
        headers: dict[str, str],
        content_type: str | None,
    ):
        """
        Handle response when `content` is an iterable.

        Note:
            Range requests are not supported for iterables.

        Returns:
            tuple: (iterable, status, headers, content_type)
        """
        content_type = content_type or "application/octet-stream"
        return content, status, headers, content_type

    def _detect_mimetype(self, path: str, content_type: str | None) -> str:
        """
        Guess MIME type from file extension or fallback to default.

        Adds `charset=utf-8` for text/* and JavaScript.

        Args:
            path: File path.
            content_type: Explicit content type, if provided.

        Returns:
            str: Final MIME type.
        """
        if content_type:
            return content_type

        guessed, encoding = mimetypes.guess_type(path)
        if encoding == "gzip":
            guessed = "application/gzip"
        elif encoding:
            guessed = f"application/x-{encoding}"

        if guessed and "charset=" not in guessed:
            if guessed.startswith("text/") or guessed == "application/javascript":
                guessed += "; charset=utf-8"

        return guessed or "application/octet-stream"

    def _parse_range(self, range_header: str, total_size: int):
        """
        Parse an HTTP Range header.

        Example: "bytes=0-499" → (0, 499)

        Args:
            range_header: Value of the Range header.
            total_size: Size of the content in bytes.

        Returns:
            tuple[int, int]: (start, end) byte positions.

        Raises:
            HTTPException: If the range is invalid.
        """
        try:
            unit, _, range_spec = range_header.partition("=")
            if unit.strip().lower() != "bytes":
                raise ValueError
            start_str, _, end_str = range_spec.partition("-")

            start = int(start_str) if start_str else 0
            end = int(end_str) if end_str else total_size - 1

            if start > end or start >= total_size:
                raise ValueError

            return start, min(end, total_size - 1)
        except ValueError as e:
            raise HTTPException("Invalid Range header.", status_code=416) from e

    def file_iterator(self, start: int = 0, end: int | None = None):
        """
        Yield file content in chunks.

        Args:
            start: Starting byte offset (default: 0).
            end: Ending byte offset (inclusive). Defaults to end of file.

        Yields:
            bytes: Chunks of the file within the given range.
        """
        end = end if end is not None else os.stat(self.file_path).st_size - 1
        with open(self.file_path, "rb") as f:
            f.seek(start)
            remaining = end - start + 1
            while remaining > 0:
                chunk = f.read(min(self.chunk_size, remaining))
                if not chunk:
                    break
                yield chunk
                remaining -= len(chunk)

    def as_wsgi(self):
        """
        Convert response into WSGI-compatible triple.

        Returns:
            tuple[str, list[tuple[str, str]], Any]:
                (status line, headers, body iterable)
        """
        status_str = STATUS_CODE.get(self.status, f"{self.status} Unknown")
        headers_list = list(self.headers.items())
        return status_str, headers_list, self.body
