"""Unit tests for the AI briefing pipeline and analyzer.

无外部依赖：LLM 以 None 注入，各板块走降级展示路径，验证
- analyzer.generate_briefing 的向后兼容 / warnings / 进度回调
- pipeline.run_briefing_pipeline 的采集合并、统计返回、推送隔离
"""

from unittest.mock import patch

# 模拟采集结果（覆盖 AI 动态 / 网络安全 / CVE 三个板块的类目）
MOCK_COLLECTED = {
    "ai_gov_usage": [
        {"title": "Gov adopts AI", "description": "agency deploys assistant",
         "source": "Gov", "published_at": "2026-07-21", "url": "http://gov/x"},
    ],
    "ai_china_narrative": [
        {"title": "China narrative", "description": "official narrative",
         "source": "Xinhua", "published_at": "2026-07-21"},
    ],
    "cyber_vuln": [
        {"title": "CVE-2026-0001", "description": "rce in widget",
         "source": "NVD", "published_at": "2026-07-21"},
    ],
}


class TestBriefingAnalyzer:
    """analyzer.generate_briefing 的单元行为。"""

    def test_backward_compat_returns_str(self):
        """未开启 with_warnings 时返回纯 markdown 字符串（CLI 兼容）。"""
        from ai_briefing.analyzer import AIBriefingAnalyzer
        md = AIBriefingAnalyzer(llm=None).generate_briefing(MOCK_COLLECTED)
        assert isinstance(md, str)
        assert "##" in md

    def test_with_warnings_returns_tuple(self):
        """开启后返回 (markdown, warnings) 且包含降级警告。"""
        from ai_briefing.analyzer import AIBriefingAnalyzer
        md, warnings = AIBriefingAnalyzer(llm=None).generate_briefing(
            MOCK_COLLECTED, with_warnings=True
        )
        assert isinstance(md, str)
        assert isinstance(warnings, list)
        assert any("未加载 LLM" in w for w in warnings)

    def test_empty_data_emits_warnings(self):
        """无数据时 TOP3 与趋势研判应各自告警。"""
        from ai_briefing.analyzer import AIBriefingAnalyzer
        _, warnings = AIBriefingAnalyzer(llm=None).generate_briefing(
            {}, with_warnings=True
        )
        assert any("未采集到任何情报数据" in w for w in warnings)
        assert any("数据不足" in w for w in warnings)

    def test_progress_callback_receives_percent(self):
        """进度回调应收到数值化 percent。"""
        from ai_briefing.analyzer import AIBriefingAnalyzer
        events = []
        AIBriefingAnalyzer(llm=None).generate_briefing(
            MOCK_COLLECTED,
            with_warnings=True,
            on_progress=lambda s, m, p: events.append((s, p)),
        )
        assert any(p is not None for _, p in events)


class TestBriefingPipeline:
    """pipeline.run_briefing_pipeline 的单元行为（外部依赖全 mock）。"""

    @patch("src.config.subscriptions.get_active_subscribers", return_value=[])
    @patch("src.config.briefing_history.get_briefing_history")
    @patch("shared.llm.core.get_llm", return_value=None)
    @patch("ai_briefing.pipeline.AIBriefingCollector")
    def test_pipeline_runs_and_reports(self, mock_collector, mock_get_llm,
                                       mock_history, mock_subs):
        """无 LLM、无订阅者时仍可生成简报并返回统计。"""
        mock_collector.return_value.collect_all_categories.return_value = MOCK_COLLECTED
        mock_history.return_value.save_briefing.return_value = None

        events = []
        result = run_briefing_pipeline(
            model="qwen2.5:7b",
            categories=None,
            push_enabled=False,
            on_progress=lambda s, m, p: events.append((s, p)),
        )

        assert isinstance(result["md"], str)
        assert "##" in result["md"]
        assert result["collected_counts"]["ai_gov_usage"] == 1
        assert result["categories"] == list(MOCK_COLLECTED.keys())
        assert result["pushed"] == 0
        assert isinstance(result["elapsed"], float)
        # 进度百分比应在 [0, 1] 区间，且以 push_skipped(1.0) 收尾
        percents = [p for _, p in events if p is not None]
        assert 0.0 <= min(percents) <= max(percents) <= 1.0
        assert events[-1][0] == "push_skipped"

    @patch("ai_briefing.pipeline.AIBriefingNotifier")
    @patch("src.config.subscriptions.get_active_subscribers",
           return_value=[{"name": "sub1", "email": "a@b.c"}])
    @patch("src.config.briefing_history.get_briefing_history")
    @patch("shared.llm.core.get_llm", return_value=None)
    @patch("ai_briefing.pipeline.AIBriefingCollector")
    def test_pipeline_push_count(self, mock_collector, mock_get_llm,
                                 mock_history, mock_subs, mock_notifier):
        """开启推送且有一个订阅者时，pushed 应计为 1。"""
        mock_collector.return_value.collect_all_categories.return_value = MOCK_COLLECTED
        mock_history.return_value.save_briefing.return_value = None
        mock_notifier.return_value.notify.return_value = {"email": True}

        result = run_briefing_pipeline(
            model="qwen2.5:7b",
            categories=["ai_gov_usage"],
            push_enabled=True,
        )
        assert result["pushed"] == 1
        mock_notifier.return_value.notify.assert_called_once()

    @patch("ai_briefing.pipeline.AIBriefingNotifier")
    @patch("src.config.subscriptions.get_active_subscribers",
           return_value=[{"name": "sub1", "email": "a@b.c"}])
    @patch("src.config.briefing_history.get_briefing_history")
    @patch("shared.llm.core.get_llm", return_value=None)
    @patch("ai_briefing.pipeline.AIBriefingCollector")
    def test_pipeline_push_isolation(self, mock_collector, mock_get_llm,
                                     mock_history, mock_subs, mock_notifier):
        """单个订阅者推送异常不应中断流水线，pushed 仍为 0。"""
        mock_collector.return_value.collect_all_categories.return_value = MOCK_COLLECTED
        mock_history.return_value.save_briefing.return_value = None
        mock_notifier.return_value.notify.side_effect = RuntimeError("smtp down")

        result = run_briefing_pipeline(
            model="qwen2.5:7b",
            categories=["ai_gov_usage"],
            push_enabled=True,
        )
        assert result["pushed"] == 0
        # 简报本身仍生成成功
        assert isinstance(result["md"], str)


def run_briefing_pipeline(*args, **kwargs):  # 延迟导入，避免模块级副作用
    from ai_briefing.pipeline import run_briefing_pipeline as _impl
    return _impl(*args, **kwargs)
