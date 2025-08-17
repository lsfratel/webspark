import os
from email.message import Message
from enum import Enum
from tempfile import NamedTemporaryFile
from typing import TYPE_CHECKING, Any, Literal

from ..utils import HTTPException

if TYPE_CHECKING:
    from tempfile import _TemporaryFileWrapper


class DelimiterEnum(bytes, Enum):
    UNDEF = b""
    CRLF = b"\r\n"
    LF = b"\n"


EncodingErrors = Literal["strict", "ignore", "replace"]
FileFields = dict[str, dict | list[dict]]
FormFields = dict[str, str | list]


class MultipartParser:
    """Parser for HTTP multipart/form-data requests.

    This class parses multipart form data from HTTP requests, handling both
    form fields and file uploads. It supports streaming large file uploads
    to temporary files and correctly handles various boundary delimiters.

    Example:
        environ = {
            "CONTENT_TYPE": "multipart/form-data; boundary=----WebKitFormBoundary",
            "CONTENT_LENGTH": "1024",
            "wsgi.input": io.BytesIO(form_data)
        }

        parser = MultipartParser(environ)
        forms, files = parser.parse()

        # Access form fields
        username = forms["username"][0]

        # Access uploaded files
        avatar_file = files["avatar"][0]
        file_path = avatar_file["tempfile"]

    Attributes:
        forms (dict): Dictionary of parsed form fields.
        files (dict): Dictionary of parsed file uploads.
    """

    def __init__(
        self,
        environ: dict[str, Any],
        *,
        max_body_size: int = 2 * 1024 * 1024,
        chunk_size: int = 4096,
        encoding: str = "utf-8",
        encoding_errors: EncodingErrors = "strict",
    ) -> None:
        """Initialize the MultipartParser.

        Args:
            environ: WSGI environment dictionary.
            max_body_size: Maximum allowed request body size in bytes (default: 2MB).
            chunk_size: Size of chunks to read at a time (default: 4KB).
            encoding: Text encoding for form data (default: "utf-8").
            encoding_errors: How to handle encoding errors (default: "strict").
        """
        self._environ = environ
        self._cfield: dict[str, str] = {}
        self._ccontent = b""
        self._cstream: None | _TemporaryFileWrapper[bytes] = None
        self._max_body_size = max_body_size
        self._chunk_size = chunk_size
        self._encoding = encoding
        self._encoding_errors = encoding_errors
        self._delimiter: DelimiterEnum = DelimiterEnum.UNDEF

        self.forms: FormFields = {}
        self.files: FileFields = {}

    @property
    def boundary(self) -> str:
        """Extract boundary parameter from Content-Type header.

        Returns:
            str: The boundary string.

        Raises:
            HTTPException: If boundary is missing from Content-Type header.
        """
        ctype = self._environ.get("CONTENT_TYPE", "")
        message = Message()
        message["Content-Type"] = ctype
        boundary = message.get_param("boundary")

        if not boundary:
            raise HTTPException(
                "Missing boundary in Content-Type header",
                status_code=400,
            )

        charset = message.get_param("charset")
        if charset:
            self._encoding = str(charset)

        return str(boundary)

    @property
    def content_length(self) -> int:
        """Get the Content-Length from the environment.

        Returns:
            int: Content length, or -1 if not specified.
        """
        return int(self._environ.get("CONTENT_LENGTH", -1))

    def parse(self):
        """Parse the multipart request data.

        Returns:
            tuple: A tuple containing (forms_dict, files_dict).

        Raises:
            HTTPException: For various parsing errors.
            Exception: For other parsing failures.
        """
        try:
            self._parse()
        except Exception:
            self._cleanup()
            raise

        return self.forms, self.files

    def _detect_delimiter(self, buffer: bytes, boundary: bytes, blength: int):
        """Detect the line delimiter used in the multipart data.

        Args:
            buffer: Buffer containing multipart data.
            boundary: Boundary string.
            blength: Length of boundary.

        Returns:
            DelimiterEnum: The detected delimiter (CRLF or LF).

        Raises:
            ValueError: If delimiter cannot be determined.
        """
        idx = buffer.find(boundary)
        if idx < 0:
            raise ValueError("Unable to determine line delimiter.")

        if buffer[idx + blength : idx + blength + 2] == DelimiterEnum.CRLF.value:
            return DelimiterEnum.CRLF
        if buffer[idx + blength : idx + blength + 1] == DelimiterEnum.LF.value:
            return DelimiterEnum.LF
        raise ValueError("Unable to determine line delimiter.")

    def _cleanup(self):
        """Clean up temporary resources and reset parser state.

        This method closes any open temporary file streams and removes
        temporary files from disk. It also resets all internal state.
        """
        if self._cstream is not None:
            if not self._cstream.closed:
                self._cstream.close()
            if os.path.exists(self._cstream.name):
                os.remove(self._cstream.name)

        self._cfield = {}
        self._ccontent = b""
        self._cstream = None
        self.forms = {}
        self.files = {}

    def _create_tempfile(self):
        """Create a temporary file for storing uploaded file data.

        Returns:
            NamedTemporaryFile: A temporary file object.
        """
        return NamedTemporaryFile(prefix="webspark-", suffix=".tmp", delete=False)

    def _on_body_end(self):
        """Handle the end of a form field body parsing.

        This method is called when a form field's content has been fully parsed.
        It decodes the content and adds it to the forms dictionary.
        """
        name = self._cfield["name"]
        content = self._ccontent.decode(self._encoding, self._encoding_errors)

        if name in self.forms:
            if isinstance(self.forms[name], list):
                self.forms[name].append(content)
            else:
                self.forms[name] = [self.forms[name], content]
        else:
            self.forms[name] = content

        self._cfield = {}
        self._ccontent = b""

    def _on_fbody_end(self):
        """Handle the end of a file body parsing.

        This method is called when a file upload's content has been fully parsed.
        It closes the temporary file and adds file information to the files dictionary.
        """
        if self._cstream is None:
            return

        self._cstream.close()

        name = self._cfield["name"]
        filename = self._cfield["filename"]
        ctype = self._cfield["content_type"]

        field = {
            "filename": filename,
            "tempfile": self._cstream.name,
            "content_type": ctype,
        }

        if name in self.files:
            if isinstance(self.files[name], list):
                self.files[name].append(field)
            else:
                self.files[name] = [self.files[name], field]
        else:
            self.files[name] = field

        self._cfield = {}
        self._cstream = None

    def _process_headers(self, data: bytes):
        """Process multipart part headers.

        Args:
            data: Raw header bytes to process.

        Raises:
            HTTPException: If Content-Disposition header is missing.
        """
        headers = [
            h.strip().decode(self._encoding, self._encoding_errors)
            for h in data.split(self._delimiter.value)
            if h
        ]
        message = Message()

        for h in headers:
            if ":" not in h:
                continue
            key, value = h.split(":", 1)
            message[key] = value.strip()

        if "Content-Disposition" not in message:
            raise HTTPException(
                "Missing Content-Disposition header.",
                status_code=400,
            )

        filename = message.get_param("filename", header="Content-Disposition")
        if filename:
            self._cfield["filename"] = str(filename)

        self._cfield["content_type"] = message.get_content_type()
        self._cfield["name"] = str(
            message.get_param("name", header="Content-Disposition")
        )

    def _parse(self):
        boundary = f"--{self.boundary}".encode()
        blength = len(boundary)
        read = self._environ["wsgi.input"].read
        chunk_size = self._chunk_size
        remaining = self.content_length

        buffer: bytes = read(min(chunk_size, remaining))
        remaining -= len(buffer)

        try:
            self._delimiter = self._detect_delimiter(buffer, boundary, blength)
        except ValueError as e:
            raise HTTPException(
                f"Invalid multipart/form-data: {e}", status_code=400
            ) from e

        delimiter = self._delimiter.value
        delimiter_double = delimiter * 2
        start_idx = buffer.find(boundary)

        if start_idx == -1:
            raise HTTPException(
                "Invalid multipart/form-data: boundary not found", status_code=400
            )

        buffer = buffer[start_idx + blength :]
        if buffer.startswith(delimiter):
            buffer = buffer[len(delimiter) :]

        while not buffer.startswith(b"--"):
            header_end_idx = buffer.find(delimiter_double)
            while header_end_idx == -1:
                if remaining <= 0:
                    raise HTTPException(
                        "Invalid multipart/form-data: malformed part headers",
                        status_code=400,
                    )
                chunk = read(min(chunk_size, remaining))
                if not chunk:
                    break
                remaining -= len(chunk)
                buffer += chunk
                header_end_idx = buffer.find(delimiter_double)

            if header_end_idx == -1:
                raise HTTPException(
                    "Invalid multipart/form-data: part header terminator not found",
                    status_code=400,
                )

            headers_bytes = buffer[:header_end_idx]
            buffer = buffer[header_end_idx + len(delimiter_double) :]
            self._process_headers(headers_bytes)

            is_file = "filename" in self._cfield
            if is_file:
                self._cstream = self._create_tempfile()
            else:
                self._ccontent = b""

            next_boundary_idx = buffer.find(boundary)
            while next_boundary_idx == -1:
                tail_size = blength + 2
                if len(buffer) > tail_size:
                    to_process, buffer = buffer[:-tail_size], buffer[-tail_size:]
                else:
                    to_process = b""

                if to_process:
                    if is_file:
                        self._cstream.write(to_process)
                    else:
                        self._ccontent += to_process

                if remaining <= 0:
                    raise HTTPException(
                        "Invalid multipart/form-data: closing boundary not found.",
                        status_code=400,
                    )

                chunk = read(min(chunk_size, remaining))
                if not chunk:
                    break
                remaining -= len(chunk)
                buffer += chunk
                next_boundary_idx = buffer.find(boundary)

            if next_boundary_idx == -1:
                raise HTTPException(
                    "Invalid multipart/form-data: part body terminator not found.",
                    status_code=400,
                )

            body_part = buffer[:next_boundary_idx]
            buffer = buffer[next_boundary_idx + blength :]

            if body_part.endswith(delimiter):
                body_part = body_part[: -len(delimiter)]

            if is_file:
                self._cstream.write(body_part)
                self._on_fbody_end()
            else:
                self._ccontent += body_part
                self._on_body_end()

            if buffer.startswith(delimiter):
                buffer = buffer[len(delimiter) :]
