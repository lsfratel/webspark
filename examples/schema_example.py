"""
Schema Validation Example
This example demonstrates WebSpark's schema validation capabilities:
- Using ObjectSchema for request body validation
- Field validation with different data types
- Automatic error responses for invalid data
"""

from webspark.core import View, WebSpark, path
from webspark.core.schema import (
    BooleanField,
    EmailField,
    IntegerField,
    ObjectSchema,
    StringField,
)
from webspark.http import JsonResponse
from webspark.utils import HTTPException


# Define a schema for user data
class UserSchema(ObjectSchema):
    name = StringField(required=True, max_length=100)
    age = IntegerField(min_value=1, max_value=120)
    email = EmailField(required=True)
    is_active = BooleanField(default=True)


# In-memory storage
users = []
next_id = 1


class UserView(View):
    """Handle user operations with schema validation."""

    body_schema = UserSchema  # Attach the schema for automatic validation

    def handle_get(self, request):
        """Return all users."""
        return JsonResponse({"users": users})

    def handle_post(self, request):
        """Create a new user with validation."""
        global next_id

        # When body_schema is defined, WebSpark automatically validates the request body
        # and makes the validated data available through self.validated_body()
        validated_data, errors = self.validated_body(raise_=True)

        # Create new user with validated data
        new_user = {
            "id": next_id,
            "name": validated_data["name"],
            "age": validated_data["age"],
            "email": validated_data["email"],
            "is_active": validated_data["is_active"],
        }
        users.append(new_user)
        next_id += 1

        return JsonResponse(new_user, status=201)


class UserDetailView(View):
    """Handle operations on a single user."""

    def handle_get(self, request):
        """Return a specific user by ID."""
        user_id = int(request.path_params["id"])
        user = next((user for user in users if user["id"] == user_id), None)

        if not user:
            raise HTTPException("User not found", status_code=404)

        return JsonResponse(user)


# Create the app
app = WebSpark(debug=True)

# Add routes
app.add_paths(
    [
        path("/users", view=UserView.as_view()),
        path("/users/:id", view=UserDetailView.as_view()),
    ]
)

if __name__ == "__main__":
    # For development purposes, you can run this with a WSGI server like:
    # gunicorn examples.schema_example:app
    print("Schema Validation Example")
    print("Run with: gunicorn examples.schema_example:app")
