import pytest

from webspark.utils.env import env


def test_env_returns_value_when_set(monkeypatch):
    key = "MY_VAR"
    value = "my_value"
    monkeypatch.setenv(key, value)
    assert env(key) == value


def test_env_returns_default_when_not_set():
    key = "MY_VAR"
    default = "default_value"
    assert env(key, default=default) == default


def test_env_returns_none_when_not_set_and_no_default():
    key = "MY_VAR"
    assert env(key) is None


def test_env_raises_exception_when_not_set_and_raise_exception_is_true():
    key = "MY_VAR"
    with pytest.raises(
        ValueError,
        match=f"Environment variable '{key}' is not set and no default value was provided.",
    ):
        env(key, raise_exception=True)


def test_env_uses_custom_parser_when_set(monkeypatch):
    key = "MY_VAR"
    value = "123"
    monkeypatch.setenv(key, value)
    assert env(key, parser=int) == 123


def test_env_parser_not_called_when_not_set():
    key = "MY_VAR"
    default = "default_value"

    def parser(value):
        raise AssertionError("Parser should not be called")

    assert env(key, default=default, parser=parser) == default


def test_env_with_empty_value(monkeypatch):
    key = "EMPTY_VAR"
    monkeypatch.setenv(key, "")
    assert env(key) == ""


def test_env_returns_string_by_default(monkeypatch):
    key = "BOOL_STRING"
    monkeypatch.setenv(key, "true")
    assert env(key) == "true"


@pytest.mark.parametrize(
    "value, expected",
    [
        ("true", True),
        ("1", True),
        ("yes", True),
        ("y", True),
        ("on", True),
        ("True", True),
        ("YES", True),
        ("false", False),
        ("0", False),
        ("no", False),
        ("n", False),
        ("off", False),
        ("False", False),
        ("NO", False),
        ("", False),
        ("any_other_string", False),
    ],
)
def test_env_with_bool_parser(monkeypatch, value, expected):
    key = "BOOL_VAR"
    monkeypatch.setenv(key, value)
    assert env(key, parser=bool) is expected


def test_env_with_bool_parser_and_default_true(monkeypatch):
    key = "BOOL_VAR"
    monkeypatch.setenv(key, "false")
    assert env(key, default=True, parser=bool) is False


def test_env_with_bool_parser_and_default_when_not_set():
    key = "UNSET_BOOL_VAR"
    assert env(key, default=True, parser=bool) is True
    assert env(key, default=False, parser=bool) is False
