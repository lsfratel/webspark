from __future__ import annotations

from webspark.contrib.plugins import TokenAuthPlugin
from webspark.core import View, WebSpark, path
from webspark.http import Context

# --- User and Token Simulation ---

# This could be your database model
USERS = {
    1: {"id": 1, "name": "Alice", "email": "alice@example.com"},
    2: {"id": 2, "name": "Bob", "email": "bob@example.com"},
}

# This maps tokens to user IDs
TOKENS = {
    "alice_token_123": 1,
    "bob_token_456": 2,
}


def find_user_by_token(token: str) -> dict | None:
    """
    This is the custom token loader function.
    In a real application, this function would query your database to find
    the user associated with the given token.
    """
    user_id = TOKENS.get(token)
    if user_id:
        return USERS.get(user_id)
    return None


# --- Authentication Plugin Setup ---

# 1. Create an instance of the authentication plugin
# 2. Pass your custom `find_user_by_token` function to it.
auth_plugin = TokenAuthPlugin(token_loader=find_user_by_token)


# --- Views ---


class HomeView(View):
    """A public view that doesn't require authentication."""

    def handle_get(self, ctx: Context):
        ctx.json({"message": "Welcome! This is a public endpoint."})


class ProfileView(View):
    """
    A protected view that requires a valid token.
    The `auth_plugin` will be applied to this view's route.
    """

    def handle_get(self, ctx: Context):
        # Because the auth_plugin was successful, `ctx.user` is now available.
        user = ctx.state["user"]
        ctx.json({"message": f"Welcome, {user['name']}!", "user_data": user})


# --- Application Setup ---

app = WebSpark()

# Add routes and apply the plugin to the protected endpoint
app.add_paths(
    [
        path("/", view=HomeView.as_view()),
        path("/profile", view=ProfileView.as_view(), plugins=[auth_plugin]),
    ]
)

if __name__ == "__main__":
    # To run this example:
    # 1. Make sure you have a WSGI server like Gunicorn installed (`pip install gunicorn`).
    # 2. Run the app: `gunicorn examples.auth_example:app`
    #
    # --- How to Test ---
    #
    # 1. Access the public endpoint (no token needed):
    #    curl http://127.0.0.1:8000/
    #
    # 2. Access the protected endpoint with a valid token:
    #    curl http://127.0.0.1:8000/profile -H "Authorization: Token alice_token_123"
    #
    # 3. Access the protected endpoint with an invalid token:
    #    curl http://127.0.0.1:8000/profile -H "Authorization: Token invalid_token"
    #
    # 4. Access the protected endpoint with no token:
    #    curl http://127.0.0.1:8000/profile
    print("Basic API with token-based authentication")
    print("Run with: gunicorn examples.auth_example:app")
