from webspark.utils.exceptions import HTTPException


def test_http_exception_default_status_code():
    exc = HTTPException("An error occurred")
    assert exc.details == "An error occurred"
    assert exc.status_code == 500


def test_http_exception_custom_status_code():
    exc = HTTPException("Not Found", status_code=404)
    assert exc.details == "Not Found"
    assert exc.status_code == 404


def test_http_exception_with_dict_details():
    details = {"error": "Invalid data", "field": "email"}
    exc = HTTPException(details, status_code=400)
    assert exc.details == details
    assert exc.status_code == 400
