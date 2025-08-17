import uuid
from datetime import datetime
from decimal import Decimal
from enum import Enum
from unittest.mock import Mock

import pytest

from webspark.core.schema import (
    BaseField,
    BooleanField,
    DateTimeField,
    DecimalField,
    EmailField,
    EnumField,
    FloatField,
    IntegerField,
    ListField,
    ObjectSchema,
    RegexField,
    SerializerField,
    StringField,
    URLField,
    UUIDField,
    undefined,
)
from webspark.utils import HTTPException


def test_base_field_initialization():
    """Test BaseField initialization."""

    def validator_func(x):
        return x

    field = BaseField(
        required=True,
        default="default_value",
        source_name="source",
        validators=[validator_func],
        nullable=True,
    )

    assert field.required is True
    assert field.default == "default_value"
    assert field.source_name == "source"
    assert field.validators == [validator_func]
    assert field.nullable is True
    assert field.field_name is None
    assert field.name is None


def test_base_field_bind():
    """Test BaseField bind method."""
    field = BaseField(source_name="source")
    field.bind("field_name")

    assert field.field_name == "field_name"
    assert field.name == "source"

    # Test without source_name
    field2 = BaseField()
    field2.bind("field_name")
    assert field2.name == "field_name"


def test_base_field_validate_required():
    """Test BaseField validate with required field."""
    field = BaseField(required=True)
    field.name = "test_field"

    with pytest.raises(HTTPException) as exc_info:
        field.validate(undefined)

    assert exc_info.value.status_code == 400
    assert "test_field" in exc_info.value.details
    assert "This field is required." in exc_info.value.details["test_field"]


def test_base_field_validate_nullable():
    """Test BaseField validate with nullable field."""
    field = BaseField(required=True, nullable=True)
    result = field.validate(None)
    assert result is None


def test_base_field_validate_with_validators():
    """Test BaseField validate with custom validators."""

    def validator(value):
        if value != "valid":
            raise ValueError("Invalid value")
        return value

    field = BaseField(validators=[validator])
    result = field.validate("valid")
    assert result == "valid"

    with pytest.raises(ValueError):
        field.validate("invalid")


def test_base_field_to_representation():
    """Test BaseField to_representation method."""
    field = BaseField()
    value = "test_value"
    result = field.to_representation(value)
    assert result == value


def test_object_schema_meta():
    """Test ObjectSchemaMeta metaclass."""

    class TestSchema(ObjectSchema):
        field1 = StringField()
        field2 = IntegerField()

    assert hasattr(TestSchema, "_declared_fields")
    assert "field1" in TestSchema._declared_fields
    assert "field2" in TestSchema._declared_fields
    assert isinstance(TestSchema._declared_fields["field1"], StringField)
    assert isinstance(TestSchema._declared_fields["field2"], IntegerField)


def test_object_schema_inheritance():
    """Test ObjectSchema inheritance."""

    class BaseSchema(ObjectSchema):
        base_field = StringField()

    class ChildSchema(BaseSchema):
        child_field = IntegerField()

    assert "base_field" in ChildSchema._declared_fields
    assert "child_field" in ChildSchema._declared_fields


def test_object_schema_initialization():
    """Test ObjectSchema initialization."""

    class TestSchema(ObjectSchema):
        pass

    schema = TestSchema(
        data={"key": "value"}, instance="instance", context={"ctx": "test"}
    )

    assert schema.initial_data == {"key": "value"}
    assert schema.instance == "instance"
    assert schema.context == {"ctx": "test"}
    assert schema._validated_data is None
    assert schema._errors == {}
    assert schema.fields == {}


def test_object_schema_properties():
    """Test ObjectSchema properties."""

    class TestSchema(ObjectSchema):
        pass

    schema = TestSchema()

    # Test errors property
    assert schema.errors == {}

    # Test validated_data property before validation
    with pytest.raises(
        AttributeError,
        match="You must call `.is_valid\\(\\)` before accessing `validated_data`\\.",
    ):
        _ = schema.validated_data

    # Test serialized_data property
    assert schema.serialized_data == {}


def test_object_schema_serialize():
    """Test ObjectSchema serialize classmethod."""

    class TestSchema(ObjectSchema):
        name = StringField()

        def to_representation(self, obj=None):
            obj = obj or self.instance
            return {"name": getattr(obj, "name", None)}

    # Test single object
    class TestObj:
        def __init__(self, name):
            self.name = name

    obj = TestObj("test")
    result = TestSchema.serialize(obj)
    assert result == {"name": "test"}

    # Test many objects
    objs = [TestObj("test1"), TestObj("test2")]
    result = TestSchema.serialize(objs, many=True)
    assert result == [{"name": "test1"}, {"name": "test2"}]


def test_object_schema_validate():
    """Test ObjectSchema validate method."""

    class TestSchema(ObjectSchema):
        pass

    schema = TestSchema()
    data = {"key": "value"}
    result = schema.validate(data)
    assert result == data


def test_object_schema_is_valid_no_data():
    """Test ObjectSchema is_valid with no data."""

    class TestSchema(ObjectSchema):
        pass

    schema = TestSchema(data=None)
    result = schema.is_valid()

    # When data is None, initial_data becomes {} not None, so it's valid
    assert result is True
    assert schema.errors == {}


def test_object_schema_is_valid_with_field_errors():
    """Test ObjectSchema is_valid with field errors."""

    class TestSchema(ObjectSchema):
        required_field = StringField(required=True)

    schema = TestSchema(data={})
    result = schema.is_valid()

    assert result is False
    assert "required_field" in schema.errors
    assert "This field is required." in schema.errors["required_field"]


def test_object_schema_is_valid_with_custom_validation_error():
    """Test ObjectSchema is_valid with custom validation error."""

    class TestSchema(ObjectSchema):
        def validate(self, data):
            raise HTTPException({"custom": ["Custom error"]}, status_code=400)

    schema = TestSchema(data={"key": "value"})
    result = schema.is_valid()

    assert result is False
    assert schema.errors == {"custom": ["Custom error"]}


def test_object_schema_is_valid_success():
    """Test ObjectSchema is_valid success case."""

    class TestSchema(ObjectSchema):
        name = StringField()
        age = IntegerField()

    schema = TestSchema(data={"name": "John", "age": 30})
    result = schema.is_valid()

    assert result is True
    assert schema.errors == {}
    assert schema.validated_data == {"name": "John", "age": 30}


def test_object_schema_to_representation():
    """Test ObjectSchema to_representation method."""

    class TestSchema(ObjectSchema):
        name = StringField()

    class TestObj:
        def __init__(self, name):
            self.name = name

    obj = TestObj("John")
    schema = TestSchema(instance=obj)
    result = schema.to_representation()

    assert result == {"name": "John"}


def test_object_schema_to_representation_no_instance():
    """Test ObjectSchema to_representation with no instance."""

    class TestSchema(ObjectSchema):
        name = StringField()

    schema = TestSchema()
    result = schema.to_representation()

    assert result == {}


def test_integer_field_validate():
    """Test IntegerField validate method."""
    field = IntegerField()
    field.name = "age"

    result = field.validate("30")
    assert result == 30

    result = field.validate(30)
    assert result == 30


def test_integer_field_validate_invalid():
    """Test IntegerField validate with invalid value."""
    field = IntegerField()
    field.name = "age"

    with pytest.raises(HTTPException) as exc_info:
        field.validate("invalid")

    assert exc_info.value.status_code == 400
    assert "age" in exc_info.value.details
    assert "Value must be an integer" in exc_info.value.details["age"][0]


def test_integer_field_validate_none():
    """Test IntegerField validate with None value."""
    field = IntegerField(required=False)
    result = field.validate(None)
    assert result is None


def test_integer_field_validate_with_default():
    """Test IntegerField validate with default value."""
    field = IntegerField(default=18)
    result = field.validate(None)
    assert result == 18


def test_integer_field_validate_min_value():
    """Test IntegerField validate with min_value."""
    field = IntegerField(min_value=18)
    field.name = "age"

    result = field.validate(25)
    assert result == 25

    with pytest.raises(HTTPException) as exc_info:
        field.validate(10)

    assert "Must be at least 18" in exc_info.value.details["age"][0]


def test_integer_field_validate_max_value():
    """Test IntegerField validate with max_value."""
    field = IntegerField(max_value=100)
    field.name = "age"

    result = field.validate(50)
    assert result == 50

    with pytest.raises(HTTPException) as exc_info:
        field.validate(150)

    assert "Must be at most 100" in exc_info.value.details["age"][0]


def test_float_field_validate():
    """Test FloatField validate method."""
    field = FloatField()
    field.name = "price"

    result = field.validate("30.5")
    assert result == 30.5

    result = field.validate(30.5)
    assert result == 30.5


def test_float_field_validate_invalid():
    """Test FloatField validate with invalid value."""
    field = FloatField()
    field.name = "price"

    with pytest.raises(HTTPException) as exc_info:
        field.validate("invalid")

    assert exc_info.value.status_code == 400
    assert "price" in exc_info.value.details
    assert "Value must be a float" in exc_info.value.details["price"][0]


def test_float_field_validate_min_value():
    """Test FloatField validate with min_value."""
    field = FloatField(min_value=0.0)
    field.name = "price"

    result = field.validate(10.5)
    assert result == 10.5

    with pytest.raises(HTTPException) as exc_info:
        field.validate(-5.0)

    assert "Must be at least 0.0" in exc_info.value.details["price"][0]


def test_float_field_validate_max_value():
    """Test FloatField validate with max_value."""
    field = FloatField(max_value=100.0)
    field.name = "price"

    result = field.validate(50.0)
    assert result == 50.0

    with pytest.raises(HTTPException) as exc_info:
        field.validate(150.0)

    assert "Must be at most 100.0" in exc_info.value.details["price"][0]


def test_string_field_validate():
    """Test StringField validate method."""
    field = StringField()
    field.name = "name"

    result = field.validate("John")
    assert result == "John"


def test_string_field_validate_invalid():
    """Test StringField validate with invalid value."""
    field = StringField()
    field.name = "name"

    with pytest.raises(HTTPException) as exc_info:
        field.validate(123)

    assert exc_info.value.status_code == 400
    assert "name" in exc_info.value.details
    assert "Value must be a string" in exc_info.value.details["name"][0]


def test_string_field_validate_min_length():
    """Test StringField validate with min_length."""
    field = StringField(min_length=3)
    field.name = "name"

    result = field.validate("John")
    assert result == "John"

    with pytest.raises(HTTPException) as exc_info:
        field.validate("Jo")

    assert "Cannot be shorter than 3 characters" in exc_info.value.details["name"][0]


def test_string_field_validate_max_length():
    """Test StringField validate with max_length."""
    field = StringField(max_length=5)
    field.name = "name"

    result = field.validate("John")
    assert result == "John"

    with pytest.raises(HTTPException) as exc_info:
        field.validate("John Doe")

    assert "Cannot be longer than 5 characters" in exc_info.value.details["name"][0]


def test_boolean_field_validate():
    """Test BooleanField validate method."""
    field = BooleanField()
    field.name = "active"

    # Test boolean values
    assert field.validate(True) is True
    assert field.validate(False) is False

    # Test string values
    assert field.validate("true") is True
    assert field.validate("false") is False
    assert field.validate("1") is True
    assert field.validate("0") is False
    assert field.validate("yes") is True
    assert field.validate("no") is False
    assert field.validate("on") is True
    assert field.validate("off") is False


def test_boolean_field_validate_invalid():
    """Test BooleanField validate with invalid value."""
    field = BooleanField()
    field.name = "active"

    with pytest.raises(HTTPException) as exc_info:
        field.validate("invalid")

    assert exc_info.value.status_code == 400
    assert "active" in exc_info.value.details
    assert "Value must be boolean" in exc_info.value.details["active"][0]


def test_boolean_field_validate_none():
    """Test BooleanField validate with None value."""
    field = BooleanField(required=False)
    result = field.validate(None)
    assert result is None


def test_list_field_validate():
    """Test ListField validate method."""
    field = ListField()
    field.name = "items"

    result = field.validate([1, 2, 3])
    assert result == [1, 2, 3]


def test_list_field_validate_invalid():
    """Test ListField validate with invalid value."""
    field = ListField()
    field.name = "items"

    with pytest.raises(HTTPException) as exc_info:
        field.validate("not a list")

    assert exc_info.value.status_code == 400
    assert "items" in exc_info.value.details
    assert "Value must be a list" in exc_info.value.details["items"][0]


def test_list_field_validate_none():
    """Test ListField validate with None value."""
    field = ListField(required=False)
    result = field.validate(None)
    assert result == []


def test_list_field_validate_min_items():
    """Test ListField validate with min_items."""
    field = ListField(min_items=2)
    field.name = "items"

    result = field.validate([1, 2, 3])
    assert result == [1, 2, 3]

    with pytest.raises(HTTPException) as exc_info:
        field.validate([1])

    assert "Must have at least 2 items" in exc_info.value.details["items"][0]


def test_list_field_validate_max_items():
    """Test ListField validate with max_items."""
    field = ListField(max_items=3)
    field.name = "items"

    result = field.validate([1, 2])
    assert result == [1, 2]

    with pytest.raises(HTTPException) as exc_info:
        field.validate([1, 2, 3, 4])

    assert "Must have at most 3 items" in exc_info.value.details["items"][0]


def test_list_field_validate_with_child_field():
    """Test ListField validate with child field."""
    field = ListField(child=IntegerField())
    field.name = "numbers"

    result = field.validate(["1", "2", "3"])
    assert result == [1, 2, 3]


def test_list_field_validate_with_child_field_errors():
    """Test ListField validate with child field errors."""
    field = ListField(child=IntegerField())
    field.name = "numbers"

    with pytest.raises(HTTPException) as exc_info:
        field.validate(["1", "invalid", "3"])

    assert exc_info.value.status_code == 400
    assert "numbers" in exc_info.value.details


def test_list_field_to_representation():
    """Test ListField to_representation method."""
    field = ListField()
    result = field.to_representation([1, 2, 3])
    assert result == [1, 2, 3]


def test_list_field_to_representation_with_child():
    """Test ListField to_representation with child field."""
    child_field = Mock()
    child_field.to_representation.return_value = "mocked"
    field = ListField(child=child_field)

    result = field.to_representation([1, 2, 3])
    assert result == ["mocked", "mocked", "mocked"]
    assert child_field.to_representation.call_count == 3


def test_list_field_to_representation_none():
    """Test ListField to_representation with None value."""
    field = ListField()
    result = field.to_representation(None)
    assert result is None


def test_datetime_field_validate():
    """Test DateTimeField validate method."""
    field = DateTimeField()
    field.name = "created_at"

    dt_str = "2023-01-01T12:00:00"
    result = field.validate(dt_str)
    assert isinstance(result, datetime)
    assert result.isoformat() == "2023-01-01T12:00:00"


def test_datetime_field_validate_datetime_object():
    """Test DateTimeField validate with datetime object."""
    field = DateTimeField()
    dt = datetime(2023, 1, 1, 12, 0, 0)
    result = field.validate(dt)
    assert result is dt


def test_datetime_field_validate_invalid():
    """Test DateTimeField validate with invalid value."""
    field = DateTimeField()
    field.name = "created_at"

    with pytest.raises(HTTPException) as exc_info:
        field.validate("invalid")

    assert exc_info.value.status_code == 400
    assert "created_at" in exc_info.value.details
    assert (
        "Value must be a valid ISO 8601 datetime string"
        in exc_info.value.details["created_at"][0]
    )


def test_datetime_field_auto_now():
    """Test DateTimeField with auto_now."""
    field = DateTimeField(auto_now=True)
    result = field.validate("2023-01-01T12:00:00")
    assert isinstance(result, datetime)
    # Should return current time, not the provided value


def test_uuid_field_validate():
    """Test UUIDField validate method."""
    field = UUIDField()
    field.name = "id"

    uuid_str = "550e8400-e29b-41d4-a716-446655440000"
    result = field.validate(uuid_str)
    assert isinstance(result, uuid.UUID)
    assert str(result) == uuid_str


def test_uuid_field_validate_invalid():
    """Test UUIDField validate with invalid value."""
    field = UUIDField()
    field.name = "id"

    with pytest.raises(HTTPException) as exc_info:
        field.validate("invalid")

    assert exc_info.value.status_code == 400
    assert "id" in exc_info.value.details
    assert "Value must be a valid UUID" in exc_info.value.details["id"][0]


def test_email_field_validate():
    """Test EmailField validate method."""
    field = EmailField()
    field.name = "email"

    result = field.validate("test@example.com")
    assert result == "test@example.com"


def test_email_field_validate_invalid():
    """Test EmailField validate with invalid value."""
    field = EmailField()
    field.name = "email"

    with pytest.raises(HTTPException) as exc_info:
        field.validate("invalid")

    assert exc_info.value.status_code == 400
    assert "email" in exc_info.value.details
    assert "Value must be a valid email address" in exc_info.value.details["email"][0]


def test_url_field_validate():
    """Test URLField validate method."""
    field = URLField()
    field.name = "website"

    result = field.validate("https://example.com")
    assert result == "https://example.com"


def test_url_field_validate_invalid():
    """Test URLField validate with invalid value."""
    field = URLField()
    field.name = "website"

    with pytest.raises(HTTPException) as exc_info:
        field.validate("invalid")

    assert exc_info.value.status_code == 400
    assert "website" in exc_info.value.details
    assert "Value must be a valid URL" in exc_info.value.details["website"][0]


def test_url_field_validate_with_schemes():
    """Test URLField validate with specific schemes."""
    field = URLField(schemes=["https"])
    field.name = "website"

    result = field.validate("https://example.com")
    assert result == "https://example.com"

    with pytest.raises(HTTPException) as exc_info:
        field.validate("http://example.com")

    assert "Invalid URL scheme" in exc_info.value.details["website"][0]


def test_enum_field_validate_with_enum():
    """Test EnumField validate with Enum type."""

    class Color(Enum):
        RED = "red"
        GREEN = "green"
        BLUE = "blue"

    field = EnumField(Color)
    field.name = "color"

    result = field.validate("red")
    assert result == Color.RED

    # Test with enum value (should fail as it's not in choices)
    with pytest.raises(HTTPException):
        field.validate(Color.GREEN)


def test_enum_field_validate_with_list():
    """Test EnumField validate with list of choices."""
    field = EnumField(["red", "green", "blue"])
    field.name = "color"

    result = field.validate("red")
    assert result == "red"


def test_enum_field_validate_invalid():
    """Test EnumField validate with invalid value."""
    field = EnumField(["red", "green", "blue"])
    field.name = "color"

    with pytest.raises(HTTPException) as exc_info:
        field.validate("yellow")

    assert exc_info.value.status_code == 400
    assert "color" in exc_info.value.details
    assert "Value must be one of" in exc_info.value.details["color"][0]


def test_decimal_field_validate():
    """Test DecimalField validate method."""
    field = DecimalField()
    field.name = "price"

    result = field.validate("10.50")
    assert isinstance(result, Decimal)
    assert result == Decimal("10.50")


def test_decimal_field_validate_invalid():
    """Test DecimalField validate with invalid value."""
    field = DecimalField()
    field.name = "price"

    with pytest.raises(HTTPException) as exc_info:
        field.validate("invalid")

    assert exc_info.value.status_code == 400
    assert "price" in exc_info.value.details
    assert "Value must be a valid decimal number" in exc_info.value.details["price"][0]


def test_decimal_field_validate_max_digits():
    """Test DecimalField validate with max_digits."""
    field = DecimalField(max_digits=5)
    field.name = "price"

    result = field.validate("123.45")
    assert result == Decimal("123.45")

    with pytest.raises(HTTPException) as exc_info:
        field.validate("12345.67")

    assert "Must have at most 5 digits" in exc_info.value.details["price"][0]


def test_decimal_field_validate_decimal_places():
    """Test DecimalField validate with decimal_places."""
    field = DecimalField(decimal_places=2)
    field.name = "price"

    result = field.validate("123.45")
    assert result == Decimal("123.45")

    with pytest.raises(HTTPException) as exc_info:
        field.validate("123.456")

    assert "Must have at most 2 decimal places" in exc_info.value.details["price"][0]


def test_regex_field_validate():
    """Test RegexField validate method."""
    field = RegexField(r"^\d{3}-\d{3}-\d{4}$")
    field.name = "phone"

    result = field.validate("123-456-7890")
    assert result == "123-456-7890"


def test_regex_field_validate_invalid():
    """Test RegexField validate with invalid value."""
    field = RegexField(r"^\d{3}-\d{3}-\d{4}$")
    field.name = "phone"

    with pytest.raises(HTTPException) as exc_info:
        field.validate("invalid")

    assert exc_info.value.status_code == 400
    assert "phone" in exc_info.value.details
    assert (
        "Value does not match the required pattern"
        in exc_info.value.details["phone"][0]
    )


def test_serializer_field_validate_single():
    """Test SerializerField validate with single object."""

    class NestedSchema(ObjectSchema):
        name = StringField()

    field = SerializerField(NestedSchema)
    field.name = "nested"

    data = {"name": "John"}
    result = field.validate(data)
    assert result == {"name": "John"}


def test_serializer_field_validate_single_invalid():
    """Test SerializerField validate with invalid single object."""

    class NestedSchema(ObjectSchema):
        name = StringField(required=True)

    field = SerializerField(NestedSchema)
    field.name = "nested"

    data = {}
    with pytest.raises(HTTPException) as exc_info:
        field.validate(data)

    assert exc_info.value.status_code == 400
    assert "nested" in exc_info.value.details


def test_serializer_field_validate_many():
    """Test SerializerField validate with many objects."""

    class NestedSchema(ObjectSchema):
        name = StringField()

    field = SerializerField(NestedSchema, many=True)
    field.name = "nested"

    data = [{"name": "John"}, {"name": "Jane"}]
    result = field.validate(data)
    assert result == [{"name": "John"}, {"name": "Jane"}]


def test_serializer_field_validate_many_invalid():
    """Test SerializerField validate with invalid many objects."""

    class NestedSchema(ObjectSchema):
        name = StringField(required=True)

    field = SerializerField(NestedSchema, many=True)
    field.name = "nested"

    data = [{"name": "John"}, {}]
    with pytest.raises(HTTPException) as exc_info:
        field.validate(data)

    assert exc_info.value.status_code == 400
    assert "nested" in exc_info.value.details


def test_serializer_field_validate_many_not_list():
    """Test SerializerField validate with many but not a list."""

    class NestedSchema(ObjectSchema):
        name = StringField()

    field = SerializerField(NestedSchema, many=True)
    field.name = "nested"

    data = {"name": "John"}
    with pytest.raises(HTTPException) as exc_info:
        field.validate(data)

    assert exc_info.value.status_code == 400
    assert "nested" in exc_info.value.details
    assert "Expected a list of items" in exc_info.value.details["nested"][0]


def test_serializer_field_validate_none_not_required():
    """Test SerializerField validate with None when not required."""

    class NestedSchema(ObjectSchema):
        name = StringField()

    field = SerializerField(NestedSchema, required=False)
    result = field.validate(None)
    assert result is None


def test_serializer_field_to_representation_single():
    """Test SerializerField to_representation with single object."""

    class NestedSchema(ObjectSchema):
        name = StringField()

        @classmethod
        def serialize(cls, obj, many=False, **initkwargs):
            if many:
                return [{"name": o.get("name", "")} for o in obj]
            return {"name": obj.get("name", "")}

    field = SerializerField(NestedSchema)
    data = {"name": "John"}
    result = field.to_representation(data)
    assert result == {"name": "John"}


def test_serializer_field_to_representation_many():
    """Test SerializerField to_representation with many objects."""

    class NestedSchema(ObjectSchema):
        name = StringField()

        @classmethod
        def serialize(cls, obj, many=False, **initkwargs):
            if many:
                return [{"name": o.get("name", "")} for o in obj]
            return {"name": obj.get("name", "")}

    field = SerializerField(NestedSchema, many=True)
    data = [{"name": "John"}, {"name": "Jane"}]
    result = field.to_representation(data)
    assert result == [{"name": "John"}, {"name": "Jane"}]


def test_serializer_field_to_representation_none():
    """Test SerializerField to_representation with None."""

    class NestedSchema(ObjectSchema):
        name = StringField()

        @classmethod
        def serialize(cls, obj, many=False, **initkwargs):
            if many:
                return []
            return None

    field = SerializerField(NestedSchema)
    result = field.to_representation(None)
    assert result is None


def test_undefined_object():
    """Test undefined object."""
    assert undefined is not None
    assert undefined is not False
    assert undefined is not True


def test_object_schema_full_integration():
    """Test ObjectSchema full integration with nested fields."""

    class UserSchema(ObjectSchema):
        name = StringField(max_length=50)
        age = IntegerField(min_value=0, max_value=150)
        email = EmailField()
        is_active = BooleanField(default=True)
        tags = ListField(child=StringField(), max_items=5)
        created_at = DateTimeField()

        def validate(self, data):
            # Custom validation
            if data.get("age", 0) < 18 and data.get("is_active", False):
                raise HTTPException(
                    {"age": ["Must be at least 18 to be active."]}, status_code=400
                )
            return data

    data = {
        "name": "John Doe",
        "age": 25,
        "email": "john@example.com",
        "tags": ["developer", "python"],
        "created_at": "2023-01-01T12:00:00",
    }

    schema = UserSchema(data=data)
    assert schema.is_valid() is True
    assert schema.validated_data["name"] == "John Doe"
    assert schema.validated_data["age"] == 25
    assert schema.validated_data["email"] == "john@example.com"
    assert schema.validated_data["is_active"] is True  # default value
    assert schema.validated_data["tags"] == ["developer", "python"]
    assert isinstance(schema.validated_data["created_at"], datetime)


def test_object_schema_custom_validation_error():
    """Test ObjectSchema with custom validation error."""

    class UserSchema(ObjectSchema):
        age = IntegerField()

        def validate(self, data):
            if data.get("age", 0) < 18:
                raise HTTPException(
                    {"age": ["Must be at least 18 years old."]}, status_code=400
                )
            return data

    data = {"age": 15}
    schema = UserSchema(data=data)

    assert schema.is_valid() is False
    assert "age" in schema.errors
    assert "Must be at least 18 years old." in schema.errors["age"][0]
