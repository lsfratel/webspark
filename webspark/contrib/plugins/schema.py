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
    """Plugin that validates data from the request context using a Schema.

    The plugin reads a value from the view context using `prop`. If that
    value is callable, it is invoked with `args` to obtain the data. The
    data is then validated using the provided `schema`. If validation succeeds,
    the validated data is injected into the handler's keyword arguments under
    the name provided by `kw` (or `prop` if `kw` is None). If validation
    fails, an HTTPException with status code 400 is raised.
    """

    __slots__ = ("schema", "prop", "args", "kw")

    def __init__(
        self,
        schema: type[Schema],
        *,
        prop: str,
        args: tuple = None,
        kw: str = None,
    ):
        """Initialize the SchemaPlugin.

        Args:
            schema: The Schema subclass used to validate the input data.
            prop: The attribute name on the Context from which to read data.
            args: Optional positional arguments used if the context attribute
                is callable; defaults to an empty tuple.
            kw: Optional keyword name under which to pass validated data to the
                handler; if None, `prop` is used.
        """
        self.schema = schema
        self.prop = prop
        self.args = args or ()
        self.kw = kw

    def apply(self, handler: Callable[[Context, ...], Any]):
        """Wrap a view handler with schema validation against context data.

        The wrapped handler will:
        - Read data from `view.ctx.<prop>`
        - Call it with `args` if it is callable
        - Validate the data using the configured schema
        - Raise HTTPException(400) if validation fails
        - Pass the validated data to the handler via keyword argument `kw`
          (or `prop` if `kw` is not provided)

        Args:
            handler: The view handler function to wrap.

        Returns:
            A callable that enforces schema validation before calling the handler.
        """

        @wraps(handler)
        def wrapper(view: View, *args, **kw: Any):
            ctx = view.ctx

            schema = self.schema
            data = getattr(ctx, self.prop)

            if callable(data):
                data = data(*self.args)

            schema_instance = schema(data=data, context=view.build_ctx())
            is_valid = schema_instance.is_valid()

            if not is_valid:
                raise HTTPException(schema_instance.errors, status_code=400)

            kw.update({self.kw or self.prop: schema_instance.validated_data})

            return handler(view, *args, **kw)

        return wrapper
