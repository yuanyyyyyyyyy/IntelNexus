"""暗网结果标记测试：.onion 判定、徽章渲染、覆盖度统计。"""
from intelnexus.ui.results_detail import _is_onion_item, _onion_badge


def test_is_onion_item_by_link():
    assert _is_onion_item({"link": "http://abc.onion/page"}) is True


def test_is_onion_item_by_url():
    assert _is_onion_item({"url": "http://abc.onion/page"}) is True


def test_is_onion_item_case_insensitive():
    assert _is_onion_item({"link": "http://ABC.ONION/page"}) is True


def test_is_onion_item_rejects_clearnet():
    assert _is_onion_item({"link": "https://ahmia.fi/search"}) is False


def test_is_onion_item_handles_missing_fields():
    assert _is_onion_item({}) is False
    assert _is_onion_item({"link": None}) is False


def test_onion_badge_markup():
    badge = _onion_badge()
    assert 'class="onion-badge"' in badge
    assert "ONION" in badge
