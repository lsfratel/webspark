import re
import uuid
from collections.abc import Callable
from datetime import datetime
from decimal import Decimal, InvalidOperation
from enum import Enum
from typing import Any
from urllib.parse import urlparse

from ..utils import HTTPException

__all__ = [
    "ObjectSchema",
    "IntegerField",
    "FloatField",
    "StringField",
    "BooleanField",
    "ListField",
    "SerializerField",
    "DateTimeField",
    "UUIDField",
    "EmailField",
    "EnumField",
]


undefined = object()


class BaseField:
    """Base class for all schema fields.

    Attributes:
        required (bool): Whether the field is required. Defaults to True.
        default (Any): Default value for the field if not provided.
        source_name (str): Name of the field in the input data. If None, uses field name.
        validators (list[Callable]): List of validator functions to apply.
        nullable (bool): Whether the field can be None. Defaults to False.
        field_name (str): Name of the field in the schema.
        name (str): Name used when accessing data (source_name or field_name).
        schema (ObjectSchema): The schema to which the field belongs.
    """

    def __init__(
        self,
        required: bool = True,
        default: Any = None,
        source_name: str = None,
        validators: list[Callable] = None,
        nullable: bool = False,
    ):
        """Initialize a BaseField.

        Args:
            required: Whether the field is required. Defaults to True.
            default: Default value for the field if not provided.
            source_name: Name of the field in the input data. If None, uses field name.
            validators: List of validator functions to apply.
            nullable: Whether the field can be None. Defaults to False.
        """
        self.required = required
        self.default = default
        self.source_name = source_name
        self.field_name: str = None
        self.validators = validators or []
        self.name: str = None
        self.nullable = nullable
        self.schema: ObjectSchema = None

    def validate(self, value: Any, data: Any) -> Any:
        """Validate the field value.

        Args:
            value: The value to validate.
            data: The complete data containing all fields.

        Returns:
            The validated value.

        Raises:
            HTTPException: If validation fails.
        """
        if value is undefined and self.required:
            raise HTTPException(
                {self.name: ["This field is required."]}, status_code=400
            )

        if value is None and self.nullable:
            return value

        for validator in self.validators:
            value = validator(value)

        return value

    def to_representation(self, value: Any, obj: Any) -> Any:
        """Convert the field value to its serialized representation.

        Args:
            value: The value to convert.
            obj: The object instance.

        Returns:
            The converted value.
        """
        return value

    def bind(self, field_name: str):
        """Bind the field to a field name in a schema.

        Args:
            field_name: The name of the field in the schema.
        """
        self.field_name = field_name
        self.name = self.source_name or field_name


class ObjectSchemaMeta(type):
    """Metaclass for ObjectSchema that handles field declaration."""

    def __new__(cls, name, bases, attrs):
        """Create a new ObjectSchema class with declared fields.

        Args:
            name: The name of the class being created.
            bases: The base classes of the class being created.
            attrs: The attributes of the class being created.

        Returns:
            The newly created class.
        """
        declared_fields = {}
        for base in bases:
            if hasattr(base, "_declared_fields"):
                declared_fields.update(base._declared_fields)

        for key, value in attrs.items():
            if isinstance(value, BaseField):
                declared_fields[key] = value
                value.bind(key)

        attrs["_declared_fields"] = declared_fields
        return super().__new__(cls, name, bases, attrs)


class ObjectSchema(metaclass=ObjectSchemaMeta):
    """Base class for defining data schemas.

    Schemas are used to validate and serialize data. Fields are declared as class attributes,
    and the metaclass handles binding field names.

    Example:
        class UserSchema(ObjectSchema):
            name = StringField(required=True, max_length=100)
            age = IntegerField(min_value=0, max_value=150)

        # Validation
        schema = UserSchema(data={"name": "John", "age": 30})
        if schema.is_valid():
            validated_data = schema.validated_data

        # Serialization
        user = User(name="John", age=30)
        serialized = UserSchema.serialize(user)
    """

    def __init__(
        self,
        data: dict = None,
        instance: Any = None,
        context: dict = None,
    ):
        """Initialize an ObjectSchema.

        Args:
            data: The data to validate.
            instance: An instance to serialize.
            context: Additional context for validation/serialization.
        """
        self.initial_data = data or {}
        self.instance = instance
        self.context = context or {}
        self._validated_data = None
        self._errors = {}
        self.fields = self._declared_fields

    @property
    def serialized_data(self) -> dict:
        """Get the serialized representation of the instance."""
        return self.to_representation()

    @property
    def validated_data(self) -> dict:
        """Get the validated data after calling is_valid().

        Returns:
            The validated data.

        Raises:
            AttributeError: If is_valid() has not been called.
        """
        if self._validated_data is None:
            raise AttributeError(
                "You must call `.is_valid()` before accessing `validated_data`."
            )
        return self._validated_data

    @property
    def errors(self) -> dict:
        """Get validation errors."""
        return self._errors

    @classmethod
    def serialize(cls, obj: Any, many=False, **initkwargs):
        """Serialize an object or list of objects.

        Args:
            obj: The object or list of objects to serialize.
            many: Whether to serialize multiple objects.
            **initkwargs: Additional keyword arguments for schema initialization.

        Returns:
            The serialized data.
        """
        if many:
            return [cls(instance=o, **initkwargs).serialized_data for o in obj]
        return cls(instance=obj, **initkwargs).serialized_data

    def validate(self, data: Any):
        """Override this method to add custom validation.

        Args:
            data: The data to validate.

        Returns:
            The validated data.
        """
        return data

    def is_valid(self) -> bool:
        """Validate the initial data.

        Returns:
            True if the data is valid, False otherwise.
        """
        if self.initial_data is None:
            self._errors = {"non_field_errors": ["No data provided."]}
            return False
        validated_data = {}
        errors = {}

        try:
            initial_data = self.validate(self.initial_data)
        except HTTPException as e:
            self._errors = e.details
            self._validated_data = validated_data
            return False

        for field_name, field in self.fields.items():
            source_name = field.name
            raw_value = initial_data.get(source_name, undefined)

            if raw_value in (undefined, None):
                if field.default is not None:
                    raw_value = field.default

            try:
                field.schema = self
                validated_value = field.validate(raw_value, initial_data)
                validated_data[field_name] = validated_value
            except HTTPException as e:
                errors.update(e.details)

        if errors:
            self._errors = errors
            self._validated_data = validated_data
            return False

        self._validated_data = validated_data
        return True

    def to_representation(self, obj: Any = None) -> dict:
        """Convert an object to its serialized representation.

        Args:
            obj: The object to serialize. If None, uses self.instance.

        Returns:
            The serialized representation.
        """
        obj = obj or self.instance
        if obj is None:
            return {}

        return {
            field_name: field.to_representation(getattr(obj, field.name, None), obj)
            for field_name, field in self.fields.items()
        }


class IntegerField(BaseField):
    """Field for validating integer values.

    Args:
        min_value: Minimum allowed value.
        max_value: Maximum allowed value.
        **kwargs: Additional arguments passed to BaseField.
    """

    def __init__(self, min_value: int = None, max_value: int = None, **kwargs):
        super().__init__(**kwargs)
        self.min_value = min_value
        self.max_value = max_value

    def validate(self, value: Any, data: Any) -> int:
        value = super().validate(value, data)
        if value is None:
            return self.default if self.default is not None else None
        try:
            value = int(value)
        except (ValueError, TypeError) as e:
            raise HTTPException(
                {self.name: ["Value must be an integer."]}, status_code=400
            ) from e
        if self.min_value is not None and value < self.min_value:
            raise HTTPException(
                {self.name: [f"Must be at least {self.min_value}."]}, status_code=400
            )
        if self.max_value is not None and value > self.max_value:
            raise HTTPException(
                {self.name: [f"Must be at most {self.max_value}."]}, status_code=400
            )
        return value


class FloatField(BaseField):
    """Field for validating float values.

    Args:
        min_value: Minimum allowed value.
        max_value: Maximum allowed value.
        **kwargs: Additional arguments passed to BaseField.
    """

    def __init__(self, min_value: float = None, max_value: float = None, **kwargs):
        super().__init__(**kwargs)
        self.min_value = min_value
        self.max_value = max_value

    def validate(self, value: Any, data: Any) -> float:
        value = super().validate(value, data)
        if value is None:
            return self.default if self.default is not None else None
        try:
            value = float(value)
        except (ValueError, TypeError) as e:
            raise HTTPException(
                {self.name: ["Value must be a float."]}, status_code=400
            ) from e
        if self.min_value is not None and value < self.min_value:
            raise HTTPException(
                {self.name: [f"Must be at least {self.min_value}."]}, status_code=400
            )
        if self.max_value is not None and value > self.max_value:
            raise HTTPException(
                {self.name: [f"Must be at most {self.max_value}."]}, status_code=400
            )
        return value


class StringField(BaseField):
    """Field for validating string values.

    Args:
        min_length: Minimum length of the string.
        max_length: Maximum length of the string.
        **kwargs: Additional arguments passed to BaseField.
    """

    def __init__(self, min_length: int = None, max_length: int = None, **kwargs):
        super().__init__(**kwargs)
        self.min_length = min_length
        self.max_length = max_length

    def validate(self, value: Any, data: Any) -> str:
        value = super().validate(value, data)
        if value is None:
            return self.default if self.default is not None else None
        if not isinstance(value, str):
            raise HTTPException(
                {self.name: ["Value must be a string."]}, status_code=400
            )
        if self.min_length is not None and len(value) < self.min_length:
            raise HTTPException(
                {self.name: [f"Cannot be shorter than {self.min_length} characters."]},
                status_code=400,
            )
        if self.max_length is not None and len(value) > self.max_length:
            raise HTTPException(
                {self.name: [f"Cannot be longer than {self.max_length} characters."]},
                status_code=400,
            )
        return value


class BooleanField(BaseField):
    """Field for validating boolean values.

    Accepts string representations like "true", "1", "yes", "on" for True
    and "false", "0", "no", "off" for False.
    """

    _TRUE_VALUES = {"true", "1", "yes", "on"}
    _FALSE_VALUES = {"false", "0", "no", "off"}

    def validate(self, value: Any, data: Any) -> bool:
        value = super().validate(value, data)
        if value is None:
            return self.default if self.default is not None else None
        if isinstance(value, bool):
            return value
        if isinstance(value, str):
            value = value.lower()
            if value in self._TRUE_VALUES:
                return True
            if value in self._FALSE_VALUES:
                return False
        raise HTTPException({self.name: ["Value must be boolean."]}, status_code=400)


class ListField(BaseField):
    """Field for validating list values.

    Args:
        child: Field type for list items.
        min_items: Minimum number of items in the list.
        max_items: Maximum number of items in the list.
        **kwargs: Additional arguments passed to BaseField.
    """

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

    def validate(self, value: Any, data: Any) -> list:
        value = super().validate(value, data)
        if value is None:
            return []
        if not isinstance(value, list):
            raise HTTPException({self.name: ["Value must be a list."]}, status_code=400)
        if self.min_items is not None and len(value) < self.min_items:
            raise HTTPException(
                {self.name: [f"Must have at least {self.min_items} items."]},
                status_code=400,
            )
        if self.max_items is not None and len(value) > self.max_items:
            raise HTTPException(
                {self.name: [f"Must have at most {self.max_items} items."]},
                status_code=400,
            )
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

    def to_representation(self, value: list, obj: Any) -> list:
        if value is None:
            return None
        if self.child and value:
            return [self.child.to_representation(item, obj) for item in value]
        return value


class SerializerField(BaseField):
    """Field for nesting serializers within serializers.

    Args:
        serializer_class: The serializer class to use for validation/serialization.
        many: Whether the field represents a list of objects.
        initkwargs: Keyword arguments to pass to the serializer.
        **kwargs: Additional arguments passed to BaseField.
    """

    def __init__(
        self,
        serializer_class: type[ObjectSchema],
        many: bool = False,
        initkwargs: dict = None,
        **kwargs,
    ):
        super().__init__(**kwargs)
        self.serializer_class = serializer_class
        self.many = many
        self.initkwargs = initkwargs or {}

    def validate(self, value: Any, data: Any):
        if value is None and not self.required:
            return None

        if self.many:
            if not isinstance(value, list):
                raise HTTPException(
                    {self.name: ["Expected a list of items."]}, status_code=400
                )

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
        else:
            serializer = self.serializer_class(data=value, **self.initkwargs)
            if not serializer.is_valid():
                raise HTTPException({self.name: serializer.errors}, status_code=400)
            return serializer.validated_data

    def to_representation(self, value: Any, obj: Any):
        if value is None:
            return [] if self.many else None

        if self.many:
            if not isinstance(value, list):
                value = [value]

        return self.serializer_class.serialize(value, many=self.many, **self.initkwargs)


class DateTimeField(BaseField):
    """Field for validating datetime values.

    Args:
        auto_now: Whether to set the value to now every time the object is saved.
        auto_now_add: Whether to set the value to now when the object is first created.
        **kwargs: Additional arguments passed to BaseField.
    """

    def __init__(self, auto_now: bool = False, auto_now_add: bool = False, **kwargs):
        super().__init__(**kwargs)
        self.auto_now = auto_now
        self.auto_now_add = auto_now_add

    def validate(self, value: Any, data: Any) -> datetime:
        if self.auto_now or self.auto_now_add:
            return datetime.now()
        value = super().validate(value, data)
        if value is None:
            return self.default
        if isinstance(value, datetime):
            return value
        try:
            return datetime.fromisoformat(value)
        except (ValueError, TypeError) as e:
            raise HTTPException(
                {self.name: ["Value must be a valid ISO 8601 datetime string."]},
                status_code=400,
            ) from e


class UUIDField(BaseField):
    """Field for validating UUID values."""

    def validate(self, value: Any, data: Any) -> uuid.UUID:
        value = super().validate(value, data)
        if value is None:
            return self.default
        try:
            return uuid.UUID(str(value))
        except (ValueError, TypeError) as e:
            raise HTTPException(
                {self.name: ["Value must be a valid UUID."]}, status_code=400
            ) from e


class URLField(StringField):
    """Field for validating URL values.

    Args:
        schemes: List of allowed URL schemes (e.g., ['http', 'https']).
        **kwargs: Additional arguments passed to StringField.
    """

    def __init__(self, schemes: list[str] = None, **kwargs):
        super().__init__(**kwargs)
        self.schemes = schemes

    def validate(self, value: Any, data: Any) -> str:
        value = super().validate(value, data)
        if value is None:
            return self.default
        parsed = urlparse(value)
        if not all([parsed.scheme, parsed.netloc]):
            raise HTTPException(
                {self.name: ["Value must be a valid URL."]}, status_code=400
            )
        if self.schemes and parsed.scheme not in self.schemes:
            raise HTTPException(
                {
                    self.name: [
                        f"Invalid URL scheme. Allowed schemes are: {self.schemes}."
                    ]
                },
                status_code=400,
            )
        return value


class EnumField(BaseField):
    """Field for validating enum values.

    Args:
        enum: An Enum class or a list of valid values.
        **kwargs: Additional arguments passed to BaseField.
    """

    def __init__(self, enum: type[Enum] | list[Any], **kwargs):
        super().__init__(**kwargs)
        if isinstance(enum, type) and issubclass(enum, Enum):
            self.enum_type = enum
            self.choices = [e.value for e in enum]
        else:
            self.enum_type = None
            self.choices = enum

    def validate(self, value: Any, data: Any) -> Any:
        value = super().validate(value, data)
        if value is None:
            return self.default
        if value not in self.choices:
            raise HTTPException(
                {self.name: [f"Value must be one of: {self.choices}."]}, status_code=400
            )
        if self.enum_type:
            return self.enum_type(value)
        return value


class DecimalField(BaseField):
    """Field for validating decimal values.

    Args:
        max_digits: Maximum number of digits.
        decimal_places: Maximum number of decimal places.
        **kwargs: Additional arguments passed to BaseField.
    """

    def __init__(self, max_digits: int = None, decimal_places: int = None, **kwargs):
        super().__init__(**kwargs)
        self.max_digits = max_digits
        self.decimal_places = decimal_places

    def validate(self, value: Any, data: Any) -> Decimal:
        value = super().validate(value, data)
        if value is None:
            return self.default
        try:
            value = Decimal(str(value))
        except (InvalidOperation, TypeError) as e:
            raise HTTPException(
                {self.name: ["Value must be a valid decimal number."]}, status_code=400
            ) from e
        if self.max_digits is not None:
            if len(value.as_tuple().digits) > self.max_digits:
                raise HTTPException(
                    {self.name: [f"Must have at most {self.max_digits} digits."]},
                    status_code=400,
                )
        if self.decimal_places is not None:
            if value.as_tuple().exponent < -self.decimal_places:
                raise HTTPException(
                    {
                        self.name: [
                            f"Must have at most {self.decimal_places} decimal places."
                        ]
                    },
                    status_code=400,
                )
        return value


class RegexField(StringField):
    """Field for validating string values against a regular expression.

    Args:
        pattern: The regular expression pattern to match.
        **kwargs: Additional arguments passed to StringField.
    """

    def __init__(self, pattern: str, **kwargs):
        super().__init__(**kwargs)
        self.pattern = re.compile(pattern)

    def validate(self, value: Any, data: Any) -> str:
        value = super().validate(value, data)
        if value is None:
            return self.default
        if not self.pattern.fullmatch(value):
            raise HTTPException(
                {self.name: ["Value does not match the required pattern."]},
                status_code=400,
            )
        return value


class EmailField(StringField):
    """Field for validating email addresses."""

    EMAIL_REGEX = re.compile(r"[^@]+@[^@]+\.[^@]+")

    def validate(self, value: Any, data: Any) -> str:
        value = super().validate(value, data)
        if value is None:
            return self.default
        if not self.EMAIL_REGEX.fullmatch(value):
            raise HTTPException(
                {self.name: ["Value must be a valid email address."]}, status_code=400
            )
        return value


class MethodField(BaseField):
    """Field for defining a method that will be called to represent the value.

    Args:
        method_name: The name of the method to call for representation.
        **kwargs: Additional arguments passed to StringField.
    """

    def __init__(self, method_name: str, **kwargs):
        super().__init__(**kwargs)
        self.method_name = method_name

    def get_method(self) -> Callable:
        method = getattr(self.schema, self.method_name, None)

        if not callable(method):
            raise AttributeError(
                f"'{self.schema.__class__.__name__}' object has no callable method '{self.method_name}'."
            )

        return method

    def validate(self, value: Any, data: Any) -> Any:
        method = self.get_method()
        value = method(data)
        return super().validate(value, data)

    def to_representation(self, value: Any, obj: Any) -> Any:
        method = self.get_method()
        value = method(obj)
        return super().to_representation(value, obj)
