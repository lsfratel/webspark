from ..utils import HTTPException


def min_value_validator(min_value: int):
    def validate(value, field):
        if value < min_value:
            raise HTTPException(
                {field.name: [f"Must be at least {min_value}."]}, status_code=400
            )
        return value

    return validate


def max_value_validator(max_value: int):
    def validate(value, field):
        if value > max_value:
            raise HTTPException(
                {field.name: [f"Must be at most {max_value}."]}, status_code=400
            )
        return value

    return validate


def min_length_validator(min_length: int):
    def validate(value, field):
        if len(value) < min_length:
            raise HTTPException(
                {field.name: [f"Cannot be shorter than {min_length} characters."]},
                status_code=400,
            )
        return value

    return validate


def max_length_validator(max_length: int):
    def validate(value, field):
        if len(value) > max_length:
            raise HTTPException(
                {field.name: [f"Cannot be longer than {max_length} characters."]},
                status_code=400,
            )
        return value

    return validate
