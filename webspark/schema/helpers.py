from __future__ import annotations

import re
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .fields import BaseField


def min_value_validator(min_value: int):
    def validate(value, field: BaseField):
        if value < min_value:
            field.fail("min_value", min_value=min_value)
        return value

    return validate


def max_value_validator(max_value: int):
    def validate(value, field: BaseField):
        if value > max_value:
            field.fail("max_value", max_value=max_value)
        return value

    return validate


def min_length_validator(min_length: int):
    def validate(value, field: BaseField):
        if len(value) < min_length:
            field.fail("min_length", min_length=min_length)
        return value

    return validate


def max_length_validator(max_length: int):
    def validate(value, field: BaseField):
        if len(value) > max_length:
            field.fail("max_length", max_length=max_length)
        return value

    return validate


def regex_pattern_validator(pattern: str, flags: re.RegexFlag = 0, full_match=False):
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
