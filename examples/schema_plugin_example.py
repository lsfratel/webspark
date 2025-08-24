"""
Schema Validation Example
This example demonstrates WebSpark's schema validation capabilities:
- Using Schema for request body validation
- Field validation with different data types
- Automatic error responses for invalid data
"""

from webspark.contrib.plugins.schema import SchemaPlugin
from webspark.core import View, WebSpark, path
from webspark.http import Context
from webspark.schema import (
    BooleanField,
    EmailField,
    IntegerField,
    Schema,
    StringField,
)
from webspark.utils import HTTPException
from webspark.utils.decorators import apply


# Define a schema for user data
class UserSchema(Schema):
    name = StringField(required=True, max_length=100)
    email = EmailField(required=True)
    age = IntegerField(min_value=1, max_value=120)
    is_active = BooleanField(default=True)


# In-memory storage
users = []
next_id = 1


class UserView(View):
    """Handle user operations with schema validation."""

    body_schema = UserSchema  # Attach the schema for automatic validation

    def handle_get(self, ctx: Context):
        """Return all users."""
        ctx.json({"users": users})

    @apply(
        SchemaPlugin(UserSchema, prop="body", kw="body"),
    )
    def handle_post(self, ctx: Context, body: dict):
        """Create a new user with validation."""
        global next_id

        # When body_schema is defined, WebSpark automatically validates the request body
        # and makes the validated data available through self.validated_body()
        # validated_data, errors = self.validated_body(raise_=True)

        # Create new user with validated data
        new_user = {
            "id": next_id,
            "name": body["name"],
            "age": body["age"],
            "email": body["email"],
            "is_active": body["is_active"],
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
    # gunicorn examples.schema_example:app
    print("Schema Validation Example")
    print("Run with: gunicorn examples.schema_plugin_example:app")
