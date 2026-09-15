"""search_settings 配置读写单测：聚焦站内检索后端字段（Provider / Key）。

覆盖：默认值、环境变量兜底、文件优先于环境变量、写入白名单、
占位符（your_xxx）视为未配置、类型化 getter。
"""
import json

import pytest

from intelnexus.config import search_settings as ss

_NEW_KEYS = ("site_search_provider", "bocha_api_key", "google_cse_api_key",
             "google_cse_id", "brave_api_key")
_ENV_NAMES = ("SITE_SEARCH_PROVIDER", "BOCHA_API_KEY", "GOOGLE_CSE_API_KEY",
              "GOOGLE_CSE_ID", "BRAVE_API_KEY", "NEWS_API_KEY")


@pytest.fixture
def tmp_settings(tmp_path, monkeypatch):
    """把配置文件指向临时目录，并清空相关环境变量，保证用例隔离。"""
    path = tmp_path / "search_settings.json"
    monkeypatch.setattr(ss, "SEARCH_SETTINGS_FILE", str(path))
    for env in _ENV_NAMES:
        monkeypatch.delenv(env, raising=False)
    return path


def test_defaults_include_site_search_fields(tmp_settings):
    cfg = ss.get_search_settings()
    for key in _NEW_KEYS:
        assert key in cfg
    assert cfg["site_search_provider"] == "auto"
    assert cfg["google_cse_api_key"] == ""
    assert cfg["google_cse_id"] == ""
    assert cfg["brave_api_key"] == ""


def test_env_vars_are_picked_up(tmp_settings, monkeypatch):
    monkeypatch.setenv("GOOGLE_CSE_API_KEY", "gk")
    monkeypatch.setenv("GOOGLE_CSE_ID", "gcx")
    monkeypatch.setenv("BRAVE_API_KEY", "bk")
    monkeypatch.setenv("SITE_SEARCH_PROVIDER", "brave")

    cfg = ss.get_search_settings()

    assert cfg["google_cse_api_key"] == "gk"
    assert cfg["google_cse_id"] == "gcx"
    assert cfg["brave_api_key"] == "bk"
    assert cfg["site_search_provider"] == "brave"


def test_file_overrides_env(tmp_settings, monkeypatch):
    monkeypatch.setenv("BRAVE_API_KEY", "from_env")
    tmp_settings.write_text(json.dumps({"brave_api_key": "from_file"}),
                            encoding="utf-8")
    assert ss.get_search_settings()["brave_api_key"] == "from_file"


def test_save_search_settings_accepts_new_fields(tmp_settings):
    assert ss.save_search_settings({"google_cse_api_key": "gk",
                                    "google_cse_id": "gcx"}) is True
    stored = json.loads(tmp_settings.read_text(encoding="utf-8"))
    assert stored["google_cse_api_key"] == "gk"
    assert stored["google_cse_id"] == "gcx"
    assert ss.get_search_settings()["google_cse_api_key"] == "gk"


def test_save_search_settings_rejects_unknown_field(tmp_settings):
    assert ss.save_search_settings({"not_a_declared_field": "x"}) is False
    assert not tmp_settings.exists()


def test_placeholder_values_treated_as_unconfigured(tmp_settings, monkeypatch):
    monkeypatch.setenv("GOOGLE_CSE_API_KEY", "your_google_key_here")
    assert ss.get_search_settings()["google_cse_api_key"] == ""


def test_get_site_search_config_typed_getter(tmp_settings, monkeypatch):
    monkeypatch.setenv("BRAVE_API_KEY", "bk")
    cfg = ss.get_site_search_config()
    assert set(cfg) == set(_NEW_KEYS)
    assert cfg["brave_api_key"] == "bk"
    assert cfg["site_search_provider"] == "auto"
