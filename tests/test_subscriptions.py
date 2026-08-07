"""Subscription config tests: CRUD, active filtering, last_sent update."""
import json

import pytest

from intelnexus.config import subscriptions as subs


@pytest.fixture
def isolated_subs(tmp_path, monkeypatch):
    f = tmp_path / "subscriptions.json"
    monkeypatch.setattr(subs, "SUBSCRIPTIONS_FILE", str(f))
    # 初始化为空
    f.write_text(json.dumps({"subscribers": []}), encoding="utf-8")
    return str(f)


def test_add_subscriber_success(isolated_subs):
    ok = subs.add_subscriber(
        name="Alice", email="alice@example.com",
        channels={"email": True}, schedule={"enabled": True, "time": "09:00"},
        categories=["security", "ai"])
    assert ok is True
    data = json.loads(open(isolated_subs, encoding="utf-8").read())
    assert len(data["subscribers"]) == 1
    sub = data["subscribers"][0]
    assert sub["name"] == "Alice"
    assert sub["email"] == "alice@example.com"
    assert sub["last_sent"] is None
    assert sub["id"].startswith("sub_")


def test_add_subscriber_requires_name_and_email(isolated_subs):
    assert subs.add_subscriber("", "x@y.com", {}, {}, []) is False
    assert subs.add_subscriber("Bob", "", {}, {}, []) is False
    assert subs.add_subscriber("Bob", "b@y.com", {}, {}, []) is True


def test_get_all_and_get_subscriber(isolated_subs):
    subs.add_subscriber("Bob", "b@y.com", {}, {"enabled": False}, ["ai"])
    sub = subs.get_all_subscribers()[0]
    fetched = subs.get_subscriber(sub["id"])
    assert fetched["name"] == "Bob"
    assert subs.get_subscriber("nonexistent") is None


def test_remove_subscriber(isolated_subs):
    subs.add_subscriber("Carol", "c@y.com", {}, {"enabled": True}, [])
    sid = subs.get_all_subscribers()[0]["id"]
    assert subs.remove_subscriber(sid) is True
    assert subs.get_all_subscribers() == []
    # 删除不存在的返回 False
    assert subs.remove_subscriber(sid) is False


def test_update_subscriber(isolated_subs):
    subs.add_subscriber("Dave", "d@y.com", {}, {"enabled": False}, ["ai"])
    sid = subs.get_all_subscribers()[0]["id"]
    assert subs.update_subscriber(sid, {"email": "new@y.com"}) is True
    updated = subs.get_subscriber(sid)
    assert updated["email"] == "new@y.com"
    # 更新不存在的返回 False
    assert subs.update_subscriber("nope", {"email": "x"}) is False


def test_update_last_sent(isolated_subs):
    subs.add_subscriber("Eve", "e@y.com", {}, {"enabled": True}, [])
    sid = subs.get_all_subscribers()[0]["id"]
    assert subs.update_last_sent(sid) is True
    assert subs.get_subscriber(sid)["last_sent"] is not None


def test_get_active_subscribers_filters_enabled(isolated_subs):
    subs.add_subscriber("Active", "a@y.com", {}, {"enabled": True}, [])
    subs.add_subscriber("Inactive", "i@y.com", {}, {"enabled": False}, [])
    active = subs.get_active_subscribers()
    assert len(active) == 1
    assert active[0]["name"] == "Active"


def test_get_subscribers_by_category(isolated_subs):
    subs.add_subscriber("Sec", "s@y.com", {}, {}, ["security"])
    subs.add_subscriber("AI", "a@y.com", {}, {}, ["ai"])
    sec = subs.get_subscribers_by_category("security")
    assert len(sec) == 1 and sec[0]["name"] == "Sec"
    both = subs.get_subscribers_by_category("ai")
    assert len(both) == 1 and both[0]["name"] == "AI"
