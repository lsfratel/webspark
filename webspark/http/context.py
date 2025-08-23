from __future__ import annotations

import io
import json
import mimetypes
import os
import time
from datetime import datetime
from email.utils import formatdate
from typing import TYPE_CHECKING, Any
from urllib.parse import parse_qs

if TYPE_CHECKING:
    from ..core.views import View
    from ..core.wsgi import WebSpark

from ..constants import BODY_METHODS, STATUS_CODE
from ..http.cookie import parse_cookie, serialize_cookie
from ..http.multipart import MultipartParser
from ..utils import HTTPException, cached_property, deserialize_json, serialize_json

_SUPPORTED_CONTENT_TYPES = frozenset(
    ("application/x-www-form-urlencoded", "application/json", "multipart/form-data")
)


class Context:
    """HTTP Context for WebSpark applications - combines Request and Response functionality.

    This class provides a unified interface for handling HTTP requests and responses.
    It includes all request data access methods and response building capabilities in
    a single object.

    Example:
        # In a view handler
        def handle_post(self, ctx):
            # Access request data
            page = ctx.query_params.get("page", 1)
            data = ctx.body

            # Check uploaded files
            if "avatar" in ctx.files:
                upload = ctx.files["avatar"]
                if isinstance(upload, list):
                    upload = upload[0]
                file_content = upload["file"].read()

            # Build response
            ctx.json({"received": data, "page": page})
            ctx.set_cookie("session", "abc123")

            # Or use shorthand methods
            # ctx.text("Hello World")
            # ctx.html("<h1>Hello</h1>")
            # ctx.redirect("/success")

    Request Attributes:
        environ (dict): The WSGI environment dictionary.
        method (str): The HTTP method (get, post, put, etc.).
        path (str): The request path.
        query_params (dict): Parsed query parameters.
        headers (dict): Request headers.
        content_type (str): Content-Type header value.
        content_length (int): Content-Length header value.
        charset (str): Character set from Content-Type header.
        cookies (dict): Parsed cookies.
        body (dict): Parsed request body.
        files (dict): Parsed file uploads (for multipart requests).

    Response Attributes:
        status (int): HTTP status code.
        response_headers (dict): Response headers.
        response_body: Response body content.

    Attributes:
        state (dict): A user-defined dictionary for internal state management.
    """

    def __init__(self, environ: dict[str, str]):
        """Initialize a Context object.

        Args:
            environ: WSGI environment dictionary.
        """
        self.environ = environ
        self._forms: dict[str, Any] | None = None
        self._files: dict[str, Any] | None = None
        self._body: dict[str, Any] | None = None
        self._multipart_parser: MultipartParser | None = None

        self.status = 200
        self.response_headers: dict[str, str] = {}
        self.response_body: bytes | str | Any = b""
        self.response_charset = "utf-8"
        self._cookies: list[str] = []
        self._responded = False

        self.state: dict[Any, Any] = {}

    def __del__(self):
        if self._multipart_parser:
            self._multipart_parser._cleanup()

    def _parse_multipart(self):
        """Parse multipart form data if not already parsed."""
        if self._forms is not None:
            return

        stream = self.environ.get("wsgi.input", io.BytesIO())
        content_type = self.headers.get("content-type", "")

        self._multipart_parser = MultipartParser(
            stream=stream,
            content_type=content_type,
            content_length=self.content_length,
            max_body_size=self.max_body_size,
            encoding=self.charset,
        )

        self._forms, self._files = self._multipart_parser.parse()

    def _get_forwarded_ips(self) -> list[str]:
        """Return a list of IPs from X-Forwarded-For header and REMOTE_ADDR."""
        x_forwarded_for = self.headers.get("x-forwarded-for")
        ips = (
            [ip.strip() for ip in x_forwarded_for.split(",")] if x_forwarded_for else []
        )
        remote_addr = self.environ.get("REMOTE_ADDR")
        if remote_addr:
            ips.append(remote_addr)
        return ips

    def _is_proxy_trusted(self) -> bool:
        if not getattr(self.webspark.config, "TRUST_PROXY", False):
            return False

        trusted_proxies = getattr(self.webspark.config, "TRUSTED_PROXY_LIST", None)
        if trusted_proxies:
            remote_addr = self.environ.get("REMOTE_ADDR", "")
            if remote_addr not in trusted_proxies:
                return False

        return True

    @cached_property
    def cookies(self) -> dict[str, Any]:
        """Parse and return cookies from the request.

        Returns:
            dict: Parsed cookies as key-value pairs.
        """
        cookie_header = self.headers.get("cookie", "")
        if not cookie_header:
            return {}

        secret = getattr(self.webspark.config, "SECRET", "!S!U!P!E!R!S!I!C!R!E!T!")
        return parse_cookie(cookie_header, secret)

    @property
    def view_instance(self) -> View:
        """Get the view instance that handled this request."""
        return self.environ["webspark.view_instance"]

    @property
    def webspark(self) -> WebSpark:
        """Get the WebSpark instance."""
        return self.environ["webspark.instance"]

    @property
    def body(self) -> dict[str, Any]:
        """Get the parsed request body."""
        if self._body is not None:
            return self._body

        if self.method not in BODY_METHODS:
            raise HTTPException(
                f"Body is only allowed for {', '.join(BODY_METHODS)} methods.",
                status_code=405,
            )

        content_length = self.content_length
        if content_length > self.max_body_size:
            raise HTTPException(
                f"Request body too large. Maximum allowed: {self.max_body_size} bytes.",
                status_code=413,
            )

        if content_length and not self.content_type:
            raise HTTPException("Missing Content-Type header.", status_code=400)

        content_type = self.content_type
        if content_type not in _SUPPORTED_CONTENT_TYPES:
            raise HTTPException(
                f"Unsupported Content-Type: {content_type}", status_code=415
            )

        if content_type == "multipart/form-data":
            self._parse_multipart()
            self._body = self._forms
            return self._body or {}

        stream = self.environ.get("wsgi.input", io.BytesIO())
        raw_body = stream.read(content_length or 0)

        try:
            if content_type == "application/x-www-form-urlencoded":
                self._body = {
                    k: v[0] if len(v) == 1 else v
                    for k, v in parse_qs(
                        raw_body.decode("utf-8"), keep_blank_values=True
                    ).items()
                }
            elif content_type == "application/json":
                self._body = (
                    deserialize_json(raw_body.decode("utf-8"))
                    if raw_body.strip()
                    else {}
                )
        except (UnicodeDecodeError, json.JSONDecodeError, ValueError) as e:
            raise HTTPException(
                f"Invalid request body format: {e}", status_code=400
            ) from e

        return self._body or {}

    @property
    def files(self) -> dict[str, Any]:
        """Get parsed file uploads from multipart requests."""
        if self.content_type == "multipart/form-data":
            self._parse_multipart()
            return self._files or {}
        return {}

    @property
    def path_params(self) -> dict[str, str]:
        """Get path parameters extracted from the URL route."""
        return getattr(self, "_path_params", {})

    @path_params.setter
    def path_params(self, params: dict[str, str]):
        """Set path parameters extracted from the URL route."""
        self._path_params = params

    @cached_property
    def max_body_size(self) -> int:
        """Get the maximum allowed body size for the request in bytes."""
        return getattr(self.webspark.config, "MAX_BODY_SIZE", 10 * 1024 * 1024)

    @cached_property
    def method(self) -> str:
        """Get the HTTP method of the request."""
        return self.environ.get("REQUEST_METHOD", "GET").lower()

    @cached_property
    def path(self) -> str:
        """Get the request path."""
        return self.environ.get("PATH_INFO", "/")

    @cached_property
    def query_params(self) -> dict[str, Any]:
        """Get parsed query parameters from the URL."""
        qs_raw = self.environ.get("QUERY_STRING", "")
        if not qs_raw:
            return {}

        try:
            return {
                k: v[0] if len(v) == 1 else v
                for k, v in parse_qs(
                    qs_raw, keep_blank_values=True, strict_parsing=True
                ).items()
            }
        except (ValueError, UnicodeDecodeError):
            return {}

    @cached_property
    def headers(self) -> dict[str, str]:
        """Get HTTP headers from the request."""
        headers = {
            key[5:].replace("_", "-").lower(): value
            for key, value in self.environ.items()
            if key.startswith("HTTP_")
        }

        if "CONTENT_TYPE" in self.environ:
            headers["content-type"] = self.environ["CONTENT_TYPE"]

        if "CONTENT_LENGTH" in self.environ:
            headers["content-length"] = self.environ["CONTENT_LENGTH"]

        return headers

    @cached_property
    def content_type(self) -> str | None:
        """Get the Content-Type header value without parameters."""
        content_type = self.environ.get("CONTENT_TYPE")
        return content_type.split(";")[0].strip().lower() if content_type else None

    @cached_property
    def content_length(self) -> int:
        """Get the Content-Length header value."""
        try:
            return max(0, int(self.environ.get("CONTENT_LENGTH", 0) or 0))
        except (ValueError, TypeError):
            return 0

    @cached_property
    def charset(self) -> str:
        """Get the charset from the Content-Type header."""
        content_type = self.headers.get("content-type", "")
        if ";" not in content_type:
            return "utf-8"

        for param in content_type.split(";")[1:]:
            if "=" in param:
                k, v = param.split("=", 1)
                if k.strip().lower() == "charset":
                    return (v.strip().strip('"').strip("'") or "utf-8").lower()

        return "utf-8"

    @cached_property
    def ip(self) -> str:
        """Get the client's IP address."""
        if not getattr(self.webspark.config, "TRUST_PROXY", False):
            return self.environ.get("REMOTE_ADDR", "")

        ips = self._get_forwarded_ips()
        if not ips:
            x_real_ip = self.headers.get("x-real-ip")
            if x_real_ip:
                return x_real_ip.strip()
            return self.environ.get("REMOTE_ADDR", "")

        trusted_proxies = getattr(self.webspark.config, "TRUSTED_PROXY_LIST", None)
        if trusted_proxies:
            if ips[-1] not in trusted_proxies:
                return ips[-1]

            for ip in reversed(ips):
                if ip not in trusted_proxies:
                    return ip
            return ips[0]

        proxy_count = getattr(self.webspark.config, "TRUSTED_PROXY_COUNT", 0)
        if proxy_count > 0:
            if len(ips) > proxy_count:
                return ips[-(proxy_count + 1)]
            else:
                return ips[0]

        x_forwarded_for = self.headers.get("x-forwarded-for")
        if x_forwarded_for:
            return x_forwarded_for.split(",")[0].strip()

        x_real_ip = self.headers.get("x-real-ip")
        if x_real_ip:
            return x_real_ip.strip()

        return self.environ.get("REMOTE_ADDR", "")

    @cached_property
    def scheme(self) -> str:
        """Get the request scheme, respecting X-Forwarded-Proto."""
        if self._is_proxy_trusted():
            x_forwarded_proto = self.headers.get("x-forwarded-proto")
            if x_forwarded_proto:
                return x_forwarded_proto.split(",")[0].strip().lower()
        return self.environ.get("wsgi.url_scheme", "http")

    @property
    def is_secure(self) -> bool:
        """Check if the request is secure (HTTPS)."""
        return self.scheme == "https"

    @cached_property
    def host(self) -> str:
        """Get the request host, respecting X-Forwarded-Host."""
        if self._is_proxy_trusted():
            x_forwarded_host = self.headers.get("x-forwarded-host")
            if x_forwarded_host:
                return x_forwarded_host.split(",")[0].strip()
        return self.environ.get("HTTP_HOST") or self.environ.get("SERVER_NAME", "")

    @cached_property
    def url(self) -> str:
        """Get the full request URL."""
        host = self.host
        if not host:
            return self.path

        url = f"{self.scheme}://{host}{self.path}"
        query_string = self.environ.get("QUERY_STRING")
        if query_string:
            url += f"?{query_string}"
        return url

    @cached_property
    def accept(self) -> str:
        """Get the 'Accept' header."""
        return self.headers.get("accept", "")

    @cached_property
    def user_agent(self) -> str:
        """Get the 'User-Agent' header."""
        return self.headers.get("user-agent", "")

    # -

    def set_header(self, name: str, value: str):
        """Set a response header.

        Args:
            name: Header name.
            value: Header value.
        """
        self.response_headers[name.lower()] = value

    def get_header(self, name: str) -> str | None:
        """Get a response header value.

        Args:
            name: Header name.

        Returns:
            str | None: Header value or None if not set.
        """
        return self.response_headers.get(name.lower())

    def delete_header(self, name: str):
        """Delete a response header.

        Args:
            name: Header name to delete.
        """
        self.response_headers.pop(name.lower(), None)

    def set_cookie(
        self,
        name: str,
        data: Any,
        *,
        path: str = "/",
        max_age: int = 3600,
        same_site: str = "Lax",
        secure: bool = False,
        http_only: bool = True,
        expires: datetime | int | None = None,
    ):
        """Set a cookie in the response.

        Args:
            name: Cookie name.
            data: Cookie value.
            path: Cookie path.
            max_age: Maximum age in seconds.
            same_site: SameSite attribute.
            secrets: List of secret keys for signing.
            secure: Secure flag.
            http_only: HttpOnly flag.
            expires: Expiration date.
        """
        secret = getattr(self.webspark.config, "SECRET", "!S!U!P!E!R!S!I!C!R!E!T!")
        self._cookies.append(
            serialize_cookie(
                name,
                data,
                path=path,
                max_age=max_age,
                same_site=same_site,
                secret=secret,
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

    def text(self, content: str, status: int = 200):
        """Send a plain text response.

        Args:
            content: The text content.
            status: HTTP status code.
        """
        self.status = status
        self.response_body = content
        self.set_header("content-type", f"text/plain; charset={self.response_charset}")
        self._responded = True

    def json(self, data: Any, status: int = 200):
        """Send a JSON response.

        Args:
            data: Python object to serialize to JSON.
            status: HTTP status code.
        """
        self.status = status
        self.response_body = data
        self.set_header(
            "content-type", f"application/json; charset={self.response_charset}"
        )
        self._responded = True

    def html(self, content: str, status: int = 200):
        """Send an HTML response.

        Args:
            content: The HTML content.
            status: HTTP status code.
        """
        self.status = status
        self.response_body = content
        self.set_header("content-type", f"text/html; charset={self.response_charset}")
        self._responded = True

    def redirect(self, url: str, permanent: bool = False):
        """Send a redirect response.

        Args:
            url: The URL to redirect to.
            permanent: If True, issues a 301 permanent redirect.
                       Otherwise, issues a 302 temporary redirect.
        """
        self.status = 301 if permanent else 302
        self.response_body = b""
        self.set_header("location", url)
        self._responded = True

    def stream(
        self,
        content: Any,
        status: int = 200,
        content_type: str | None = None,
        chunk_size: int = 4096,
        download: str | None = None,
    ):
        """Send a streaming response.

        Args:
            content: Response body (bytes, file path, or iterable).
            status: HTTP status code.
            content_type: MIME type.
            chunk_size: Chunk size when streaming files.
            download: Optional filename for download.
        """
        self.chunk_size = chunk_size
        self.range_header = self.headers.get("range")

        body, final_status, final_headers, final_type = self._prepare_stream_content(
            content, status, dict(self.response_headers), content_type, download
        )

        final_headers["accept-ranges"] = "bytes"

        self.status = final_status
        self.response_body = body
        self.response_headers.update(final_headers)
        self.set_header("content-type", final_type)
        self._responded = True

    def _prepare_stream_content(
        self,
        content: Any,
        status: int,
        headers: dict[str, str],
        content_type: str | None,
        download: str | None,
    ):
        """Inspect content type and delegate handling for streaming."""
        if isinstance(content, bytes):
            return self._handle_stream_bytes(content, status, headers, content_type)

        if isinstance(content, str | os.PathLike):
            return self._handle_stream_file(
                content, status, headers, content_type, download
            )

        return self._handle_stream_iterable(content, status, headers, content_type)

    def _handle_stream_bytes(
        self,
        content: bytes,
        status: int,
        headers: dict[str, str],
        content_type: str | None,
    ):
        """Handle streaming response when content is raw bytes."""
        content_type = content_type or "application/octet-stream"
        total_size = len(content)

        if self.range_header:
            start, end = self._parse_range(self.range_header, total_size)
            headers["content-range"] = f"bytes {start}-{end}/{total_size}"
            headers["content-length"] = str(end - start + 1)
            return [content[start : end + 1]], 206, headers, content_type

        headers["content-length"] = str(total_size)
        return [content], status, headers, content_type

    def _handle_stream_file(
        self,
        path: str | os.PathLike,
        status: int,
        headers: dict[str, str],
        content_type: str | None,
        download: str | None,
    ):
        """Handle streaming response when content is a file path."""
        path = os.fspath(path)
        if not os.path.exists(path) or not os.path.isfile(path):
            raise HTTPException("File does not exist.", status_code=404)

        if not os.access(path, os.R_OK):
            raise HTTPException(
                "You do not have permission to access this file.", status_code=403
            )

        self.file_path = path
        content_type = self._detect_stream_mimetype(path, content_type)

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
            return self._file_iterator(start, end), 206, headers, content_type

        headers["content-length"] = str(file_size)
        return self._file_iterator(), status, headers, content_type

    def _handle_stream_iterable(
        self,
        content: Any,
        status: int,
        headers: dict[str, str],
        content_type: str | None,
    ):
        """Handle streaming response when content is an iterable."""
        content_type = content_type or "application/octet-stream"
        return content, status, headers, content_type

    def _detect_stream_mimetype(self, path: str, content_type: str | None) -> str:
        """Guess MIME type from file extension or fallback to default."""
        if content_type:
            return content_type

        guessed, encoding = mimetypes.guess_type(path)
        if encoding == "gzip":
            guessed = "application/gzip"
        elif encoding:
            guessed = f"application/x-{encoding}"

        if guessed and "charset=" not in guessed:
            if guessed.startswith("text/") or guessed == "application/javascript":
                guessed += f"; charset={self.response_charset}"

        return guessed or "application/octet-stream"

    def _parse_range(self, range_header: str, total_size: int):
        """Parse an HTTP Range header."""
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

    def _file_iterator(self, start: int = 0, end: int | None = None):
        """Yield file content in chunks."""
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

    def error(self, message: str, status: int = 500):
        """Send an error response.

        Args:
            message: Error message.
            status: HTTP status code.
        """
        self.status = status
        self.response_body = {"error": message, "status": status}
        self.set_header(
            "content-type", f"application/json; charset={self.response_charset}"
        )
        self._responded = True

    def _to_bytes(self, body: Any) -> bytes:
        """Convert body to bytes."""
        if isinstance(body, bytes):
            return body
        if isinstance(body, str):
            return body.encode(self.response_charset)
        if hasattr(body, "__bytes__"):
            return bytes(body)

        content_type = self.get_header("content-type") or ""
        if "application/json" in content_type:
            return serialize_json(body)

        return str(body).encode(self.response_charset)

    @cached_property
    def _body_bytes(self) -> bytes:
        """Convert response body to bytes."""
        return self._to_bytes(self.response_body)

    def as_wsgi(self):
        """Convert context to WSGI format.

        Returns:
            tuple: A tuple of (status_string, headers_list, body_iterator).
        """
        status_str = STATUS_CODE.get(self.status, f"{self.status} Unknown")
        headers_list = list(self.response_headers.items())

        if hasattr(self, "chunk_size") and hasattr(self.response_body, "__iter__"):
            for cookie in self._cookies:
                headers_list.append(("Set-Cookie", cookie))
            return status_str, headers_list, self.response_body
        else:
            body_bytes = self._body_bytes
            if "content-length" not in self.response_headers:
                headers_list.append(("Content-Length", str(len(body_bytes))))

            for cookie in self._cookies:
                headers_list.append(("Set-Cookie", cookie))

            return status_str, headers_list, [body_bytes]

    @property
    def responded(self) -> bool:
        """Check if a response has been set."""
        return self._responded

    def assert_not_responded(self):
        """Raise an exception if a response has already been set."""
        if self._responded:
            raise RuntimeError("Response has already been set for this context.")

    def reset_response(self):
        """Reset the response to allow setting a new one."""
        self.status = 200
        self.response_headers.clear()
        self.response_body = b""
        self._cookies.clear()
        self._responded = False

    def is_ajax(self) -> bool:
        """Check if the request is an AJAX request."""
        return self.headers.get("x-requested-with", "").lower() == "xmlhttprequest"

    def accepts(self, content_type: str) -> bool:
        """Check if the client accepts a specific content type."""
        accept_header = self.accept.lower()
        return content_type.lower() in accept_header or "*/*" in accept_header

    def wants_json(self) -> bool:
        """Check if the client prefers JSON response."""
        return self.accepts("application/json")

    def wants_html(self) -> bool:
        """Check if the client prefers HTML response."""
        return self.accepts("text/html")
