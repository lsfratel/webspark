from __future__ import annotations

import re
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .fields import BaseField


def min_value_validator(min_value: int):
    """Create a validator that ensures a value is greater than or equal to min_value.

    Parameters:
        min_value: The minimum allowed numeric (or comparable) value.

    Returns:
        A callable validate(value, field) that returns the value or calls field.fail("min_value").
    """

    def validate(value, field: BaseField):
        if value < min_value:
            field.fail("min_value", min_value=min_value)
        return value

    return validate


def max_value_validator(max_value: int):
    """Create a validator that ensures a value is less than or equal to max_value.

    Parameters:
        max_value: The maximum allowed numeric (or comparable) value.

    Returns:
        A callable validate(value, field) that returns the value or calls field.fail("max_value").
    """

    def validate(value, field: BaseField):
        if value > max_value:
            field.fail("max_value", max_value=max_value)
        return value

    return validate


def min_length_validator(min_length: int):
    """Create a validator that ensures len(value) is at least min_length.

    Parameters:
        min_length: The minimum allowed length.

    Returns:
        A callable validate(value, field) that returns the value or calls field.fail("min_length").
    """

    def validate(value, field: BaseField):
        if len(value) < min_length:
            field.fail("min_length", min_length=min_length)
        return value

    return validate


def max_length_validator(max_length: int):
    """Create a validator that ensures len(value) is at most max_length.

    Parameters:
        max_length: The maximum allowed length.

    Returns:
        A callable validate(value, field) that returns the value or calls field.fail("max_length").
    """

    def validate(value, field: BaseField):
        if len(value) > max_length:
            field.fail("max_length", max_length=max_length)
        return value

    return validate


def regex_pattern_validator(pattern: str, flags: re.RegexFlag = 0, full_match=False):
    """Create a validator that enforces a regular expression on string values.

    Parameters:
        pattern: The regex pattern to compile.
        flags: Optional re flags to pass to re.compile.
        full_match: If True, require a full match; otherwise, allow a prefix match.

    Returns:
        A callable validate(value, field) that returns the value or calls field.fail("pattern").
    """
    compiled_pattern = re.compile(pattern, flags)

    def validate(value, field: BaseField):
        match_ = (
            compiled_pattern.fullmatch(value)
            if full_match
            else compiled_pattern.match(value)
        )
        if not match_:
            field.fail("pattern")
        return value

    return validate
