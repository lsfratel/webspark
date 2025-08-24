from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from typing import Any

from ..constants import UNDEFINED
from ..utils import HTTPException
from .fields import BaseField


class SchemaMeta(type):
    """Metaclass for Schema that handles field declaration."""

    def __new__(cls, name, bases, attrs):
        """Create a new Schema class with declared fields.

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


class Schema(metaclass=SchemaMeta):
    """Base class for defining data schemas.

    Schemas are used to validate data. Fields are declared as class attributes,
    and the metaclass handles binding field names.

    Example:
        class UserSchema(Schema):
            name = StringField(required=True, max_length=100)
            age = IntegerField(min_value=0, max_value=150)

        # Validation
        schema = UserSchema(data={"name": "John", "age": 30})
        if schema.is_valid():
            validated_data = schema.validated_data
    """

    def __init__(
        self,
        data: dict = None,
        context: dict = None,
    ):
        """Initialize a Schema.

        Args:
            data: The data to validate.
            context: Additional context for validation.
        """
        self.initial_data = data or {}
        self.context = context or {}
        self._validated_data = None
        self._errors = {}
        self.fields: dict[str, BaseField] = self._declared_fields

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
            initial_data = self.validate(
                self.initial_data if self.initial_data is not None else {}
            )
        except HTTPException as e:
            self._errors = e.details
            self._validated_data = validated_data
            return False

        for field_name, field in self.fields.items():
            source_name = field.name
            raw_value = initial_data.get(source_name, UNDEFINED)

            if raw_value in (UNDEFINED, None):
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
