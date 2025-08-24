from __future__ import annotations

from functools import wraps
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Callable
    from typing import Any

    from ...core.views import View
    from ...http.context import Context
    from ...schema.object_schema import ObjectSchema

from ...core.plugin import Plugin
from ...utils.exceptions import HTTPException


class SchemaPlugin(Plugin):
    """Plugin that validates data from the request context using an ObjectSchema.

    The plugin reads a value from the view context using `ctx_prop`. If that
    value is callable, it is invoked with `ctx_args` to obtain the data. The
    data is then validated using the provided `schema`. If validation succeeds,
    the validated data is injected into the handler's keyword arguments under
    the name provided by `kw` (or `ctx_prop` if `kw` is None). If validation
    fails, an HTTPException with status code 400 is raised.
    """

    __slots__ = ("schema", "ctx_prop", "ctx_args", "kw")

    def __init__(
        self,
        schema: type[ObjectSchema],
        *,
        ctx_prop: str,
        ctx_args: tuple = None,
        kw: str = None,
    ):
        """Initialize the SchemaPlugin.

        Args:
            schema: The ObjectSchema subclass used to validate the input data.
            ctx_prop: The attribute name on the Context from which to read data.
            ctx_args: Optional positional arguments used if the context attribute
                is callable; defaults to an empty tuple.
            kw: Optional keyword name under which to pass validated data to the
                handler; if None, `ctx_prop` is used.
        """
        self.schema = schema
        self.ctx_prop = ctx_prop
        self.ctx_args = ctx_args or ()
        self.kw = kw

    def apply(self, handler: Callable[[Context, ...], Any]):
        """Wrap a view handler with schema validation against context data.

        The wrapped handler will:
        - Read data from `view.ctx.<ctx_prop>`
        - Call it with `ctx_args` if it is callable
        - Validate the data using the configured schema
        - Raise HTTPException(400) if validation fails
        - Pass the validated data to the handler via keyword argument `kw`
          (or `ctx_prop` if `kw` is not provided)

        Args:
            handler: The view handler function to wrap.

        Returns:
            A callable that enforces schema validation before calling the handler.
        """

        @wraps(handler)
        def wrapper(view: View, *args, **kw: Any):
            ctx = view.ctx

            schema = self.schema
            data = getattr(ctx, self.ctx_prop)

            if callable(data):
                data = data(*self.ctx_args)

            schema_instance = schema(data=data, context=view.build_ctx())
            is_valid = schema_instance.is_valid()

            if not is_valid:
                raise HTTPException(schema_instance.errors, status_code=400)

            kw.update({self.kw or self.ctx_prop: schema_instance.validated_data})

            return handler(view, *args, **kw)

        return wrapper
