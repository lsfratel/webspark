import uuid
from datetime import datetime
from decimal import Decimal
from enum import Enum
from unittest.mock import Mock

import pytest

from webspark.utils import HTTPException
from webspark.validation import Schema
from webspark.validation.fields import (
    UNDEFINED,
    BaseField,
    BooleanField,
    DateTimeField,
    DecimalField,
    EmailField,
    EnumField,
    FloatField,
    IntegerField,
    ListField,
    MethodField,
    RegexField,
    SerializerField,
    StringField,
    URLField,
    UUIDField,
)


def test_base_field_initialization():
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
    field = BaseField(source_name="source")
    field.bind("field_name")

    assert field.field_name == "field_name"
    assert field.name == "source"

    field2 = BaseField()
    field2.bind("field_name")
    assert field2.name == "field_name"


def test_base_field_validate_required():
    field = BaseField(required=True)
    field.name = "test_field"

    with pytest.raises(HTTPException) as exc_info:
        field.validate(UNDEFINED)

    assert exc_info.value.status_code == 400
    assert "test_field" in exc_info.value.details
    assert "This field is required." in exc_info.value.details["test_field"]


def test_base_field_validate_nullable():
    field = BaseField(required=True, nullable=True)
    result = field.validate(None)
    assert result is None


def test_base_field_validate_with_validators():
    def validator(value, field):
        if value != "valid":
            raise ValueError("Invalid value")
        return value

    field = BaseField(validators=[validator])
    result = field.validate("valid")
    assert result == "valid"

    with pytest.raises(ValueError):
        field.validate("invalid")


def test_base_field_to_representation():
    field = BaseField()
    value = "test_value"
    result = field.to_representation(value, {})
    assert result == value


def test_schema_meta():
    class TestSchema(Schema):
        field1 = StringField()
        field2 = IntegerField()

    assert hasattr(TestSchema, "_declared_fields")
    assert "field1" in TestSchema._declared_fields
    assert "field2" in TestSchema._declared_fields
    assert isinstance(TestSchema._declared_fields["field1"], StringField)
    assert isinstance(TestSchema._declared_fields["field2"], IntegerField)


def test_schema_inheritance():
    class BaseSchema(Schema):
        base_field = StringField()

    class ChildSchema(BaseSchema):
        child_field = IntegerField()

    assert "base_field" in ChildSchema._declared_fields
    assert "child_field" in ChildSchema._declared_fields


def test_schema_initialization():
    class TestSchema(Schema):
        pass

    schema = TestSchema(
        data={"key": "value"}, context={"ctx": "test"}
    )

    assert schema.initial_data == {"key": "value"}
    assert schema.context == {"ctx": "test"}
    assert schema._validated_data is None
    assert schema._errors == {}
    assert schema.fields == {}


def test_schema_properties():
    class TestSchema(Schema):
        pass

    schema = TestSchema()

    assert schema.errors == {}

    with pytest.raises(
        AttributeError,
        match="You must call `.is_valid\\(\\)` before accessing `validated_data`\\.",
    ):
        _ = schema.validated_data


def test_schema_validate():
    class TestSchema(Schema):
        pass

    schema = TestSchema()
    data = {"key": "value"}
    result = schema.validate(data)
    assert result == data


def test_schema_is_valid_no_data():
    class TestSchema(Schema):
        pass

    schema = TestSchema(data=None)
    result = schema.is_valid()

    assert result is True
    assert schema.errors == {}


def test_schema_is_valid_with_field_errors():
    class TestSchema(Schema):
        required_field = StringField(required=True)

    schema = TestSchema(data={})
    result = schema.is_valid()

    assert result is False
    assert "required_field" in schema.errors
    assert "This field is required." in schema.errors["required_field"]


def test_schema_is_valid_with_custom_validation_error():
    class TestSchema(Schema):
        def validate(self, data):
            raise HTTPException({"custom": ["Custom error"]}, status_code=400)

    schema = TestSchema(data={"key": "value"})
    result = schema.is_valid()

    assert result is False
    assert schema.errors == {"custom": ["Custom error"]}


def test_schema_is_valid_success():
    class TestSchema(Schema):
        name = StringField()
        age = IntegerField()

    schema = TestSchema(data={"name": "John", "age": 30})
    result = schema.is_valid()

    assert result is True
    assert schema.errors == {}
    assert schema.validated_data == {"name": "John", "age": 30}


def test_integer_field_validate():
    field = IntegerField()
    field.name = "age"

    result = field.validate("30")
    assert result == 30

    result = field.validate(30)
    assert result == 30


def test_integer_field_validate_invalid():
    field = IntegerField()
    field.name = "age"

    with pytest.raises(HTTPException) as exc_info:
        field.validate("invalid")

    assert exc_info.value.status_code == 400
    assert "age" in exc_info.value.details
    assert "Value must be an integer" in exc_info.value.details["age"][0]


def test_integer_field_validate_none():
    field = IntegerField(required=False)
    field.name = "field"
    result = field.validate(UNDEFINED)
    assert result is None


def test_integer_field_validate_with_default():
    field = IntegerField(default=18)
    field.name = "field"
    result = field.validate(UNDEFINED)
    assert result == 18


def test_integer_field_validate_min_value():
    field = IntegerField(min_value=18)
    field.name = "age"

    result = field.validate(25)
    assert result == 25

    with pytest.raises(HTTPException) as exc_info:
        field.validate(10)

    assert "Value must be at least 18." in exc_info.value.details["age"][0]


def test_integer_field_validate_max_value():
    field = IntegerField(max_value=100)
    field.name = "age"

    result = field.validate(50)
    assert result == 50

    with pytest.raises(HTTPException) as exc_info:
        field.validate(150)

    assert "Value must be at most 100." in exc_info.value.details["age"][0]


def test_float_field_validate():
    field = FloatField()
    field.name = "price"

    result = field.validate("30.5")
    assert result == 30.5

    result = field.validate(30.5)
    assert result == 30.5


def test_float_field_validate_invalid():
    field = FloatField()
    field.name = "price"

    with pytest.raises(HTTPException) as exc_info:
        field.validate("invalid")

    assert exc_info.value.status_code == 400
    assert "price" in exc_info.value.details
    assert "Value must be a float" in exc_info.value.details["price"][0]


def test_float_field_validate_min_value():
    field = FloatField(min_value=0.0)
    field.name = "price"

    result = field.validate(10.5)
    assert result == 10.5

    with pytest.raises(HTTPException) as exc_info:
        field.validate(-5.0)

    assert "Value must be at least 0.0." in exc_info.value.details["price"][0]


def test_float_field_validate_max_value():
    field = FloatField(max_value=100.0)
    field.name = "price"

    result = field.validate(50.0)
    assert result == 50.0

    with pytest.raises(HTTPException) as exc_info:
        field.validate(150.0)

    assert "Value must be at most 100.0." in exc_info.value.details["price"][0]


def test_string_field_validate():
    field = StringField()
    field.name = "name"

    result = field.validate("John")
    assert result == "John"


def test_string_field_validate_invalid():
    field = StringField()
    field.name = "name"

    with pytest.raises(HTTPException) as exc_info:
        field.validate(123)

    assert exc_info.value.status_code == 400
    assert "name" in exc_info.value.details
    assert "Value must be a string" in exc_info.value.details["name"][0]


def test_string_field_validate_min_length():
    field = StringField(min_length=3)
    field.name = "name"

    result = field.validate("John")
    assert result == "John"

    with pytest.raises(HTTPException) as exc_info:
        field.validate("Jo")

    assert (
        "Value must be at least 3 characters long." in exc_info.value.details["name"][0]
    )


def test_string_field_validate_max_length():
    field = StringField(max_length=5)
    field.name = "name"

    result = field.validate("John")
    assert result == "John"

    with pytest.raises(HTTPException) as exc_info:
        field.validate("John Doe")

    assert (
        "Value must be at most 5 characters long." in exc_info.value.details["name"][0]
    )


def test_boolean_field_validate():
    field = BooleanField()
    field.name = "active"

    assert field.validate(True) is True
    assert field.validate(False) is False

    assert field.validate("true") is True
    assert field.validate("false") is False
    assert field.validate("1") is True
    assert field.validate("0") is False
    assert field.validate("yes") is True
    assert field.validate("no") is False
    assert field.validate("on") is True
    assert field.validate("off") is False


def test_boolean_field_validate_invalid():
    field = BooleanField()
    field.name = "active"

    with pytest.raises(HTTPException) as exc_info:
        field.validate("invalid")

    assert exc_info.value.status_code == 400
    assert "active" in exc_info.value.details
    assert "Value must be boolean" in exc_info.value.details["active"][0]


def test_boolean_field_validate_none():
    field = BooleanField(required=False)
    field.name = "field"
    result = field.validate(UNDEFINED)
    assert result is None


def test_list_field_validate():
    field = ListField()
    field.name = "items"

    result = field.validate([1, 2, 3])
    assert result == [1, 2, 3]


def test_list_field_validate_invalid():
    field = ListField()
    field.name = "items"

    with pytest.raises(HTTPException) as exc_info:
        field.validate("not a list")

    assert exc_info.value.status_code == 400
    assert "items" in exc_info.value.details
    assert "Value must be a list" in exc_info.value.details["items"][0]


def test_list_field_validate_none():
    field = ListField(required=False)
    field.name = "field"
    result = field.validate(UNDEFINED)
    assert result is None


def test_list_field_validate_min_items():
    field = ListField(min_items=2)
    field.name = "items"

    result = field.validate([1, 2, 3])
    assert result == [1, 2, 3]

    with pytest.raises(HTTPException) as exc_info:
        field.validate([1])

    assert "Value must have at least 2 items." in exc_info.value.details["items"][0]


def test_list_field_validate_max_items():
    field = ListField(max_items=3)
    field.name = "items"

    result = field.validate([1, 2])
    assert result == [1, 2]

    with pytest.raises(HTTPException) as exc_info:
        field.validate([1, 2, 3, 4])

    assert "Value must have at most 3 items." in exc_info.value.details["items"][0]


def test_list_field_validate_with_child_field():
    field = ListField(child=IntegerField())
    field.name = "numbers"

    result = field.validate(["1", "2", "3"])
    assert result == [1, 2, 3]


def test_list_field_validate_with_child_field_errors():
    field = ListField(child=IntegerField())
    field.name = "numbers"

    with pytest.raises(HTTPException) as exc_info:
        field.validate(["1", "invalid", "3"])

    assert exc_info.value.status_code == 400
    assert "numbers" in exc_info.value.details


def test_list_field_to_representation():
    field = ListField()
    result = field.to_representation([1, 2, 3])
    assert result == [1, 2, 3]


def test_list_field_to_representation_with_child():
    child_field = Mock()
    child_field.to_representation.return_value = "mocked"
    field = ListField(child=child_field)

    result = field.to_representation([1, 2, 3])
    assert result == ["mocked", "mocked", "mocked"]
    assert child_field.to_representation.call_count == 3


def test_list_field_to_representation_none():
    field = ListField()
    result = field.to_representation(None, {})
    assert result is None


def test_datetime_field_validate():
    field = DateTimeField()
    field.name = "created_at"

    dt_str = "2023-01-01T12:00:00"
    result = field.validate(dt_str)
    assert isinstance(result, datetime)
    assert result.isoformat() == "2023-01-01T12:00:00"


def test_datetime_field_validate_datetime_object():
    field = DateTimeField()
    dt = datetime(2023, 1, 1, 12, 0, 0)
    result = field.validate(dt)
    assert result is dt


def test_datetime_field_validate_invalid():
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
    field = DateTimeField(auto_now=True)
    result = field.validate("2023-01-01T12:00:00")
    assert isinstance(result, datetime)


def test_uuid_field_validate():
    field = UUIDField()
    field.name = "id"

    uuid_str = "550e8400-e29b-41d4-a716-446655440000"
    result = field.validate(uuid_str)
    assert isinstance(result, uuid.UUID)
    assert str(result) == uuid_str


def test_uuid_field_validate_invalid():
    field = UUIDField()
    field.name = "id"

    with pytest.raises(HTTPException) as exc_info:
        field.validate("invalid")

    assert exc_info.value.status_code == 400
    assert "id" in exc_info.value.details
    assert "Value must be a valid UUID" in exc_info.value.details["id"][0]


def test_email_field_validate():
    field = EmailField()
    field.name = "email"

    result = field.validate("test@example.com")
    assert result == "test@example.com"


def test_email_field_validate_invalid():
    field = EmailField()
    field.name = "email"

    with pytest.raises(HTTPException) as exc_info:
        field.validate("invalid")

    assert exc_info.value.status_code == 400
    assert "email" in exc_info.value.details
    assert "Value must be a valid email address" in exc_info.value.details["email"][0]


def test_url_field_validate():
    field = URLField()
    field.name = "website"

    result = field.validate("https://example.com")
    assert result == "https://example.com"


def test_url_field_validate_invalid():
    field = URLField()
    field.name = "website"

    with pytest.raises(HTTPException) as exc_info:
        field.validate("invalid")

    assert exc_info.value.status_code == 400
    assert "website" in exc_info.value.details
    assert "Value must be a valid URL" in exc_info.value.details["website"][0]


def test_url_field_validate_with_schemes():
    field = URLField(schemes=["https"])
    field.name = "website"

    result = field.validate("https://example.com")
    assert result == "https://example.com"

    with pytest.raises(HTTPException) as exc_info:
        field.validate("http://example.com")

    assert "Invalid URL scheme" in exc_info.value.details["website"][0]


def test_enum_field_validate_with_enum():
    class Color(Enum):
        RED = "red"
        GREEN = "green"
        BLUE = "blue"

    field = EnumField(Color)
    field.name = "color"

    result = field.validate("red")
    assert result == Color.RED

    with pytest.raises(HTTPException):
        field.validate(Color.GREEN)


def test_enum_field_validate_with_list():
    field = EnumField(["red", "green", "blue"])
    field.name = "color"

    result = field.validate("red")
    assert result == "red"


def test_enum_field_validate_invalid():
    field = EnumField(["red", "green", "blue"])
    field.name = "color"

    with pytest.raises(HTTPException) as exc_info:
        field.validate("yellow")

    assert exc_info.value.status_code == 400
    assert "color" in exc_info.value.details
    assert "Value must be one of" in exc_info.value.details["color"][0]


def test_decimal_field_validate():
    field = DecimalField()
    field.name = "price"

    result = field.validate("10.50")
    assert isinstance(result, Decimal)
    assert result == Decimal("10.50")


def test_decimal_field_validate_invalid():
    field = DecimalField()
    field.name = "price"

    with pytest.raises(HTTPException) as exc_info:
        field.validate("invalid")

    assert exc_info.value.status_code == 400
    assert "price" in exc_info.value.details
    assert "Value must be a valid decimal number" in exc_info.value.details["price"][0]


def test_decimal_field_validate_max_digits():
    field = DecimalField(max_digits=5)
    field.name = "price"

    result = field.validate("123.45")
    assert result == Decimal("123.45")

    with pytest.raises(HTTPException) as exc_info:
        field.validate("12345.67")

    assert "Must have at most 5 digits" in exc_info.value.details["price"][0]


def test_decimal_field_validate_decimal_places():
    field = DecimalField(decimal_places=2)
    field.name = "price"

    result = field.validate("123.45")
    assert result == Decimal("123.45")

    with pytest.raises(HTTPException) as exc_info:
        field.validate("123.456")

    assert "Must have at most 2 decimal places" in exc_info.value.details["price"][0]


def test_regex_field_validate():
    field = RegexField(r"^\d{3}-\d{3}-\d{4}$")
    field.name = "phone"

    result = field.validate("123-456-7890")
    assert result == "123-456-7890"


def test_regex_field_validate_invalid():
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


def test_method_field_validate():
    schema = Mock()
    schema.get_method = lambda data: data["test"]

    field = MethodField(method_name="get_method")
    field.schema = schema
    result = field.validate(None, {"test": True})
    assert result is True


def test_method_field_raise_for_no_method():
    field = MethodField(method_name="non_existent_method")
    field.schema = object()

    with pytest.raises(HTTPException):
        field.validate(None, {})


def test_method_field_to_representation():
    obj = Mock()
    obj.some_attr = "value"

    schema = Mock()
    schema.get_method = lambda obj: obj.some_attr

    field = MethodField(method_name="get_method")
    field.schema = schema

    result = field.to_representation(None, obj)
    assert result == "value"


def test_serializer_field_validate_single():
    class NestedSchema(Schema):
        name = StringField()

    field = SerializerField(NestedSchema)
    field.name = "nested"

    data = {"name": "John"}
    result = field.validate(data)
    assert result == {"name": "John"}


def test_serializer_field_validate_single_invalid():
    class NestedSchema(Schema):
        name = StringField(required=True)

    field = SerializerField(NestedSchema)
    field.name = "nested"

    data = {}
    with pytest.raises(HTTPException) as exc_info:
        field.validate(data)

    assert exc_info.value.status_code == 400
    assert "nested" in exc_info.value.details


def test_serializer_field_validate_many():
    class NestedSchema(Schema):
        name = StringField()

    field = SerializerField(NestedSchema, many=True)
    field.name = "nested"

    data = [{"name": "John"}, {"name": "Jane"}]
    result = field.validate(data)
    assert result == [{"name": "John"}, {"name": "Jane"}]


def test_serializer_field_validate_many_invalid():
    class NestedSchema(Schema):
        name = StringField(required=True)

    field = SerializerField(NestedSchema, many=True)
    field.name = "nested"

    data = [{"name": "John"}, {}]
    with pytest.raises(HTTPException) as exc_info:
        field.validate(data)

    assert exc_info.value.status_code == 400
    assert "nested" in exc_info.value.details


def test_serializer_field_validate_many_not_list():
    class NestedSchema(Schema):
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
    class NestedSchema(Schema):
        name = StringField()

    field = SerializerField(NestedSchema, required=False)
    field.name = "nested"
    result = field.validate(UNDEFINED)
    assert result is None


def test_serializer_field_to_representation_single():
    class NestedSchema(Schema):
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
    class NestedSchema(Schema):
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
    class NestedSchema(Schema):
        name = StringField()

        @classmethod
        def serialize(cls, obj, many=False, **initkwargs):
            if many:
                return []
            return None

    field = SerializerField(NestedSchema)
    result = field.to_representation(None)
    assert result is None


def test_schema_full_integration():
    class UserSchema(Schema):
        name = StringField(max_length=50)
        age = IntegerField(min_value=0, max_value=150)
        email = EmailField()
        is_active = BooleanField(default=True)
        tags = ListField(child=StringField(), max_items=5)

        def validate(self, data):
            data = super().validate(data)
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
    }

    schema = UserSchema(data=data)
    assert schema.is_valid() is True
    assert schema.validated_data["name"] == "John Doe"
    assert schema.validated_data["age"] == 25
    assert schema.validated_data["email"] == "john@example.com"
    assert schema.validated_data["is_active"] is True
    assert schema.validated_data["tags"] == ["developer", "python"]


def test_schema_custom_validation_error():
    class UserSchema(Schema):
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


def test_schema_partial():
    class UserSchema(Schema):
        name = StringField(required=True)
        age = IntegerField(required=True)
        email = EmailField(required=True)

    data = {"name": "John Doe"}
    schema = UserSchema(data, partial=True)

    assert schema.is_valid() is True
    assert schema.errors == {}
    assert schema.validated_data == {"name": "John Doe"}
