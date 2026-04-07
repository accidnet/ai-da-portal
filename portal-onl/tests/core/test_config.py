from core.config import get_settings


def test_get_settings_loads_dev_env_file(tmp_path, monkeypatch):
    (tmp_path / ".env.dev").write_text(
        "ENVIRONMENT=dev\nLOG_LEVEL=DEBUG\n", encoding="utf-8"
    )
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("PORTAL_ENV", "dev")
    get_settings.cache_clear()

    settings = get_settings()

    assert settings.environment == "dev"
    assert settings.log_level == "DEBUG"
    get_settings.cache_clear()
