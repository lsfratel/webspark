import io
from unittest.mock import Mock, patch

import pytest

from webspark.http.multipart import MultipartParser
from webspark.utils.exceptions import HTTPException


def test_multipart_parser_initialization():
    """Test MultipartParser initialization with default values."""
    stream = io.BytesIO(b"")
    content_type = "multipart/form-data; boundary=boundary"
    content_length = 0

    parser = MultipartParser(stream, content_type, content_length)

    assert parser._stream == stream
    assert parser._content_type == content_type
    assert parser._content_length == content_length
    assert parser._max_body_size == 2 * 1024 * 1024
    assert parser._chunk_size == 4096
    assert parser._encoding == "utf-8"
    assert parser._encoding_errors == "strict"
    assert parser.forms == {}
    assert parser.files == {}


def test_multipart_parser_initialization_with_custom_values():
    """Test MultipartParser initialization with custom values."""
    stream = io.BytesIO(b"")
    content_type = "multipart/form-data; boundary=boundary"
    content_length = 0

    parser = MultipartParser(
        stream,
        content_type,
        content_length,
        max_body_size=1024,
        chunk_size=512,
        encoding="latin1",
        encoding_errors="ignore",
    )

    assert parser._max_body_size == 1024
    assert parser._chunk_size == 512
    assert parser._encoding == "latin1"
    assert parser._encoding_errors == "ignore"


def test_boundary_property():
    """Test boundary property extraction."""
    stream = io.BytesIO(b"")
    content_type = "multipart/form-data; boundary=----WebKitFormBoundary7MA4YWxkTrZu0gW"
    content_length = 0

    parser = MultipartParser(stream, content_type, content_length)

    assert parser.boundary == "----WebKitFormBoundary7MA4YWxkTrZu0gW"


def test_boundary_property_with_charset():
    """Test boundary property extraction with charset."""
    stream = io.BytesIO(b"")
    content_type = "multipart/form-data; boundary=----WebKitFormBoundary7MA4YWxkTrZu0gW; charset=utf-8"
    content_length = 0

    parser = MultipartParser(stream, content_type, content_length)

    assert parser.boundary == "----WebKitFormBoundary7MA4YWxkTrZu0gW"
    assert parser._encoding == "utf-8"


def test_boundary_property_missing():
    """Test boundary property when boundary is missing."""
    stream = io.BytesIO(b"")
    content_type = "multipart/form-data"
    content_length = 0

    parser = MultipartParser(stream, content_type, content_length)

    with pytest.raises(HTTPException) as exc_info:
        _ = parser.boundary

    assert exc_info.value.status_code == 400
    assert "Missing boundary in Content-Type header" in str(exc_info.value)


def test_content_length_property():
    """Test content_length property."""
    stream = io.BytesIO(b"")
    content_type = "multipart/form-data; boundary=boundary"
    content_length = 1024

    parser = MultipartParser(stream, content_type, content_length)

    assert parser.content_length == 1024


def test_detect_delimiter_crlf():
    """Test _detect_delimiter with CRLF."""
    parser = MultipartParser(io.BytesIO(b""), "", 0)
    boundary = b"----boundary"
    buffer = b"random data----boundary\r\nmore data"
    delimiter = parser._detect_delimiter(buffer, boundary, len(boundary))

    assert delimiter.name == "CRLF"
    assert delimiter.value == b"\r\n"


def test_detect_delimiter_lf():
    """Test _detect_delimiter with LF."""
    parser = MultipartParser(io.BytesIO(b""), "", 0)
    boundary = b"----boundary"
    buffer = b"random data----boundary\nmore data"
    delimiter = parser._detect_delimiter(buffer, boundary, len(boundary))

    assert delimiter.name == "LF"
    assert delimiter.value == b"\n"


def test_detect_delimiter_not_found():
    """Test _detect_delimiter when boundary not found."""
    parser = MultipartParser(io.BytesIO(b""), "", 0)
    boundary = b"----boundary"
    buffer = b"random data without boundary"

    with pytest.raises(ValueError, match="Unable to determine line delimiter"):
        parser._detect_delimiter(buffer, boundary, len(boundary))


def test_cleanup():
    """Test _cleanup method."""
    parser = MultipartParser(io.BytesIO(b""), "", 0)

    # Set some test values
    parser._cfield = {"name": "test"}
    parser._ccontent = b"test content"
    parser.forms = {"field": ["value"]}
    parser.files = {"file": ["file_data"]}

    # Create a mock tempfile
    mock_stream = Mock()
    mock_stream.closed = False
    mock_stream.name = "/tmp/test.tmp"
    parser._temp_files.append(mock_stream)

    with patch("os.path.exists", return_value=True):
        with patch("os.remove") as mock_remove:
            parser._cleanup()

            # Check that stream was closed
            mock_stream.close.assert_called_once()
            # Check that file was removed
            mock_remove.assert_called_once_with("/tmp/test.tmp")

    # Check that attributes were reset
    assert parser._cfield == {}
    assert parser._ccontent == b""
    assert parser._cstream is None
    assert parser.forms == {}
    assert parser.files == {}


def test_create_tempfile():
    """Test _create_tempfile method."""
    parser = MultipartParser(io.BytesIO(b""), "", 0)

    with patch("webspark.http.multipart.NamedTemporaryFile") as mock_tempfile:
        mock_file = Mock()
        mock_tempfile.return_value = mock_file
        result = parser._create_tempfile()

        mock_tempfile.assert_called_once_with(
            prefix="webspark-", suffix=".tmp", delete=False
        )
        assert result == mock_file
        assert mock_file in parser._temp_files


def test_on_body_end():
    """Test _on_body_end method."""
    parser = MultipartParser(io.BytesIO(b""), "", 0)
    parser._cfield = {"name": "test_field"}
    parser._ccontent = b"test content"
    parser._encoding = "utf-8"
    parser._encoding_errors = "strict"

    parser._on_body_end()

    assert "test_field" in parser.forms
    assert parser.forms["test_field"] == "test content"
    assert parser._cfield == {}
    assert parser._ccontent == b""


def test_on_fbody_end():
    """Test _on_fbody_end method."""
    parser = MultipartParser(io.BytesIO(b""), "", 0)

    # Create a mock tempfile
    mock_stream = Mock()
    mock_stream.name = "/tmp/test.tmp"
    parser._cstream = mock_stream

    parser._cfield = {
        "name": "test_file",
        "filename": "test.txt",
        "content_type": "text/plain",
    }

    parser._on_fbody_end()

    # Check that stream was rewound
    mock_stream.seek.assert_called_once_with(0)

    # Check that file was added to files dict
    assert "test_file" in parser.files
    assert isinstance(parser.files["test_file"], dict)
    file_info = parser.files["test_file"]
    assert file_info["filename"] == "test.txt"
    assert file_info["file"] == mock_stream
    assert file_info["content_type"] == "text/plain"

    # Check that attributes were reset
    assert parser._cfield == {}
    assert parser._cstream is None


def test_process_headers():
    """Test _process_headers method."""
    parser = MultipartParser(io.BytesIO(b""), "", 0)
    parser._delimiter = Mock()
    parser._delimiter.value = b"\r\n"
    parser._encoding = "utf-8"
    parser._encoding_errors = "strict"

    headers_data = b'Content-Disposition: form-data; name="test_field"\r\nContent-Type: text/plain\r\n\r\n'

    parser._process_headers(headers_data)

    assert parser._cfield["name"] == "test_field"
    assert parser._cfield["content_type"] == "text/plain"


def test_parse_simple_form_data():
    """Test parsing simple form data."""
    boundary = "----WebKitFormBoundary7MA4YWxkTrZu0gW"
    form_data = (
        f"------{boundary}\r\n"
        f'Content-Disposition: form-data; name="field1"\r\n\r\n'
        f"value1\r\n"
        f"------{boundary}--\r\n"
    ).encode()

    stream = io.BytesIO(form_data)
    content_type = f"multipart/form-data; boundary={boundary}"
    content_length = len(form_data)

    parser = MultipartParser(stream, content_type, content_length)
    forms, files = parser.parse()

    assert "field1" in forms
    assert "value1" in forms["field1"]
    assert files == {}


def test_parse_file_upload():
    """Test parsing file upload."""
    boundary = "----WebKitFormBoundary7MA4YWxkTrZu0gW"
    form_data = (
        f"------{boundary}\r\n"
        f'Content-Disposition: form-data; name="file"; filename="test.txt"\r\n'
        f"Content-Type: text/plain\r\n\r\n"
        f"test file content\r\n"
        f"------{boundary}--\r\n"
    ).encode()

    stream = io.BytesIO(form_data)
    content_type = f"multipart/form-data; boundary={boundary}"
    content_length = len(form_data)

    with patch("webspark.http.multipart.NamedTemporaryFile") as mock_tempfile:
        mock_file = Mock()
        mock_file.name = "/tmp/webspark-test.tmp"
        mock_file.write = Mock()
        mock_file.seek = Mock()
        mock_tempfile.return_value = mock_file

        parser = MultipartParser(stream, content_type, content_length)
        forms, files = parser.parse()

        assert forms == {}
        assert "file" in files
        assert isinstance(files["file"], dict)
        file_info = files["file"]
        assert file_info["filename"] == "test.txt"
        assert file_info["content_type"] == "text/plain"
        assert file_info["file"] == mock_file


def test_parse_max_body_size_exceeded():
    """Test parsing when max body size is exceeded."""
    stream = io.BytesIO(b"")
    content_type = "multipart/form-data; boundary=boundary"
    content_length = 2048
    max_body_size = 1024

    with pytest.raises(HTTPException) as exc_info:
        MultipartParser(
            stream, content_type, content_length, max_body_size=max_body_size
        )

    assert exc_info.value.status_code == 413


def test_parse_with_context_manager():
    """Test parsing using a context manager."""
    boundary = "----WebKitFormBoundary7MA4YWxkTrZu0gW"
    form_data = (
        f"------{boundary}\r\n"
        f'Content-Disposition: form-data; name="field1"\r\n\r\n'
        f"value1\r\n"
        f"------{boundary}--\r\n"
    ).encode()

    stream = io.BytesIO(form_data)
    content_type = f"multipart/form-data; boundary={boundary}"
    content_length = len(form_data)

    with patch.object(MultipartParser, "_cleanup") as mock_cleanup:
        with MultipartParser(stream, content_type, content_length) as parser:
            parser.parse()
        mock_cleanup.assert_called_once()


def test_parse_multiple_files_same_name():
    """Test parsing multiple files with the same name."""
    boundary = "----WebKitFormBoundary7MA4YWxkTrZu0gW"
    form_data = (
        f"------{boundary}\r\n"
        f'Content-Disposition: form-data; name="files"; filename="file1.txt"\r\n\r\n'
        f"content1\r\n"
        f"------{boundary}\r\n"
        f'Content-Disposition: form-data; name="files"; filename="file2.txt"\r\n\r\n'
        f"content2\r\n"
        f"------{boundary}--\r\n"
    ).encode()

    stream = io.BytesIO(form_data)
    content_type = f"multipart/form-data; boundary={boundary}"
    content_length = len(form_data)

    with patch("webspark.http.multipart.NamedTemporaryFile") as mock_tempfile:
        mock_file1 = Mock()
        mock_file2 = Mock()
        mock_tempfile.side_effect = [mock_file1, mock_file2]

        parser = MultipartParser(stream, content_type, content_length)
        _, files = parser.parse()

        assert len(files["files"]) == 2
        assert files["files"][0]["filename"] == "file1.txt"
        assert files["files"][1]["filename"] == "file2.txt"


def test_process_headers_malformed():
    """Test processing malformed headers."""
    parser = MultipartParser(io.BytesIO(b""), "", 0)
    parser._delimiter = Mock()
    parser._delimiter.value = b"\r\n"
    headers_data = (
        b"Content-Disposition: form-data; name=test_field\r\nmalformed-header\r\n"
    )
    parser._process_headers(headers_data)
    assert parser._cfield["name"] == "test_field"


def test_parse_malformed_part_headers():
    """Test parsing malformed part headers."""
    boundary = "----WebKitFormBoundary7MA4YWxkTrZu0gW"
    form_data = (
        f"------{boundary}\r\nContent-Disposition: form-data; name=field1".encode()
    )

    stream = io.BytesIO(form_data)
    content_type = f"multipart/form-data; boundary={boundary}"
    content_length = len(form_data)

    parser = MultipartParser(stream, content_type, content_length)
    with pytest.raises(HTTPException) as exc_info:
        parser.parse()
    assert exc_info.value.status_code == 400
    assert "malformed part headers" in str(exc_info.value)


def test_parse_part_header_terminator_not_found():
    """Test parsing when part header terminator is not found."""
    boundary = "----WebKitFormBoundary7MA4YWxkTrZu0gW"
    form_data = (
        f"------{boundary}\r\nContent-Disposition: form-data; name=field1\r\n".encode()
    )

    stream = io.BytesIO(form_data)
    content_type = f"multipart/form-data; boundary={boundary}"
    content_length = len(form_data)

    parser = MultipartParser(stream, content_type, content_length)
    with pytest.raises(HTTPException) as exc_info:
        parser.parse()
    assert exc_info.value.status_code == 400
    assert "malformed part headers" in str(exc_info.value)


def test_parse_closing_boundary_not_found():
    """Test parsing when closing boundary is not found."""
    boundary = "----WebKitFormBoundary7MA4YWxkTrZu0gW"
    form_data = (
        f"------{boundary}\r\n"
        f'Content-Disposition: form-data; name="field1"\r\n\r\n'
        f"value1"
    ).encode()

    stream = io.BytesIO(form_data)
    content_type = f"multipart/form-data; boundary={boundary}"
    content_length = len(form_data)

    parser = MultipartParser(stream, content_type, content_length)
    with pytest.raises(HTTPException) as exc_info:
        parser.parse()
    assert exc_info.value.status_code == 400
    assert "closing boundary not found" in str(exc_info.value)


def test_parse_body_terminator_not_found():
    """Test parsing when body terminator is not found."""
    boundary = "----WebKitFormBoundary7MA4YWxkTrZu0gW"
    form_data = (
        f"------{boundary}\r\n"
        f'Content-Disposition: form-data; name="field1"\r\n\r\n'
        f"value1\r\n"
        f"------{boundary}"
    ).encode()
    # Missing the final '--'

    stream = io.BytesIO(form_data)
    content_type = f"multipart/form-data; boundary={boundary}"
    content_length = len(form_data)

    parser = MultipartParser(stream, content_type, content_length)
    with pytest.raises(HTTPException) as exc_info:
        parser.parse()
    assert exc_info.value.status_code == 400
    assert "malformed part header" in str(exc_info.value)
