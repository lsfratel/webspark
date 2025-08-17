from typing import Any


class HTTPException(Exception):
    """Exception class for HTTP errors in WebSpark applications.

    This exception is used to signal HTTP errors that should be returned as HTTP responses.
    It carries both error details and an HTTP status code.

    Example:
        # Raise an HTTP exception with custom details
        raise HTTPException(
            details={"error": "Invalid input data"},
            status_code=400
        )

        # Raise with default status code (500)
        raise HTTPException("Something went wrong")

    Attributes:
        details: Error details that will be sent in the HTTP response.
        status_code: HTTP status code for the response (defaults to 500).
        DEFAULT_STATUS_CODE: Class attribute defining the default status code (500).
    """

    DEFAULT_STATUS_CODE = 500

    def __init__(self, details: Any, status_code: int = None):
        """Initialize the HTTPException.

        Args:
            details: Error details that will be sent in the response.
            status_code: HTTP status code (defaults to 500 if not provided).
        """
        super().__init__(details)
        self.details = details
        self.status_code = status_code or self.DEFAULT_STATUS_CODE
