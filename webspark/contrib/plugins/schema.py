from __future__ import annotations

from functools import wraps
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Callable
    from typing import Any

    from ...core.views import View
    from ...http.context import Context
    from ...validation.schema import Schema

from ...core.plugin import Plugin
from ...utils.exceptions import HTTPException


class SchemaPlugin(Plugin):
    """Plugin that validates data from a Context attribute using a Schema.

    It reads data from ctx.<prop>, validates it with the provided
    Schema, raises HTTPException(400) on failure, and, on success, injects
    the validated data into the handler's kwargs under <param or prop>.
    """

    __slots__ = ("schema", "prop", "kwargs", "param")

    def __init__(
        self,
        schema: type[Schema],
        *,
        prop: str,
        param: str = None,
        kwargs: dict = None,
    ):
        """Initialize the SchemaPlugin.

        Args:
            schema: A Schema class used to validate the incoming data.
            prop: Name of the Context attribute to read (e.g., 'json', 'query', 'form').
            param: Optional name for the keyword argument passed to the handler.
                   If omitted, the value of 'prop' is used.
            kwargs: Extra keyword arguments forwarded to the Schema constructor.
        """
        self.schema = schema
        self.prop = prop
        self.kwargs = kwargs or {}
        self.param = param

    def apply(self, handler: Callable[[Context, ...], Any]):
        """Decorate a handler to run schema validation before execution.

        The wrapper validates data taken from the configured Context property and
        passes the validated data to the handler as a keyword argument.

        Args:
            handler: The view handler function to decorate.

        Returns:
            A callable that performs validation then calls the original handler.
        """

        @wraps(handler)
        def wrapper(view: View, *args, **kw: Any):
            """Validate incoming data from the Context and call the handler."""
            ctx = view.ctx

            schema = self.schema
            data = getattr(ctx, self.prop)

            if callable(data):
                raise ValueError("Property must not be callable.")

            schema_instance = schema(data=data, context=view.build_ctx(), **self.kwargs)
            is_valid = schema_instance.is_valid()

            if not is_valid:
                raise HTTPException(schema_instance.errors, status_code=400)

            kw.update({self.param or self.prop: schema_instance.validated_data})

            return handler(view, *args, **kw)

        return wrapper
