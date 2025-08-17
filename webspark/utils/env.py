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
    value = os.getenv(key)

    if value is None:
        if default is None and raise_exception:
            raise ValueError(
                f"Environment variable '{key}' is not set and no default value was provided."
            )
        return default

    return parser(value) if parser else value
