import pytest

from webspark.utils.env import env


def test_env_returns_value_when_set():
    key = "MY_VAR"
    value = "my_value"
    with pytest.MonkeyPatch.context() as monkeypatch:
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


def test_env_uses_parser_when_set():
    key = "MY_VAR"
    value = "123"
    with pytest.MonkeyPatch.context() as monkeypatch:
        monkeypatch.setenv(key, value)
        assert env(key, parser=int) == 123


def test_env_parser_not_called_when_not_set():
    key = "MY_VAR"
    default = "default_value"

    def parser(value):
        raise AssertionError("Parser should not be called")

    assert env(key, default=default, parser=parser) == default


def test_env_with_empty_value():
    key = "EMPTY_VAR"
    with pytest.MonkeyPatch.context() as monkeypatch:
        monkeypatch.setenv(key, "")
        assert env(key) == ""


def test_env_with_empty_value_and_parser():
    key = "EMPTY_VAR_PARSED"
    with pytest.MonkeyPatch.context() as monkeypatch:
        monkeypatch.setenv(key, "")
        assert env(key, parser=bool) is False
