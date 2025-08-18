import os
from collections.abc import Callable
from typing import Any, TypeVar, overload

T = TypeVar("T")
U = TypeVar("U")


@overload
def env(
    key: str, default: T, parser: Callable[[str], U], *, raise_exception: bool = False
) -> U: ...


@overload
def env(
    key: str, parser: Callable[[str], U], *, raise_exception: bool = False
) -> U | None: ...


@overload
def env(key: str, default: T, *, raise_exception: bool = False) -> T | str: ...


@overload
def env(key: str, *, raise_exception: bool = False) -> str | None: ...


def env(
    key: str,
    default: Any = None,
    parser: Callable[[str], Any] = None,
    *,
    raise_exception: bool = False,
) -> Any:
    """
    Retrieves and parses an environment variable.

    This function provides a convenient way to access environment variables,
    with options for default values, custom parsing, and robust boolean casting.

    Args:
        key: The name of the environment variable.
        default: The default value to return if the variable is not set.
                 If `None` and the variable is not set, `None` is returned.
        parser: A callable used to parse the environment variable's string value.
                If the parser is `bool`, the function performs a smart conversion,
                treating "true", "1", "yes", "y", and "on" (case-insensitive) as `True`,
                and any other non-empty string as `False`.
        raise_exception: If `True`, a `ValueError` is raised if the environment
                         variable is not set and no default value is provided.

    Returns:
        The parsed value of the environment variable, the default value, or `None`.

    Raises:
        ValueError: If `raise_exception` is `True` and the environment variable
                    is not set and no default is provided.

    Example:
        >>> os.environ["DEBUG"] = "true"
        >>> env("DEBUG", parser=bool)
        True

        >>> os.environ["PORT"] = "8080"
        >>> env("PORT", default=8000, parser=int)
        8080

        >>> env("DATABASE_URL", "sqlite:///default.db")
        "sqlite:///default.db"

        >>> env("SECRET_KEY", raise_exception=True)
        # Raises ValueError if SECRET_KEY is not set
    """
    value = os.getenv(key)

    if value is None:
        if default is None and raise_exception:
            raise ValueError(
                f"Environment variable '{key}' is not set and no default value was provided."
            )
        return default

    if parser is bool:
        return value.lower() in ("true", "1", "yes", "y", "on")

    if parser:
        return parser(value)

    return value
