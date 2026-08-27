"""Tests for the search pipeline fixes: preflight, embedder timeout, partial rendering."""

from unittest.mock import patch, MagicMock


# ============================================================
# Test: zero-results failure judgment (_zero_results_is_failure)
# ============================================================

class TestZeroResultsIsFailure:
    """纯函数分支覆盖：含 ok 源不判失败；全非 ok 判失败；空统计不判失败。"""

    def test_ok_source_not_failure(self):
        from intelnexus.ui.search_worker import _zero_results_is_failure
        stats = {"Web": {"status": "ok", "count": 3},
                 "News": {"status": "timeout", "count": 0}}
        assert _zero_results_is_failure(stats) is False

    def test_ok_with_zero_count_not_failure(self):
        from intelnexus.ui.search_worker import _zero_results_is_failure
        stats = {"Web": {"status": "ok", "count": 0}}
        assert _zero_results_is_failure(stats) is False

    def test_error_and_timeout_only_is_failure(self):
        from intelnexus.ui.search_worker import _zero_results_is_failure
        stats = {"Web": {"status": "error", "count": 0},
                 "News": {"status": "timeout", "count": 0}}
        assert _zero_results_is_failure(stats) is True

    def test_no_proxy_only_is_failure(self):
        from intelnexus.ui.search_worker import _zero_results_is_failure
        stats = {"DarkWeb": {"status": "no_proxy", "count": 0}}
        assert _zero_results_is_failure(stats) is True

    def test_empty_stats_not_failure(self):
        from intelnexus.ui.search_worker import _zero_results_is_failure
        assert _zero_results_is_failure({}) is False

    def test_none_stats_not_failure(self):
        from intelnexus.ui.search_worker import _zero_results_is_failure
        assert _zero_results_is_failure(None) is False


# ============================================================
# Test: vision model detection
# ============================================================

class TestVisionModelDetection:
    def test_detects_llava(self):
        from intelnexus.core.llm.utils import is_vision_model
        assert is_vision_model("llava:7b") is True

    def test_detects_moondream(self):
        from intelnexus.core.llm.utils import is_vision_model
        assert is_vision_model("moondream:1.8b") is True

    def test_text_model_not_vision(self):
        from intelnexus.core.llm.utils import is_vision_model
        assert is_vision_model("qwen2.5:7b") is False
        assert is_vision_model("llama3.1:8b") is False


# ============================================================
# Test: Ollama preflight check
# ============================================================

class TestOllamaPreflight:
    @patch("intelnexus.core.llm.utils._get_ollama_base_url", return_value="http://127.0.0.1:11434")
    def test_missing_base_url(self, mock_base):
        from intelnexus.core.llm.utils import check_ollama_model_available
        mock_base.return_value = ""
        ok, msg = check_ollama_model_available("qwen2.5:7b")
        assert ok is False
        assert msg

    @patch("intelnexus.core.llm.utils._get_ollama_base_url", return_value="http://127.0.0.1:11434")
    def test_connection_error(self, mock_base):
        import requests
        from intelnexus.core.llm.utils import check_ollama_model_available
        with patch("intelnexus.core.llm.utils.requests.get",
                   side_effect=requests.exceptions.ConnectionError()):
            ok, msg = check_ollama_model_available("qwen2.5:7b", timeout=2.0)
        assert ok is False
        assert "Ollama" in msg

    @patch("intelnexus.core.llm.utils._get_ollama_base_url", return_value="http://127.0.0.1:11434")
    def test_unknown_model(self, mock_base):
        from intelnexus.core.llm.utils import check_ollama_model_available
        fake_resp = MagicMock()
        fake_resp.json.return_value = {"models": [{"name": "qwen2.5:7b"}]}
        with patch("intelnexus.core.llm.utils.requests.get", return_value=fake_resp):
            ok, msg = check_ollama_model_available("llama3.1:8b", timeout=2.0)
        assert ok is False
        assert "未找到" in msg

    @patch("intelnexus.core.llm.utils._get_ollama_base_url", return_value="http://127.0.0.1:11434")
    def test_model_available(self, mock_base):
        from intelnexus.core.llm.utils import check_ollama_model_available
        fake_resp = MagicMock()
        fake_resp.json.return_value = {"models": [{"name": "qwen2.5:7b"}, {"name": "llava:7b"}]}
        with patch("intelnexus.core.llm.utils.requests.get", return_value=fake_resp):
            ok, msg = check_ollama_model_available("qwen2.5:7b", timeout=2.0)
        assert ok is True
        assert msg == ""


# ============================================================
# Test: sentence model lazy load + timeout
# ============================================================

class TestEmbedderTimeout:
    def test_returns_none_on_load_timeout(self):
        import threading
        from intelnexus.analysis import _MODEL_LOAD_TIMEOUT, _model_load_lock
        from intelnexus import analysis

        # 让模型构造挂起超过超时，模拟下载/加载极慢
        def slow_build():
            threading.Event().wait(_MODEL_LOAD_TIMEOUT + 3)

        with patch.object(analysis, "_shared_model", None):
            with patch.object(analysis, "_model_load_lock", _model_load_lock):
                with patch("intelnexus.analysis._build_sentence_model", side_effect=slow_build):
                    result = analysis.load_sentence_model()
        # 超时分支应降级返回 None，不抛异常
        assert result is None

    def test_returns_none_on_import_error(self):
        from intelnexus import analysis
        with patch.object(analysis, "_shared_model", None):
            with patch("intelnexus.analysis._build_sentence_model",
                       side_effect=ImportError("no sentence_transformers")):
                result = analysis.load_sentence_model()
        assert result is None


# ============================================================
# Test: partial rendering independence
# ============================================================

class _SessionStateStub:
    """Minimal stand-in for streamlit.session_state supporting both get() and attr set."""

    def __init__(self, data):
        self._data = dict(data)

    def get(self, key, default=None):
        return self._data.get(key, default)

    def __setattr__(self, name, value):
        if name == "_data":
            super().__setattr__(name, value)
        else:
            self._data[name] = value

    def __getattr__(self, name):
        if name in self._data:
            return self._data[name]
        raise AttributeError(name)

    def __contains__(self, name):
        return name in self._data


class TestPartialRendering:
    def test_results_detail_renders_without_summary(self):
        """render_results_detail should render when search_completed and filtered exist,
        even if streamed_summary is missing."""
        import intelnexus.ui.results_detail as rd
        fake_session = _SessionStateStub({
            "search_completed": True,
            "filtered": [{"title": "t", "link": "http://x", "source": "S"}],
            "result_page": 1,
        })
        with patch("intelnexus.ui.results_detail.st") as mock_st:
            mock_st.session_state = fake_session
            mock_st.markdown = MagicMock()
            def _cols(spec):
                n = len(spec) if isinstance(spec, (list, tuple)) else spec
                return [MagicMock() for _ in range(n)]
            mock_st.columns = MagicMock(side_effect=_cols)
            mock_st.button = MagicMock(return_value=False)
            mock_st.rerun = MagicMock()
            mock_st.info = MagicMock()
            # Should not raise and should call markdown at least once
            rd.render_results_detail()
            assert mock_st.markdown.called

    def test_download_section_renders_without_summary(self):
        """render_download_section should allow download even when streamed_summary is absent,
        falling back to scraped content."""
        import intelnexus.ui.download as dl
        fake_session = _SessionStateStub({
            "search_completed": True,
            "streamed_summary": "",
            "scraped": {"http://x": "content about topic"},
            "refined": "topic",
            "report_timestamp": "2026-01-01_00-00-00",
        })
        with patch("intelnexus.ui.download.st") as mock_st:
            mock_st.session_state = fake_session
            mock_st.markdown = MagicMock()
            mock_st.selectbox = MagicMock(return_value="md")
            mock_st.button = MagicMock(return_value=False)
            mock_st.download_button = MagicMock()
            dl.render_download_section()
            # 应达到渲染阶段（markdown 被调用），不提前 return
            assert mock_st.markdown.called
