"""站内检索源的去噪：非笔记黑名单 + 与 web 对齐的相关性过滤 + 过滤观测。

审计依据（2026-09-15 实测）：小红书试搜 10 条结果中，4 条是非笔记页面
（``pgy.xiaohongshu.com`` 商业平台 ×2、``/explore`` 索引页、``ipp.xiaohongshu.com``
登录页），其余 6 条虽是真实笔记但内容与查询无关（生活吐槽、显卡科普等），
经项目自带评分器打分 **10/10 全部 0.0 分**，低于阈值 0.3。

因此本文件的覆盖目标：
- 黑名单只拦**已知非笔记**页面（失败模式是漏掉个别垃圾，可接受）；
  不做路径白名单（失败模式是误杀整类笔记，不可接受）。
- 相关性过滤与 web 源共用同一阈值常量，避免两处口径漂移。
- 「后端返回 N 条 → 过滤后 M 条」必须可观测，否则「过滤生效」会被误判为
  「源坏了」。
"""
import pytest

from intelnexus.core.search import RELEVANCE_THRESHOLD
from intelnexus.core.search.sources.site_scoped_source import SiteScopedSource


class _StubBackend:
    name = "Stub"

    def __init__(self, rows=None, error=None):
        self.rows = list(rows or [])
        self.error = error
        self.calls = []

    def is_configured(self):
        return True

    def search(self, query, domain, max_results=10):
        self.calls.append((query, domain, max_results))
        if self.error is not None:
            raise self.error
        return list(self.rows)


def _row(url, title="T", description="d"):
    return {"title": title, "url": url, "description": description,
            "source": "Stub"}


def _src(rows, **over):
    kwargs = dict(name="Xhs", domains=("xiaohongshu.com",),
                  allowed_hosts=("xiaohongshu.com",),
                  backend=_StubBackend(rows))
    kwargs.update(over)
    return SiteScopedSource(**kwargs)


XHS_NOTE = "https://www.xiaohongshu.com/explore/64c26710000000000a018941"
PGY = "https://pgy.xiaohongshu.com/"
IPP = "https://ipp.xiaohongshu.com/mobile?from=/login"
INDEX_ROOT = "https://www.xiaohongshu.com/"
INDEX_EXPLORE = "https://www.xiaohongshu.com/explore"


# ---------------------------------------------------------------------------
# 阈值常量：web 源与站内源共用同一口径
# ---------------------------------------------------------------------------

def test_relevance_threshold_is_shared_constant():
    """阈值必须是单一来源：否则 web 源与站内源各写一份，将来必然漂移。"""
    assert RELEVANCE_THRESHOLD == 0.3


def test_relevance_detail_uses_shared_threshold():
    """契约守卫：评分器的通过判定必须引用该常量（改常量即改两处行为）。"""
    from intelnexus.core.search import relevance_detail

    hit = relevance_detail({"title": "数据泄露应急响应笔记", "description": "d",
                            "url": XHS_NOTE}, "数据泄露")
    miss = relevance_detail({"title": "绝了啊啊啊啊啊啊", "description": "d",
                             "url": XHS_NOTE}, "数据泄露")

    assert hit["passed"] is True
    assert miss["passed"] is False
    assert hit["total"] >= RELEVANCE_THRESHOLD > miss["total"]


# ---------------------------------------------------------------------------
# 非笔记黑名单（host + path）
# ---------------------------------------------------------------------------

def test_blocked_host_filters_commercial_and_login_pages():
    # 噪声行**必须用与查询相关的标题**：否则它们会被相关性过滤掉，黑名单即使
    # 完全失效，本用例也会通过（假阳性）—— 那样就测不出黑名单有没有生效。
    src = _src([_row(PGY, title="数据泄露"), _row(IPP, title="数据泄露"),
                _row(XHS_NOTE, title="数据泄露应急响应")],
               blocked_hosts=("pgy.xiaohongshu.com", "ipp.xiaohongshu.com"))

    out = src.search("数据泄露")

    assert [r["url"] for r in out] == [XHS_NOTE]


def test_blocked_path_filters_index_pages_without_note_id():
    src = _src([_row(INDEX_ROOT, title="数据泄露"),
                _row(INDEX_EXPLORE, title="数据泄露"),
                _row(XHS_NOTE, title="数据泄露应急响应")],
               blocked_paths=("/", "/explore", "/explore/"))

    out = src.search("数据泄露")

    assert [r["url"] for r in out] == [XHS_NOTE]


def test_blocked_path_matches_with_trailing_slash_normalized():
    """``/explore/`` 与 ``/explore`` 视为同一路径（URL 常见形态差异）。"""
    src = _src([_row("https://www.xiaohongshu.com/explore/", title="数据泄露"),
                _row(XHS_NOTE, title="数据泄露应急响应")],
               blocked_paths=("/explore",))

    assert [r["url"] for r in src.search("数据泄露")] == [XHS_NOTE]


def test_no_blacklist_by_default_keeps_non_note_pages():
    """默认不配置黑名单时，非笔记页面**不被黑名单拦**（它们只受相关性过滤影响）。

    这是「默认行为不变」的真正护栏：三条标题都与查询相关，故应全部保留。
    若把黑名单写死进通用逻辑，本用例会立刻失败。
    """
    src = _src([_row(PGY, title="数据泄露"), _row(INDEX_EXPLORE, title="数据泄露"),
                _row(XHS_NOTE, title="数据泄露应急响应")])

    out = src.search("数据泄露")

    assert [r["url"] for r in out] == [PGY, INDEX_EXPLORE, XHS_NOTE]
    assert src.last_filter_stats["raw"] == 3


# ---------------------------------------------------------------------------
# 相关性过滤（与 web 源对齐）
# ---------------------------------------------------------------------------

def test_irrelevant_notes_are_dropped_by_relevance():
    """实测噪声：与查询无关的笔记不得原样进入结果集。"""
    src = _src([_row(XHS_NOTE, title="绝了啊啊啊啊啊啊"),
                _row("https://www.xiaohongshu.com/explore/aaa",
                     title="电脑知识小白也能看懂的显卡篇")])

    assert src.search("数据泄露") == []


def test_relevant_note_is_kept():
    src = _src([_row(XHS_NOTE, title="数据泄露应急响应笔记",
                     description="分享一次数据泄露的处置过程")])

    out = src.search("数据泄露")

    assert len(out) == 1
    assert out[0]["url"] == XHS_NOTE


def test_query_without_tokens_does_not_kill_results():
    """沿用 relevance_detail 语义：无关键词时不误杀（不得覆写该行为）。"""
    src = _src([_row(XHS_NOTE, title="任意标题")])

    assert len(src.search("，。")) == 1


# ---------------------------------------------------------------------------
# 过滤观测（raw / kept / dropped）
# ---------------------------------------------------------------------------

def test_filter_stats_reports_raw_kept_dropped():
    src = _src([_row(XHS_NOTE, title="数据泄露应急响应"),
                _row(PGY, title="数据泄露"),
                _row("https://www.xiaohongshu.com/explore/bbb",
                     title="绝了啊啊啊")],
               blocked_hosts=("pgy.xiaohongshu.com",))

    out = src.search("数据泄露")

    stats = src.last_filter_stats
    assert stats["raw"] == 3        # 后端返回 3 条
    assert stats["kept"] == 1       # 过滤后只剩 1 条
    assert stats["dropped"] == 2
    assert len(out) == stats["kept"]


def test_filter_stats_zero_raw_when_backend_returns_nothing():
    """后端零返回：raw=0，用于与「过滤后为 0」区分（排障方向完全不同）。"""
    src = _src([])

    src.search("数据泄露")

    assert src.last_filter_stats == {"raw": 0, "kept": 0, "dropped": 0}


@pytest.mark.parametrize("url,expected", [
    # 已知非笔记页面 → 拦
    ("https://pgy.xiaohongshu.com/", True),
    ("https://ipp.xiaohongshu.com/mobile?from=/login", True),
    ("https://www.xiaohongshu.com/", True),
    ("https://www.xiaohongshu.com", True),      # 空路径按根路径处理
    ("https://www.xiaohongshu.com/explore", True),
    ("https://www.xiaohongshu.com/explore/", True),
    # 笔记与其它站内页 → 不得误杀（用黑名单而非路径白名单的意义所在）
    ("https://www.xiaohongshu.com/explore/64c2", False),
    ("https://www.xiaohongshu.com/discovery/item/5c30", False),
    ("https://www.xiaohongshu.com/user/profile/abc", False),
    ("https://www.xiaohongshu.com/search_result?kw=x", False),
    # userinfo 形态：hostname 剥离 userinfo，不得被误判为黑名单主机
    ("https://evil@www.xiaohongshu.com/explore/1", False),
])
def test_is_noise_url_forms(url, expected):
    """直接单测 ``is_noise``：只拦已知非笔记页，笔记形态一律放行。"""
    src = _src([], blocked_hosts=("pgy.xiaohongshu.com", "ipp.xiaohongshu.com"),
               blocked_paths=("/", "/explore"))

    assert src.is_noise(url) is expected


def test_is_noise_false_when_no_blacklist():
    """未配置黑名单时恒为 False（「默认行为不变」的第二道护栏）。"""
    src = _src([])

    assert src.is_noise(PGY) is False
    assert src.is_noise(INDEX_EXPLORE) is False


def test_blocked_hosts_are_normalized():
    """黑名单主机大小写/首尾空白归一化（用户手填配置时常见）。"""
    src = _src([], blocked_hosts=(" PGY.XiaoHongShu.com ",))

    assert src.is_noise("https://pgy.xiaohongshu.com/") is True


def test_is_noise_does_not_raise_on_malformed_input():
    """畸形输入不得抛异常（过滤路径上任何异常都会让整源失效）。"""
    src = _src([], blocked_hosts=("pgy.xiaohongshu.com",),
               blocked_paths=("/", "/explore"))

    assert src.is_noise("") in (True, False)
    assert src.is_noise("not a url") is False
    assert src.is_noise(None) in (True, False)


def test_filter_stats_cleared_on_blank_query():
    """空查询不检索：统计必须归零，避免残留上一轮数字误导。"""
    src = _src([_row(XHS_NOTE, title="数据泄露应急响应")])
    src.search("数据泄露")
    assert src.last_filter_stats["raw"] == 1

    src.search("   ")

    assert src.last_filter_stats == {"raw": 0, "kept": 0, "dropped": 0}
