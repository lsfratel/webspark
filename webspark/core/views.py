from __future__ import annotations

from collections.abc import Callable
from functools import update_wrapper
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from ..http import Context
    from ..schema import ObjectSchema

from ..constants import HTTP_METHODS
from ..utils import HTTPException

DEFAULT_ACTIONS = {http_method: f"handle_{http_method}" for http_method in HTTP_METHODS}


class View:
    """Base view class for WebSpark applications.

    The View class provides a foundation for creating HTTP request handlers in WebSpark.
    It supports method-based dispatching, data validation with schemas, and request/response
    lifecycle management.

    Example:
        class UserView(View):
            query_params_schema = UserQueryParamsSchema
            body_schema = UserBodySchema

            def handle_get(self, ctx):
                # Validate query parameters
                params = self.validated_query_params(raise_=True)
                # Process request
                users = get_users(**params)
                ctx.json(users)

            def handle_post(self, request):
                # Validate request body
                data = self.validated_body(raise_=True)
                # Process request
                user = create_user(**data)
                ctx.json(user, status=201)

        # Register the view
        app.add_paths([
            path("/users/", view=UserView.as_view())
        ])

    Attributes:
        query_params_schema (type[ObjectSchema] | None): Schema for validating query parameters.
        body_schema (type[ObjectSchema] | None): Schema for validating request body.
        request (Request): Current request object.
        args (tuple): Positional arguments from URL pattern matching.
        kwargs (dict): Keyword arguments from URL pattern matching.
        action_map (dict): Mapping of HTTP methods to handler methods.
    """

    query_params_schema: type[ObjectSchema] | None = None
    body_schema: type[ObjectSchema] | None = None

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

    def _validate_schema(
        self, schema_cls: type[ObjectSchema], data: dict, raise_: bool = True
    ):
        """Validate data using a schema class.

        This method instantiates a schema and validates the provided data.
        If validation fails and raise_ is True, it raises an HTTPException.

        Args:
            schema_cls: The schema class to use for validation.
            data: The data to validate.
            raise_: Whether to raise an exception on validation failure.

        Returns:
            tuple: (validated_data, errors) - validated data and any validation errors.

        Raises:
            HTTPException: If validation fails and raise_ is True.
        """
        schema_instance = schema_cls(data=data, context=self.build_ctx())
        is_valid = schema_instance.is_valid()

        if not is_valid and raise_:
            raise HTTPException(schema_instance.errors, status_code=400)

        return schema_instance.validated_data, schema_instance.errors

    def validated_query_params(self, raise_: bool = False):
        """Get validated query parameters.

        This method validates the request's query parameters using the
        query_params_schema if one is defined. If no schema is defined,
        it returns the raw query parameters.

        Args:
            raise_: Whether to raise an exception on validation failure.

        Returns:
            dict: Validated query parameters or raw query parameters if no schema.
        """
        if not self.query_params_schema:
            return self.ctx.query_params

        return self._validate_schema(
            self.query_params_schema, self.ctx.query_params, raise_
        )

    def validated_body(self, raise_: bool = False):
        """Get validated request body.

        This method validates the request's body using the body_schema if one
        is defined. If no schema is defined, it returns the raw body.

        Args:
            raise_: Whether to raise an exception on validation failure.

        Returns:
            dict: Validated body or raw body if no schema.
        """
        if not self.body_schema:
            return self.ctx.body

        return self._validate_schema(self.body_schema, self.ctx.body, raise_)
