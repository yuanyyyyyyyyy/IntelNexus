"""侧栏 UI 冒烟与脱敏辅助。

存在动机：本轮曾出现「函数注解引用未导入的 ``Dict``，模块导入即 NameError」——
core 层单测再全也覆盖不到这条路径（侧栏只在真实运行时才被导入），必须用
import 级冒烟把这类错误挡在 CI 里。
"""
import intelnexus.ui.sidebar as sidebar


def test_sidebar_module_imports():
    """导入级冒烟：注解/导入错误在这里暴露，而不是等用户打开页面才发现。"""
    assert callable(sidebar._render_search_service_settings)
    assert callable(sidebar._run_site_search_trial)


def test_mask_secret_keeps_only_edges():
    assert sidebar._mask_secret("sk-abcdefghijklmnop") == "sk-a****mnop"


def test_mask_secret_short_value_fully_masked():
    """短凭证不得保留首尾各 4 位——那样掩码几乎等于明文。

    Google CSE 的 cx、自挂 Provider 的短 token 都属于这一类。
    """
    assert sidebar._mask_secret("abcd1234") == "****"
    assert sidebar._mask_secret("short") == "****"
    assert sidebar._mask_secret("a" * 12) == "****"


def test_mask_secret_blank():
    assert sidebar._mask_secret("") == ""
    assert sidebar._mask_secret(None) == ""


def test_site_search_masked_empty_when_unset():
    cfg = {"bocha_api_key": "", "brave_api_key": "",
           "google_cse_api_key": "", "google_cse_id": ""}
    assert sidebar._site_search_masked(cfg, "bocha") == ""
    assert sidebar._site_search_masked(cfg, "brave") == ""


def test_site_search_masked_joins_all_credential_fields():
    """多字段 Provider（Google CSE 需 key + cx）要逐项掩码后一并展示。"""
    cfg = {"bocha_api_key": "sk-abcdefghijklmnop",
           "google_cse_api_key": "AIzaSyabcdefghijkl",
           "google_cse_id": "cx-1234567890"}
    assert sidebar._site_search_masked(cfg, "bocha") == "sk-a****mnop"
    masked = sidebar._site_search_masked(cfg, "google_cse")
    assert " / " in masked
    assert "AIzaSyabcdefghijkl" not in masked
    assert "1234567890" not in masked
