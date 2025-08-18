"""
Cookies and Session Example
This example demonstrates:
- Setting and reading cookies
- Simple session management with cookies
- HTML responses
"""

import time

from webspark.core import View, WebSpark, path
from webspark.http import HTMLResponse, JsonResponse
from webspark.utils import HTTPException

# Simple in-memory session store
sessions = {}


class HomeView(View):
    def handle_get(self, request):
        # Check if user has a session
        session_id = request.cookies.get("session_id")
        user_data = sessions.get(session_id) if session_id else None

        if user_data:
            html_content = f"""
            <!DOCTYPE html>
            <html>
            <head>
                <title>WebSpark Cookies Example</title>
                <style>
                    body {{ font-family: Arial, sans-serif; margin: 40px; }}
                    .user-info {{ background: #e7f3ff; padding: 15px; border-radius: 5px; }}
                    .actions {{ margin-top: 20px; }}
                    button {{ padding: 10px 15px; margin: 5px; cursor: pointer; }}
                </style>
            </head>
            <body>
                <h1>WebSpark Cookies Example</h1>
                <div class="user-info">
                    <h2>Welcome back, {user_data["username"]}!</h2>
                    <p>Session ID: {session_id}</p>
                    <p>Login time: {user_data["login_time"]}</p>
                </div>
                <div class="actions">
                    <form action="/logout" method="post" style="display: inline;">
                        <button type="submit">Logout</button>
                    </form>
                </div>
            </body>
            </html>
            """
        else:
            html_content = """
            <!DOCTYPE html>
            <html>
            <head>
                <title>WebSpark Cookies Example</title>
                <style>
                    body { font-family: Arial, sans-serif; margin: 40px; }
                    .login-form { max-width: 300px; padding: 20px; border: 1px solid #ccc; border-radius: 5px; }
                    input { width: 100%; padding: 10px; margin: 10px 0; }
                    button { padding: 10px 15px; cursor: pointer; }
                </style>
            </head>
            <body>
                <h1>WebSpark Cookies Example</h1>
                <div class="login-form">
                    <h2>Login</h2>
                    <form action="/login" method="post">
                        <input type="text" name="username" placeholder="Username" required>
                        <input type="password" name="password" placeholder="Password" required>
                        <button type="submit">Login</button>
                    </form>
                </div>
            </body>
            </html>
            """

        return HTMLResponse(html_content)


class LoginView(View):
    def handle_post(self, request):
        # In a real app, you would validate credentials
        username = request.body.get("username", "") if request.body else ""
        password = request.body.get("password", "") if request.body else ""

        if not username or not password:
            raise HTTPException("Username and password are required", status_code=400)

        # Create a simple session (in a real app, use a proper session library)
        import uuid

        session_id = str(uuid.uuid4())
        sessions[session_id] = {
            "username": username,
            "login_time": time.strftime("%Y-%m-%d %H:%M:%S"),
        }

        # Create response with session cookie
        response = HTMLResponse("""
        <!DOCTYPE html>
        <html>
        <head>
            <title>Login Successful</title>
            <style>
                body { font-family: Arial, sans-serif; margin: 40px; }
                .message { background: #d4edda; padding: 15px; border-radius: 5px; }
            </style>
        </head>
        <body>
            <h1>Login Successful</h1>
            <div class="message">
                <p>You have been logged in successfully!</p>
                <a href="/">Go to home page</a>
            </div>
        </body>
        </html>
        """)
        response.set_cookie(
            "session_id",
            session_id,
            {
                "path": "/",
                "max_age": 3600,  # 1 hour
                "httponly": True,
                "secure": False,  # Set to True in production with HTTPS
            },
        )

        return response


class LogoutView(View):
    def handle_post(self, request):
        # Clear session
        session_id = request.cookies.get("session_id")
        if session_id and session_id in sessions:
            del sessions[session_id]

        # Create response that clears the cookie
        response = HTMLResponse("""
        <!DOCTYPE html>
        <html>
        <head>
            <title>Logged Out</title>
            <style>
                body { font-family: Arial, sans-serif; margin: 40px; }
                .message { background: #f8d7da; padding: 15px; border-radius: 5px; }
            </style>
        </head>
        <body>
            <h1>Logged Out</h1>
            <div class="message">
                <p>You have been logged out successfully.</p>
                <a href="/">Go to home page</a>
            </div>
        </body>
        </html>
        """)
        response.delete_cookie("session_id")

        return response


class SessionInfoView(View):
    def handle_get(self, request):
        session_id = request.cookies.get("session_id")
        user_data = sessions.get(session_id) if session_id else None

        return JsonResponse(
            {
                "session_id": session_id,
                "user_data": user_data,
                "active_sessions": len(sessions),
            }
        )


# Create the app
app = WebSpark(debug=True)

# Add routes
app.add_paths(
    [
        path("/", view=HomeView.as_view()),
        path("/login", view=LoginView.as_view()),
        path("/logout", view=LogoutView.as_view()),
        path("/session-info", view=SessionInfoView.as_view()),
    ]
)

if __name__ == "__main__":
    # For development purposes, you can run this with a WSGI server like:
    # gunicorn examples.cookies_example:app
    print("Cookies and Session Example")
    print("Run with: gunicorn examples.cookies_example:app")
