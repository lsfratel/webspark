from __future__ import annotations

import io
import json
from typing import TYPE_CHECKING, Any
from urllib.parse import parse_qs

if TYPE_CHECKING:
    from ..core.views import View
    from ..core.wsgi import WebSpark

from ..constants import BODY_METHODS
from ..utils import HTTPException, cached_property, deserialize_json
from .multipart import MultipartParser

_MAX_CONTENT_LENGTH = 10 * 1024 * 1024
_SUPPORTED_CONTENT_TYPES = frozenset(
    ("application/x-www-form-urlencoded", "application/json", "multipart/form-data")
)


class Request:
    """HTTP Request wrapper for WebSpark applications.

    This class provides a convenient interface for accessing HTTP request data
    including headers, query parameters, form data, and uploaded files. It handles
    parsing of different content types and provides easy access to request metadata.

    Example:
        # In a view handler
        def handle_post(self, request):
            # Access query parameters
            page = request.query_params.get("page", 1)

            # Access request body (JSON, form data, or multipart)
            data = request.body

            # Access uploaded files
            if "avatar" in request.files:
                # request.files['avatar'] is a dict for a single file, or a list of dicts for multiple files.
                upload = request.files["avatar"]
                if isinstance(upload, list):
                    upload = upload[0]  # Taking the first file

                # The 'file' key holds a file-like object for the upload.
                file_content = upload["file"].read()

            return JsonResponse({"received": data})

    Attributes:
        ENV (dict): The WSGI environment dictionary.
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
    """

    def __init__(self, environ: dict[str, str]):
        """Initialize a Request object.

        Args:
            environ: WSGI environment dictionary.
        """
        self.ENV = environ
        self._forms: dict[str, Any] | None = None
        self._files: dict[str, Any] | None = None
        self._body: dict[str, Any] | None = None
        self._multipart_parser: MultipartParser | None = None

    def __del__(self):
        if self._multipart_parser:
            self._multipart_parser._cleanup()

    def _parse_multipart(self):
        """Parse multipart form data if not already parsed.

        This method initializes the multipart parser and parses form data
        and file uploads, storing the results in _forms and _files attributes.
        """
        if self._forms is not None:
            return

        stream = self.ENV.get("wsgi.input", io.BytesIO())
        content_type = self.headers.get("content-type", "")

        self._multipart_parser = MultipartParser(
            stream=stream,
            content_type=content_type,
            content_length=self.content_length,
            max_body_size=_MAX_CONTENT_LENGTH,
            encoding=self.charset,
        )

        self._forms, self._files = self._multipart_parser.parse()

    @property
    def view_instance(self) -> View:
        """Get the view instance that handled this request.

        Returns:
            View: The view instance from the WSGI environment.
        """
        return self.ENV["webspark.view_instance"]

    @property
    def webspark(self) -> WebSpark:
        """Get the WebSpark instance.

        Returns:
            WebSpark: The WebSpark instance from the WSGI environment.
        """
        return self.ENV["webspark.instance"]

    @property
    def body(self) -> dict[str, Any]:
        """Get the parsed request body.

        Returns:
            dict: Parsed request body data.

        Raises:
            HTTPException: If the method doesn't allow a body, if the body is too large,
                          if Content-Type is missing, or if the body format is invalid.
        """
        if self._body is not None:
            return self._body

        if self.method not in BODY_METHODS:
            raise HTTPException(
                f"Body is only allowed for {', '.join(BODY_METHODS)} methods.",
                status_code=405,
            )

        content_length = self.content_length
        if content_length > _MAX_CONTENT_LENGTH:
            raise HTTPException(
                f"Request body too large. Maximum allowed: {_MAX_CONTENT_LENGTH} bytes.",
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

        stream = self.ENV.get("wsgi.input", io.BytesIO())
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
        """Get parsed file uploads from multipart requests.

        Returns:
            dict: Dictionary of uploaded files, or empty dict if not multipart.
        """
        if self.content_type == "multipart/form-data":
            self._parse_multipart()
            return self._files or {}
        return {}

    @property
    def path_params(self) -> dict[str, str]:
        """Get path parameters extracted from the URL route.

        Returns:
            dict: Dictionary of path parameters.
        """
        return getattr(self, "_path_params", {})

    @path_params.setter
    def path_params(self, params: dict[str, str]):
        """Set path parameters extracted from the URL route.

        Args:
            params: Dictionary of path parameters.
        """
        self._path_params = params

    @cached_property
    def method(self) -> str:
        """Get the HTTP method of the request.

        Returns:
            str: The HTTP method in lowercase (e.g., 'get', 'post', 'put').
        """
        return self.ENV.get("REQUEST_METHOD", "GET").lower()

    @cached_property
    def path(self) -> str:
        """Get the request path.

        Returns:
            str: The path portion of the URL.
        """
        return self.ENV.get("PATH_INFO", "/")

    @cached_property
    def query_params(self) -> dict[str, Any]:
        """Get parsed query parameters from the URL.

        Returns:
            dict: Dictionary of query parameters.
        """
        qs_raw = self.ENV.get("QUERY_STRING", "")
        if not qs_raw:
            return {}

        try:
            return {
                k: v[0] if len(v) == 1 else v
                for k, v in parse_qs(qs_raw, keep_blank_values=True).items()
            }
        except (ValueError, UnicodeDecodeError):
            return {}

    @cached_property
    def headers(self) -> dict[str, str]:
        """Get HTTP headers from the request.

        Returns:
            dict: Dictionary of HTTP headers with lowercase keys.
        """
        headers = {
            key[5:].replace("_", "-").lower(): value
            for key, value in self.ENV.items()
            if key.startswith("HTTP_")
        }

        if "CONTENT_TYPE" in self.ENV:
            headers["content-type"] = self.ENV["CONTENT_TYPE"]

        if "CONTENT_LENGTH" in self.ENV:
            headers["content-length"] = self.ENV["CONTENT_LENGTH"]

        return headers

    @cached_property
    def content_type(self) -> str | None:
        """Get the Content-Type header value without parameters.

        Returns:
            str | None: The content type (e.g., 'application/json') or None if not set.
        """
        content_type = self.ENV.get("CONTENT_TYPE")
        return content_type.split(";")[0].strip().lower() if content_type else None

    @cached_property
    def content_length(self) -> int:
        """Get the Content-Length header value.

        Returns:
            int: The content length in bytes, or 0 if not set or invalid.
        """
        try:
            return max(0, int(self.ENV.get("CONTENT_LENGTH", 0) or 0))
        except (ValueError, TypeError):
            return 0

    @cached_property
    def charset(self) -> str:
        """Get the charset from the Content-Type header.

        Returns:
            str: The charset (e.g., 'utf-8'), defaults to 'utf-8' if not specified.
        """
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
    def cookies(self) -> dict[str, Any]:
        """Get parsed cookies from the request.

        Returns:
            dict: Dictionary of cookies.
        """
        cookie_header = self.ENV.get("HTTP_COOKIE", "")
        if not cookie_header:
            return {}

        cookies = {}
        for chunk in cookie_header.split(";"):
            if "=" in chunk:
                key, val = chunk.split("=", 1)
                cookies[key.strip()] = val.strip()
        return cookies
