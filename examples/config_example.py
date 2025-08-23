"""
Configuration, Proxy, and Allowed Hosts Example
This example demonstrates:
- Application configuration
- Proxy configuration for production deployments
- Allowed hosts security feature
- Environment variable usage
"""

from webspark.contrib.plugins import AllowedHostsPlugin
from webspark.core import View, WebSpark, path
from webspark.http import Context
from webspark.utils import env


# Configuration class
class AppConfig:
    # Debug mode from environment variable or default to False
    DEBUG = env("DEBUG", default=False, parser=bool)

    # Secret key from environment variable (required in production)
    SECRET_KEY = env("SECRET_KEY", default="dev-secret-key")

    # Database URL from environment variable or default
    DATABASE_URL = env("DATABASE_URL", default="sqlite:///dev.db")

    # Proxy configuration
    TRUST_PROXY = env("TRUST_PROXY", default=False, parser=bool)
    # TRUSTED_PROXY_LIST = ["192.168.1.1", "10.0.0.1"]  # Uncomment to specify trusted proxies
    # TRUSTED_PROXY_COUNT = 1  # Uncomment to specify number of trusted proxies

    # Allowed hosts for security (in production, specify your domain)
    ALLOWED_HOSTS = env(
        "ALLOWED_HOSTS",
        default=["*"] if DEBUG else ["localhost", "127.0.0.1"],
        parser=lambda x: x.split(",") if x else [],
    )


# Create the app with configuration
app = WebSpark(
    config=AppConfig(),
    debug=AppConfig.DEBUG,
    plugins=[AllowedHostsPlugin(allowed_hosts=AppConfig.ALLOWED_HOSTS)],
)


# Sample view to show configuration
class ConfigView(View):
    def handle_get(self, ctx: Context):
        # In a real app, you wouldn't expose sensitive config like this
        ctx.json(
            {
                "debug": app.debug,
                "config": {
                    "TRUST_PROXY": getattr(app.config, "TRUST_PROXY", None),
                    "ALLOWED_HOSTS": getattr(app.config, "ALLOWED_HOSTS", None),
                    "DATABASE_URL": getattr(app.config, "DATABASE_URL", None),
                },
                "request_info": {
                    "host": ctx.host,
                    "scheme": ctx.scheme,
                    "ip": ctx.ip,
                    "method": ctx.method,
                    "path": ctx.path,
                },
            }
        )


class HomeView(View):
    def handle_get(self, ctx: Context):
        html_content = (
            """
        <!DOCTYPE html>
        <html>
        <head>
            <title>WebSpark Configuration Example</title>
            <style>
                body { font-family: Arial, sans-serif; margin: 40px; }
                .config-info { background: #f0f8ff; padding: 20px; border-radius: 5px; }
                .env-var { margin: 10px 0; }
                code { background: #eee; padding: 2px 5px; border-radius: 3px; }
            </style>
        </head>
        <body>
            <h1>WebSpark Configuration Example</h1>
            <div class="config-info">
                <h2>Environment Variables</h2>
                <div class="env-var"><strong>DEBUG:</strong> <code>"""
            + str(env("DEBUG", default=False))
            + """</code></div>
                <div class="env-var"><strong>SECRET_KEY:</strong> <code>"""
            + ("Set" if env("SECRET_KEY") else "Not set")
            + """</code></div>
                <div class="env-var"><strong>DATABASE_URL:</strong> <code>"""
            + env("DATABASE_URL", default="sqlite:///dev.db")
            + """</code></div>
                <div class="env-var"><strong>TRUST_PROXY:</strong> <code>"""
            + str(env("TRUST_PROXY", default=False))
            + """</code></div>
                <div class="env-var"><strong>ALLOWED_HOSTS:</strong> <code>"""
            + str(env("ALLOWED_HOSTS", default="*"))
            + """</code></div>

                <h2>Endpoints</h2>
                <ul>
                    <li><a href="/config">/config</a> - View application configuration</li>
                </ul>

                <h2>Try it out</h2>
                <p>Set environment variables to see how the configuration changes:</p>
                <pre>DEBUG=true SECRET_KEY=my-secret DATABASE_URL=postgresql://localhost/mydb python -m gunicorn examples.config_example:app</pre>
            </div>
        </body>
        </html>
        """
        )
        ctx.html(html_content)


# Add routes
app.add_paths(
    [path("/", view=HomeView.as_view()), path("/config", view=ConfigView.as_view())]
)

if __name__ == "__main__":
    # For development purposes, you can run this with a WSGI server like:
    # gunicorn examples.config_example:app
    print("Configuration, Proxy, and Allowed Hosts Example")
    print("Run with: gunicorn examples.config_example:app")
    print("\nTry setting environment variables:")
    print(
        "DEBUG=true SECRET_KEY=my-secret DATABASE_URL=postgresql://localhost/mydb gunicorn examples.config_example:app"
    )
