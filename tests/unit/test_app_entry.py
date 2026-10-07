import importlib

import pytest


@pytest.fixture(autouse=True)
def restore_settings(monkeypatch):
    """These tests reload src.config.settings with different env vars; put it back after."""
    yield
    monkeypatch.undo()
    import src.config.settings as module

    importlib.reload(module)


def test_app_exits_with_a_clear_message_when_the_key_is_missing(monkeypatch):
    import app

    monkeypatch.setattr(app.settings, "openai_api_key", "")
    with pytest.raises(SystemExit) as exc:
        app.main()
    assert "OPENAI_API_KEY" in str(exc.value) and ".env.example" in str(exc.value)


def settings_with(monkeypatch, **env):
    for name in ("PORT", "APP_PORT"):
        monkeypatch.delenv(name, raising=False)
    for name, value in env.items():
        monkeypatch.setenv(name, value)
    import src.config.settings as module

    return importlib.reload(module).settings


def test_port_defaults_to_7860(monkeypatch):
    assert settings_with(monkeypatch).port == 7860


def test_port_variable_is_used(monkeypatch):
    assert settings_with(monkeypatch, PORT="8123").port == 8123


def test_app_port_still_works_as_a_fallback(monkeypatch):
    assert settings_with(monkeypatch, APP_PORT="9000").port == 9000


def test_port_wins_over_app_port(monkeypatch):
    assert settings_with(monkeypatch, PORT="8123", APP_PORT="9000").port == 8123


def test_temperature_defaults_to_zero(monkeypatch):
    monkeypatch.delenv("TEMPERATURE", raising=False)
    import src.config.settings as module

    assert importlib.reload(module).settings.temperature == 0.0
