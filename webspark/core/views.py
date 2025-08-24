from __future__ import annotations

from collections.abc import Callable
from functools import update_wrapper
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from ..http import Context

from ..constants import HTTP_METHODS
from ..utils import HTTPException

DEFAULT_ACTIONS = {http_method: f"handle_{http_method}" for http_method in HTTP_METHODS}


class View:
    """Base view class for WebSpark applications.

    The View class provides a foundation for creating HTTP request handlers in WebSpark.
    It supports method-based dispatching, and request/response lifecycle management.

    Example:
        class UserView(View):

            def handle_get(self, ctx):
                # Validate query parameters
                params = ctx.query_params
                # Process request
                users = get_users(**params)
                ctx.json(users)

            def handle_post(self, ctx):
                # Validate request body
                data = ctx.body
                # Process request
                user = create_user(**data)
                ctx.json(user, status=201)

        # Register the view
        app.add_paths([
            path("/users/", view=UserView.as_view())
        ])

    Attributes:
        request (Request): Current request object.
        args (tuple): Positional arguments from URL pattern matching.
        kwargs (dict): Keyword arguments from URL pattern matching.
        action_map (dict): Mapping of HTTP methods to handler methods.
    """

    @property
    def ctx(self):
        """Get the current context object.

        Returns:
            Context: The context of the request being processed.
        """
        return self.__ctx__

    @ctx.setter
    def ctx(self, ctx: Context):
        """Set the current context object.

        Args:
            ctx: The context object to set.
        """
        self.__ctx__ = ctx

    @classmethod
    def as_view(
        cls,
        actions: dict[str, str] = None,
        **initkwargs,
    ) -> Callable[[Context], None]:
        """Create a view function from a View class.

        This method converts a View class into a callable function that can be
        used as a WSGI application. It handles HTTP method dispatching and
        view instantiation.

        Args:
            actions: Mapping of HTTP methods to handler method names.
                If not provided, uses DEFAULT_ACTIONS for methods that exist on the class.
            **initkwargs: Keyword arguments to pass to the view constructor.

        Returns:
            Callable: A WSGI-compatible view function.

        Example:
            # Use default actions (handle_get, handle_post, etc.)
            view_func = MyView.as_view()

            # Specify custom actions
            view_func = MyView.as_view({
                "get": "list_users",
                "post": "create_user"
            })

            # Pass initialization arguments
            view_func = MyView.as_view(custom_param="value")
        """
        if not actions:
            actions = {
                http_method: handler_name
                for http_method, handler_name in DEFAULT_ACTIONS.items()
                if hasattr(cls, handler_name)
            }

        if "get" in actions and "head" not in actions:
            actions["head"] = actions["get"]

        http_methods = actions.keys()

        def view(ctx: Context, *args, **kwargs):
            self = cls(**initkwargs)
            self.action_map = actions
            ctx.environ["webspark.view_instance"] = self

            return self.dispatch(ctx, *args, **kwargs)

        update_wrapper(view, cls, updated=())
        view.http_methods = http_methods

        return view

    def dispatch(self, ctx: Context, *args, **kwargs):
        """Dispatch the request to the appropriate handler method.

        This method sets up the view state and calls the handler method that
        corresponds to the request's HTTP method.

        Args:
            ctx: The context of the request being processed.
            *args: Positional arguments from URL pattern matching.
            **kwargs: Keyword arguments from URL pattern matching.

        Returns:
            Response: The HTTP response from the handler method.
        """
        actions = self.action_map

        if ctx.method not in actions:
            raise HTTPException("Method not allowed.", status_code=405)

        self.args = args
        self.kwargs = kwargs
        self.ctx = ctx

        handler = getattr(self, actions[ctx.method])

        return handler(ctx, *args, **kwargs)

    def build_ctx(self):
        """Build context dictionary for schema validation.

        This method creates a context dictionary that is passed to schema
        validators. It includes references to the view, request, and URL parameters.

        Returns:
            dict: Context dictionary with view, args, kwargs, and request.
        """
        return {
            "view": self,
            "args": self.args,
            "kwargs": self.kwargs,
            "ctx": self.ctx,
        }
