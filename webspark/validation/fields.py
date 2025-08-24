from __future__ import annotations

import re
import uuid
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
from enum import Enum
from typing import TYPE_CHECKING
from urllib.parse import urlparse

if TYPE_CHECKING:
    from collections.abc import Callable
    from typing import Any

    from .validation import Schema

from ..constants import UNDEFINED
from ..utils import HTTPException
from . import helpers


class BaseField:
    """Base class for all schema fields, handling validation, conversion, and representation."""

    default_error_messages = {
        "required": "This field is required.",
        "invalid": "Invalid value.",
        "null": "This field may not be null.",
    }

    @classmethod
    def get_default_error_messages(cls):
        """
        Collect and merge default error messages from the class hierarchy.

        Traverses the method resolution order (MRO) from base classes to the
        most-derived class, merging any 'default_error_messages' dicts found.
        Later classes in the MRO override keys from earlier ones.

        Returns:
            dict: Combined default error messages for this field class.
        """
        messages = {}
        for c in reversed(cls.__mro__):
            if hasattr(c, "default_error_messages"):
                messages.update(c.default_error_messages)
        return messages

    def __init__(
        self,
        required: bool = None,
        default: Any = None,
        source_name: str = None,
        validators: list[Callable] = None,
        nullable: bool = None,
        error_messages: dict[str, str] = None,
    ):
        self.required = required
        self.default = default
        self.source_name = source_name
        self.field_name: str = None
        self.validators = validators or []
        self.name: str = None
        self.nullable = nullable
        self.schema: Schema = None

        self.error_messages = self.get_default_error_messages()
        if error_messages:
            self.error_messages.update(error_messages)

    def to_python(self, value: Any) -> Any:
        return value

    def fail(self, key: str, **kwargs):
        msg = self.error_messages.get(key, "Invalid value.").format(**kwargs)
        raise HTTPException({self.name: [msg]}, status_code=400)

    def validate(self, value: Any, data: Any = None) -> Any:
        if value is UNDEFINED:
            if self.required:
                self.fail("required")
            return self.default

        if value is None:
            if self.nullable:
                return None
            self.fail("null")

        value = self.to_python(value)

        for validator in self.validators:
            value = validator(value, self)

        return value

    def to_representation(self, value: Any, obj: Any = None) -> Any:
        return value

    def bind(self, field_name: str):
        self.field_name = field_name
        self.name = self.source_name or field_name


class IntegerField(BaseField):
    """Field for integer values with optional min/max constraints."""

    default_error_messages = {
        "invalid": "Value must be an integer.",
        "min_value": "Value must be at least {min_value}.",
        "max_value": "Value must be at most {max_value}.",
    }

    def __init__(self, min_value: int = None, max_value: int = None, **kwargs):
        super().__init__(**kwargs)

        if min_value is not None:
            self.validators.append(helpers.min_value_validator(min_value))

        if max_value is not None:
            self.validators.append(helpers.max_value_validator(max_value))

    def to_python(self, value: Any) -> int:
        try:
            return int(value)
        except (ValueError, TypeError):
            self.fail("invalid")


class FloatField(BaseField):
    """Field for float values with optional min/max constraints."""

    default_error_messages = {
        "invalid": "Value must be a float.",
        "min_value": "Value must be at least {min_value}.",
        "max_value": "Value must be at most {max_value}.",
    }

    def __init__(self, min_value: float = None, max_value: float = None, **kwargs):
        super().__init__(**kwargs)

        if min_value is not None:
            self.validators.append(helpers.min_value_validator(min_value))

        if max_value is not None:
            self.validators.append(helpers.max_value_validator(max_value))

    def to_python(self, value: Any) -> float:
        try:
            return float(value)
        except (ValueError, TypeError):
            self.fail("invalid")


class StringField(BaseField):
    """Field for string values with optional length constraints."""

    default_error_messages = {
        "invalid": "Value must be a string.",
        "min_length": "Value must be at least {min_length} characters long.",
        "max_length": "Value must be at most {max_length} characters long.",
    }

    def __init__(self, min_length: int = None, max_length: int = None, **kwargs):
        super().__init__(**kwargs)

        if min_length is not None:
            self.validators.append(helpers.min_length_validator(min_length))

        if max_length is not None:
            self.validators.append(helpers.max_length_validator(max_length))

    def to_python(self, value: Any) -> str:
        if not isinstance(value, str):
            self.fail("invalid")
        return value


class BooleanField(BaseField):
    """Field for boolean values with support for common truthy/falsey strings."""

    default_error_messages = {
        "invalid": "Value must be boolean.",
    }

    _TRUE_VALUES = {"true", "1", "yes", "on"}
    _FALSE_VALUES = {"false", "0", "no", "off"}

    def to_python(self, value: Any) -> bool:
        if isinstance(value, bool):
            return value
        if isinstance(value, int | float):
            return bool(value)
        if isinstance(value, str):
            v = value.strip().lower()
            if v in self._TRUE_VALUES:
                return True
            if v in self._FALSE_VALUES:
                return False
        self.fail("invalid")


class ListField(BaseField):
    """Field representing a list with optional child field validation and size constraints."""

    default_error_messages = {
        "invalid": "Value must be a list.",
        "min_items": "Value must have at least {min_items} items.",
        "max_items": "Value must have at most {max_items} items.",
    }

    def __init__(
        self,
        child: BaseField = None,
        min_items: int = None,
        max_items: int = None,
        **kwargs,
    ):
        super().__init__(**kwargs)
        self.child = child
        self.min_items = min_items
        self.max_items = max_items

    def to_python(self, value: Any) -> list:
        if not isinstance(value, list):
            self.fail("invalid")
        return value

    def validate(self, value: Any, data: Any = None) -> list:
        value = super().validate(value, data)

        if self.min_items is not None and len(value) < self.min_items:
            self.fail("min_items", min_items=self.min_items)

        if self.max_items is not None and len(value) > self.max_items:
            self.fail("max_items", max_items=self.max_items)

        if self.child:
            validated = []
            errors = []
            for i, item in enumerate(value):
                try:
                    validated.append(self.child.validate(item, data))
                except HTTPException as e:
                    errors.append({i: e.details})
            if errors:
                raise HTTPException({self.name: errors}, status_code=400)
            return validated
        return value

    def to_representation(self, value: list, obj: Any = None) -> list:
        if self.child and value:
            return [self.child.to_representation(item, obj) for item in value]
        return value


class SerializerField(BaseField):
    """Nesting de schemas."""

    default_error_messages = {
        "invalid_list": "Expected a list of items.",
    }

    def __init__(
        self,
        serializer_class: type[Schema],
        many: bool = False,
        initkwargs: dict = None,
        **kwargs,
    ):
        super().__init__(**kwargs)
        self.serializer_class = serializer_class
        self.many = many
        self.initkwargs = initkwargs or {}

    def validate(self, value: Any, data: Any = None):
        if value is UNDEFINED:
            return super().validate(value, data)

        if value is None:
            return super().validate(value, data)

        if self.many:
            if not isinstance(value, list):
                self.fail("invalid_list")
            validated_data = []
            errors = {}
            for i, item in enumerate(value):
                try:
                    serializer = self.serializer_class(data=item, **self.initkwargs)
                    if serializer.is_valid():
                        validated_data.append(serializer.validated_data)
                    else:
                        errors[str(i)] = serializer.errors
                except HTTPException as e:
                    errors[str(i)] = e.details
            if errors:
                raise HTTPException({self.name: errors}, status_code=400)
            return validated_data

        serializer = self.serializer_class(data=value, **self.initkwargs)
        if not serializer.is_valid():
            raise HTTPException({self.name: serializer.errors}, status_code=400)
        return serializer.validated_data

    def to_representation(self, value: Any, obj: Any = None):
        if value is None:
            return [] if self.many else None
        if self.many and not isinstance(value, list):
            value = [value]
        return self.serializer_class.serialize(value, many=self.many, **self.initkwargs)


class DateTimeField(BaseField):
    """Field for ISO 8601 datetime values with optional auto_now/auto_now_add behavior."""

    default_error_messages = {
        "invalid": "Value must be a valid ISO 8601 datetime string.",
    }

    def __init__(self, auto_now: bool = False, auto_now_add: bool = False, **kwargs):
        super().__init__(**kwargs)
        self.auto_now = auto_now
        self.auto_now_add = auto_now_add

    def to_python(self, value: Any) -> datetime:
        if isinstance(value, datetime):
            return value
        try:
            return datetime.fromisoformat(value)
        except (ValueError, TypeError):
            self.fail("invalid")

    def validate(self, value: Any, data: Any = None) -> datetime:
        if self.auto_now or (self.auto_now_add and value is UNDEFINED):
            return datetime.now(tz=timezone.utc)

        if value is UNDEFINED:
            return super().validate(value, data)

        return super().validate(value, data)


class UUIDField(BaseField):
    """Field for UUID values."""

    default_error_messages = {
        "invalid": "Value must be a valid UUID.",
    }

    def to_python(self, value: Any) -> uuid.UUID:
        try:
            return uuid.UUID(str(value))
        except (ValueError, TypeError):
            self.fail("invalid")


class URLField(StringField):
    """Field for URL strings with optional scheme restrictions."""

    default_error_messages = {
        "invalid": "Value must be a valid URL.",
        "scheme": "Invalid URL scheme. Allowed schemes are: {schemes}.",
    }

    def __init__(self, schemes: list[str] = None, **kwargs):
        super().__init__(**kwargs)
        self.schemes = schemes

    def to_python(self, value: Any) -> str:
        value = super().to_python(value)
        parsed = urlparse(value)
        if not all([parsed.scheme, parsed.netloc]):
            self.fail("invalid")
        if self.schemes and parsed.scheme not in self.schemes:
            self.fail("scheme", schemes=self.schemes)
        return value


class EnumField(BaseField):
    """Field that restricts values to a fixed set (enum or list of choices)."""

    default_error_messages = {
        "invalid_choice": "Value must be one of: {choices}.",
    }

    def __init__(self, enum: type[Enum] | list[Any], **kwargs):
        super().__init__(**kwargs)
        if isinstance(enum, type) and issubclass(enum, Enum):
            self.enum_type = enum
            self.choices = [e.value for e in enum]
        else:
            self.enum_type = None
            self.choices = list(enum)

    def to_python(self, value: Any) -> Any:
        if value not in self.choices:
            self.fail("invalid_choice", choices=self.choices)
        return self.enum_type(value) if self.enum_type else value


class DecimalField(BaseField):
    """Field for Decimal values with optional precision and scale limits."""

    default_error_messages = {
        "invalid": "Value must be a valid decimal number.",
        "max_digits": "Must have at most {max_digits} digits.",
        "decimal_places": "Must have at most {decimal_places} decimal places.",
    }

    def __init__(self, max_digits: int = None, decimal_places: int = None, **kwargs):
        super().__init__(**kwargs)
        self.max_digits = max_digits
        self.decimal_places = decimal_places

    def to_python(self, value: Any) -> Decimal:
        try:
            return Decimal(str(value))
        except (InvalidOperation, TypeError):
            self.fail("invalid")

    def validate(self, value: Any, data: Any = None) -> Decimal:
        value = super().validate(value, data)
        if value is None:
            return value
        if self.max_digits is not None:
            if len(value.as_tuple().digits) > self.max_digits:
                self.fail("max_digits", max_digits=self.max_digits)
        if self.decimal_places is not None:
            if value.as_tuple().exponent < -self.decimal_places:
                self.fail("decimal_places", decimal_places=self.decimal_places)
        return value


class RegexField(StringField):
    """Field for strings validated against a regular expression pattern."""

    default_error_messages = {
        "pattern": "Value does not match the required pattern.",
    }

    def __init__(
        self, pattern: str, flags: re.RegexFlag = 0, full_match=False, **kwargs
    ):
        super().__init__(**kwargs)

        self.validators.append(
            helpers.regex_pattern_validator(pattern, flags, full_match)
        )


class EmailField(RegexField):
    """Field for email addresses."""

    default_error_messages = {
        "pattern": "Value must be a valid email address.",
    }

    def __init__(self, **kwargs):
        super().__init__(pattern=r"[^@]+@[^@]+\.[^@]+", full_match=True, **kwargs)


class MethodField(BaseField):
    """Field whose value is computed by calling a method on the schema."""

    default_error_messages = {
        "missing_method": "'{method}' is not a callable method on '{schema}'.",
    }

    def __init__(self, method_name: str, **kwargs):
        super().__init__(required=False, **kwargs)
        self.method_name = method_name

    def get_method(self) -> Callable:
        method = getattr(self.schema, self.method_name, None)
        if not callable(method):
            self.fail(
                "missing_method",
                method=self.method_name,
                schema=self.schema.__class__.__name__,
            )
        return method

    def validate(self, value: Any, data: Any = None) -> Any:
        method = self.get_method()
        computed = method(data)
        return super().validate(computed, data)

    def to_representation(self, value: Any, obj: Any = None) -> Any:
        method = self.get_method()
        computed = method(obj)
        return super().to_representation(computed, obj)
