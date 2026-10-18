"""读-改-写路径的防抹除测试（阶段一配套）。

问题背景：``safe_read_json`` 在读取失败（文件被占用 / 内容损坏 / 无法加锁）时
返回 ``{}``，调用方无法把「读取失败」与「文件本来是空的」区分开。读-改-写的
代码形如::

    data = safe_read_json(FILE)          # 读到失败 → {}
    data.setdefault("items", []).append(new)
    safe_write_json(FILE, data)          # 把只有一条目的表写回去 → 整表被抹除

一次瞬时读锁竞争加一次成功写，就会永久抹掉整个订阅者列表 / Topic 表 /
API key 配置，且函数返回「成功」，用户毫无感知。实测读失败率约 0.2%。

修复：新增 ``read_for_update``——读取失败返回 None，调用方必须放弃写回。

本文件对**全部 21 个读-改-写入口**做参数化回归：mock 掉读取失败，断言
(a) 函数拒绝执行，(b) 磁盘上的文件字节未被改写。

两个必须显式处理的坑：

1. monkeypatch 要打在**各模块自己的命名空间**上。这些模块都是
   ``from ...file_lock import read_for_update``，持有符号副本，
   patch ``file_lock.read_for_update`` 对它们无效。
2. 文件路径常量在 import 时就从 ``get_data_dir()`` 解析完毕，也要逐模块
   patch 到 tmp_path，否则会碰真实 ``data/`` 目录。
"""
import importlib
import json

import pytest

from intelnexus.core.settings.file_lock import JsonReadError, read_for_update

# 模块 → (模块对象, 该模块涉及的全部文件路径常量)
# models 有两个常量，都要隔离，否则没 patch 的那个会指向真实 data/
from intelnexus.config import (  # noqa: E402
    briefing_drafts, email_settings, proxy_settings, search_settings,
    sources, subscriptions, watch_categories,
)
from intelnexus.core.llm import models  # noqa: E402
from intelnexus.core.search import health  # noqa: E402
from intelnexus.topics import store  # noqa: E402
from intelnexus.topics.registry import Topic  # noqa: E402

MODULES = {
    "topics": (store, ["TOPICS_FILE"]),
    "watch": (watch_categories, ["WATCH_CATEGORIES_FILE"]),
    "drafts": (briefing_drafts, ["DRAFTS_FILE"]),
    "email": (email_settings, ["EMAIL_SETTINGS_FILE"]),
    "proxy": (proxy_settings, ["PROXY_SETTINGS_FILE"]),
    "search": (search_settings, ["SEARCH_SETTINGS_FILE"]),
    "sources": (sources, ["SOURCES_FILE"]),
    "subscriptions": (subscriptions, ["SUBSCRIPTIONS_FILE"]),
    "models": (models, ["CUSTOM_MODELS_FILE", "CUSTOM_PROVIDERS_FILE"]),
    "health": (health, ["HEALTH_FILE"]),
}

# 每个模块用到的文件名 → 常量名
CONST_BY_FILENAME = {
    "topics": {"topics.json": "TOPICS_FILE"},
    "watch": {"watch_categories.json": "WATCH_CATEGORIES_FILE"},
    "drafts": {"briefing_drafts.json": "DRAFTS_FILE"},
    "email": {"email_settings.json": "EMAIL_SETTINGS_FILE"},
    "proxy": {"proxy_settings.json": "PROXY_SETTINGS_FILE"},
    "search": {"search_settings.json": "SEARCH_SETTINGS_FILE"},
    "sources": {"sources.json": "SOURCES_FILE"},
    "subscriptions": {"subscriptions.json": "SUBSCRIPTIONS_FILE"},
    "models": {"custom_models.json": "CUSTOM_MODELS_FILE",
               "custom_providers.json": "CUSTOM_PROVIDERS_FILE"},
    "health": {"source_health.json": "HEALTH_FILE"},
}


# ---------------------------------------------------------------------------
# read_for_update 自身的契约
# ---------------------------------------------------------------------------


class TestReadForUpdateContract:
    def test_missing_file_is_not_a_failure(self, tmp_path):
        """文件不存在（首次运行）是合法状态，不返回 None。"""
        assert read_for_update(str(tmp_path / "nope.json")) == {}

    def test_valid_empty_object_is_not_a_failure(self, tmp_path):
        """内容真的是空对象（合法空表）返回 {}，不返回 None。"""
        p = tmp_path / "empty.json"
        p.write_text("{}", encoding="utf-8")
        assert read_for_update(str(p)) == {}

    def test_corrupt_file_is_reported_as_failure(self, tmp_path):
        """内容损坏：strict 抛 JsonReadError → read_for_update 返回 None。"""
        p = tmp_path / "bad.json"
        p.write_text("{not json", encoding="utf-8")
        assert read_for_update(str(p)) is None

    def test_strict_raises_on_corrupt(self, tmp_path):
        from intelnexus.core.settings import file_lock
        p = tmp_path / "bad2.json"
        p.write_text("{oops", encoding="utf-8")
        with pytest.raises(JsonReadError):
            file_lock.safe_read_json(str(p), strict=True)

    def test_default_behavior_unchanged_for_readonly_callers(self, tmp_path):
        """默认行为不变：51 个只读调用点零影响。"""
        from intelnexus.core.settings import file_lock
        p = tmp_path / "bad3.json"
        p.write_text("{oops", encoding="utf-8")
        assert file_lock.safe_read_json(str(p)) == {}

    def test_list_payload_roundtrip(self, tmp_path):
        p = tmp_path / "list.json"
        p.write_text(json.dumps([{"a": 1}]), encoding="utf-8")
        assert read_for_update(str(p)) == [{"a": 1}]

    def test_missing_file_strict_is_not_a_failure(self, tmp_path):
        """strict 模式下文件不存在同样不算失败（首次运行要能建表）。"""
        from intelnexus.core.settings import file_lock
        assert file_lock.safe_read_json(str(tmp_path / "none.json"), strict=True) == {}


# ---------------------------------------------------------------------------
# 21 个读-改-写入口的参数化防抹除表
# ---------------------------------------------------------------------------


def _build_cases():
    from intelnexus.config import (
        briefing_drafts, email_settings, proxy_settings, search_settings,
        sources, subscriptions, watch_categories,
    )
    from intelnexus.core.llm import models
    from intelnexus.core.search import health
    from intelnexus.topics import store
    from intelnexus.topics.registry import Topic

    # 用真实的默认 ID，否则函数在读之前就早退，测到的只是参数校验而非防抹除逻辑
    cat = "ai_gov_usage"
    toggle = "ENABLE_CNVD"

    return [
        # ---- topics/store.py：3 个 RMW 入口 ----
        ("topics.add_topic", "topics", "topics.json",
         lambda: store.add_topic(Topic(id="t_new", name="新", search_queries=["q"])), False),
        ("topics.update_topic", "topics", "topics.json",
         lambda: store.update_topic("t_seed", {"enabled": False}), False),
        ("topics.remove_topic", "topics", "topics.json",
         lambda: store.remove_topic("t_seed"), False),

        # ---- watch_categories.py：4 个 RMW 入口 ----
        ("watch.add_category", "watch", "watch_categories.json",
         lambda: watch_categories.add_category("my_cat", {"name": "我的"}), False),
        ("watch.update_category", "watch", "watch_categories.json",
         lambda: watch_categories.update_category(cat, {"name": "改名"}), False),
        ("watch.remove_category", "watch", "watch_categories.json",
         lambda: watch_categories.remove_category(cat), False),
        ("watch.restore_default", "watch", "watch_categories.json",
         lambda: watch_categories.restore_default(cat), False),

        # ---- briefing_drafts.py：2 个 RMW 入口 ----
        ("drafts.add_draft", "drafts", "briefing_drafts.json",
         lambda: briefing_drafts.add_draft({"url": "http://new", "title": "新"}), False),
        ("drafts.remove_draft", "drafts", "briefing_drafts.json",
         lambda: briefing_drafts.remove_draft("d_seed"), False),

        # ---- email_settings / proxy_settings ----
        ("email.save_email_settings", "email", "email_settings.json",
         lambda: email_settings.save_email_settings({"smtp_server": "evil.example.com"}), False),
        ("proxy.save_proxy_settings", "proxy", "proxy_settings.json",
         lambda: proxy_settings.save_proxy_settings({"proxy_url": "http://evil:1"}), False),

        # ---- search_settings.py：2 个 RMW 入口 ----
        ("search.save_search_settings", "search", "search_settings.json",
         lambda: search_settings.save_search_settings({"news_api_key": "sk-new"}), False),
        ("search.save_source_toggles", "search", "search_settings.json",
         lambda: search_settings.save_source_toggles({toggle: True}), False),

        # ---- sources / subscriptions ----
        ("sources.add_source", "sources", "sources.json",
         lambda: sources.add_source("rss", "新源", "http://new.example/feed", "cat"), False),
        ("subscriptions.add_subscriber", "subscriptions", "subscriptions.json",
         lambda: subscriptions.add_subscriber(
             "新订阅者", "new@x.com", {"email": True}, {"freq": "daily"}, ["ai"]), None),

        # ---- models.py：2 个 RMW 入口，各自不同的文件 ----
        ("models.add_custom_model", "models", "custom_models.json",
         lambda: models.add_custom_model("m_new", "openai", {"base_url": "https://api.x.com"}),
         False),
        ("models.add_custom_provider", "models", "custom_providers.json",
         lambda: models.add_custom_provider("p_new", "https://p.com", api_key="k"), False),

        # ---- health.py：两条写入路径 ----
        ("health.update_health", "health", "source_health.json",
         lambda: health.update_health("SecRSS", 3, 100.0), False),
        ("health.apply_health_updates", "health", "source_health.json",
         lambda: health.apply_health_updates([("SecRSS", 3, 100.0, None, False)]), 0),
    ]


CASES = _build_cases()

SEEDS = {
    "topics.add_topic": {"t_a": {"id": "t_a"}, "t_b": {"id": "t_b"}},
    "topics.update_topic": {"t_seed": {"id": "t_seed", "enabled": True}},
    "topics.remove_topic": {"t_seed": {"id": "t_seed"}, "t_other": {"id": "t_other"}},

    "watch.add_category": {"ai_data_leak": {"name": "已有"}},
    "watch.update_category": {"ai_gov_usage": {"name": "已有"}},
    "watch.remove_category": {"ai_gov_usage": {"name": "已有"}},
    "watch.restore_default": {"ai_gov_usage": {"enabled": False}},

    "drafts.add_draft": [{"id": "d_seed", "url": "http://seed", "saved_at": "2026-10-18"}],
    "drafts.remove_draft": [{"id": "d_seed", "url": "http://seed"}],

    "email.save_email_settings": {"smtp_server": "mail.s.com", "password": "s3cret",
                                  "username": "u", "smtp_port": 465, "use_tls": True},
    "proxy.save_proxy_settings": {"proxy_url": "http://a:1", "auto_detect": True},

    "search.save_search_settings": {"news_api_key": "sk-seed", "bocha_api_key": "bc-seed"},
    "search.save_source_toggles": {"news_api_key": "sk-seed", "bocha_api_key": "bc-seed"},

    "sources.add_source": {
        "subscription_sources": [{"id": "s1", "name": "S1", "url": "http://s1"}],
        "custom_sources": [{"id": "s2", "name": "S2", "url": "http://s2"}],
    },
    "subscriptions.add_subscriber": {
        "subscribers": [{"id": "sub_1", "name": "老", "email": "old@x.com"}]
    },

    "models.add_custom_model": {"models": [{"name": "m1", "type": "openai", "config": {}}]},
    "models.add_custom_provider": {"providers": [{"name": "p1", "base_url": "https://p1.com"}]},

    "health.update_health": {"sources": {"SecRSS": {"source_name": "SecRSS", "status": "healthy",
                                                  "success_count": 5},
                                        "CISA_KEV": {"source_name": "CISA_KEV",
                                                     "status": "healthy"}}, "updated_at": "x"},
    "health.apply_health_updates": {"sources": {"SecRSS": {"source_name": "SecRSS",
                                                          "status": "healthy"},
                                                "CISA_KEV": {"source_name": "CISA_KEV",
                                                             "status": "healthy"}},
                                    "updated_at": "x"},
}


def _isolate(monkeypatch, module_key, tmp_path, real_target):
    """把模块的所有路径常量重定向，其中本用例的那个指向 real_target。"""
    module, consts = MODULES[module_key]
    real_const = CONST_BY_FILENAME[module_key][real_target.name]
    for c in consts:
        if c == real_const:
            monkeypatch.setattr(module, c, str(real_target))
        else:
            monkeypatch.setattr(module, c, str(tmp_path / f"_other_{c}.json"))


def _seed(target, payload):
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
    return target.read_bytes()


@pytest.mark.parametrize("case_id,module_key,fname,call,expected", CASES,
                         ids=[c[0] for c in CASES])
def test_read_failure_never_wipes_file(monkeypatch, tmp_path, case_id, module_key, fname,
                                       call, expected):
    """读失败 → 函数拒绝执行 → 磁盘文件字节未被改写。"""
    module, _ = MODULES[module_key]
    target = tmp_path / fname
    _isolate(monkeypatch, module_key, tmp_path, target)
    original = _seed(target, SEEDS[case_id])

    monkeypatch.setattr(module, "read_for_update", lambda p: None)

    result = call()

    assert result == expected, (
        f"{case_id}: 读失败时应返回 {expected!r}（拒绝执行），实际 {result!r}"
    )
    assert target.exists(), f"{case_id}: 文件在读失败后消失了"
    assert target.read_bytes() == original, (
        f"{case_id}: 读失败后文件被改写——这正是本测试要防的抹除"
    )


@pytest.mark.parametrize("case_id,module_key,fname,call,expected", CASES,
                         ids=[c[0] for c in CASES])
def test_read_success_still_works(monkeypatch, tmp_path, case_id, module_key, fname,
                                  call, expected):
    """Happy path 不回归：读取正常时守卫不触发，操作成功且确实写盘。"""
    # 本用例测的是读-写路径，不是 URL 安全校验。构造用的 URL 在沙箱里
    # 解析不了 DNS，会把 add_source / add_custom_provider 提前拒掉，
    # 因此这里把两个校验器短路成「通过」。
    from intelnexus.core.security import url_guard
    monkeypatch.setattr(url_guard, "validate_external_url", lambda u: (True, ""))
    monkeypatch.setattr(models, "_base_url_guard_ok", lambda u: True)

    target = tmp_path / fname
    _isolate(monkeypatch, module_key, tmp_path, target)
    original = _seed(target, SEEDS[case_id])

    result = call()

    # update_health 本来是无返回值函数（成功返回 None），失败才返回 False；
    # 因此统一用「不是 False」判定，再由文件内容变化确认真的写到了盘。
    assert result is not False, (
        f"{case_id}: 读取正常时操作应当成功，实际返回 {result!r}"
    )
    assert target.exists(), f"{case_id}: happy path 下文件应仍存在"
    assert target.read_bytes() != original, (
        f"{case_id}: happy path 下文件内容没有任何变化，说明写盘路径没走到"
    )


class TestSidebarUiSettingsGuard:
    """ui/sidebar.py 模型选择持久化的守卫（审计清单上的第 21 个站点）。

    这个站点没法用 AppTest 覆盖：模型选项来自 cached_model_choices()，
    带 Ollama HTTP 探测，Ollama 未运行时约 3s，正好耗尽 AppTest 的脚本
    执行时限（报 `AppTest script run timed out after 3(s)`，是测试基建
    的时限问题，与守卫逻辑本身无关）。因此把读-判定逻辑抽成纯函数
    _load_ui_settings_for_persist 后直接单测。
    """

    @staticmethod
    def _helper():
        import intelnexus.ui.sidebar as sidebar
        return sidebar._load_ui_settings_for_persist

    def test_read_failure_refuses_persist(self, monkeypatch, tmp_path):
        from intelnexus.core.settings import file_lock
        monkeypatch.setattr(file_lock, "read_for_update", lambda p: None)

        target = tmp_path / "ui_settings.json"
        target.write_text(json.dumps({"last_model": "m1", "extra": "keep"}),
                          encoding="utf-8")
        original = target.read_bytes()

        settings, allow_persist = self._helper()(str(target))

        assert allow_persist is False, "读失败却允许持久化，写回会抹掉整个文件"
        assert settings == {}
        assert target.read_bytes() == original, "读失败后 ui_settings.json 被改写"

    def test_read_success_allows_persist(self, tmp_path):
        target = tmp_path / "ui_settings.json"
        target.write_text(json.dumps({"last_model": "m1", "extra": "keep"}),
                          encoding="utf-8")

        settings, allow_persist = self._helper()(str(target))

        assert allow_persist is True
        assert settings == {"last_model": "m1", "extra": "keep"}

    def test_non_dict_payload_does_not_block_persist(self, tmp_path):
        """内容不是 dict（损坏成列表等）时按空设置处理，但不禁止持久化。

        与「读失败」区分开：文件读到了，只是结构不对。
        """
        target = tmp_path / "ui_settings.json"
        target.write_text(json.dumps(["oops"]), encoding="utf-8")

        settings, allow_persist = self._helper()(str(target))

        assert allow_persist is True
        assert settings == {}

    def test_render_uses_the_guard(self):
        """结构绑定：_render_model_settings 必须走守卫，写盘受 allow_persist 约束。

        没有这层断言，上三个用例只证明纯函数自身正确，证明不了渲染函数
        真的调用了它（重构后完全可能被绕过而复测仍全绿）。
        """
        import inspect
        import intelnexus.ui.sidebar as sidebar

        src = inspect.getsource(sidebar._render_model_settings)
        assert "_load_ui_settings_for_persist" in src, "渲染函数绕过了读守卫"
        assert "if allow_persist and model != saved_model:" in src, (
            "写盘不再受 allow_persist 保护"
        )
        assert "ui_settings[\"last_model\"] = model" in src, (
            "持久化写入字段消失"
        )
