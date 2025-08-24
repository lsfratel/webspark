"""
Schema Validation Example
This example demonstrates WebSpark's schema validation capabilities:
- Using Schema for request body validation
- Field validation with different data types
- Automatic error responses for invalid data
"""

from webspark.core import View, WebSpark, path
from webspark.http import Context
from webspark.utils import HTTPException
from webspark.validation import Schema, fields


# Define a schema for user data
class UserSchema(Schema):
    name = fields.StringField(required=True, max_length=100)
    age = fields.IntegerField(min_value=1, max_value=120)
    email = fields.EmailField(required=True)
    is_active = fields.BooleanField(default=True)


# In-memory storage
users = []
next_id = 1


class UserView(View):
    """Handle user operations with schema validation."""

    def handle_get(self, ctx: Context):
        """Return all users."""
        ctx.json({"users": users})

    def handle_post(self, ctx: Context):
        """Create a new user with validation."""
        global next_id

        schema_instance = UserSchema(data=ctx.body)
        if not schema_instance.is_valid():
            raise HTTPException(schema_instance.errors, status_code=400)

        validated_data = schema_instance.validated_data

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

        ctx.json(new_user, status=201)


class UserDetailView(View):
    """Handle operations on a single user."""

    def handle_get(self, ctx: Context):
        """Return a specific user by ID."""
        user_id = int(ctx.path_params["id"])
        user = next((user for user in users if user["id"] == user_id), None)

        if not user:
            raise HTTPException("User not found", status_code=404)

        ctx.json(user)


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
    # gunicorn examples.validation_example:app
    print("Schema Validation Example")
    print("Run with: gunicorn examples.validation_example:app")
