"""源健康状态模块测试。"""
import pytest
from unittest.mock import patch, MagicMock

from intelnexus.core.search.health import (
    SourceHealth, get_health, save_health, update_health,
    DEGRADE_THRESHOLD, DOWN_THRESHOLD
)


class TestSourceHealth:
    def test_record_success_resets_consecutive_failures(self):
        h = SourceHealth(source_name="test")
        h.consecutive_failures = 5
        h.record_success(100.0)
        assert h.consecutive_failures == 0
        assert h.status == "healthy"
        assert h.success_count == 1

    def test_record_failure_increments_consecutive_failures(self):
        h = SourceHealth(source_name="test")
        h.record_failure("error msg")
        assert h.consecutive_failures == 1
        assert h.fail_count == 1
        assert h.last_error == "error msg"

    def test_status_transitions(self):
        h = SourceHealth(source_name="test")
        # healthy → degraded
        for _ in range(DEGRADE_THRESHOLD):
            h.record_failure("err")
        assert h.status == "degraded"
        # degraded → down
        for _ in range(DOWN_THRESHOLD - DEGRADE_THRESHOLD):
            h.record_failure("err")
        assert h.status == "down"

    def test_reset(self):
        h = SourceHealth(source_name="test")
        h.record_failure("err")
        h.record_failure("err")
        h.record_failure("err")
        assert h.status == "degraded"
        h.reset()
        assert h.status == "healthy"
        assert h.consecutive_failures == 0
        assert h.last_error is None

    def test_success_rate(self):
        h = SourceHealth(source_name="test", success_count=7, fail_count=3)
        assert h.success_rate == pytest.approx(0.7)
        # 空数据时返回1.0
        h2 = SourceHealth(source_name="empty")
        assert h2.success_rate == 1.0


class TestHealthPersistence:
    @patch("intelnexus.core.search.health.save_health")
    @patch("intelnexus.core.search.health.get_health")
    def test_update_health_success(self, mock_get, mock_save):
        mock_h = MagicMock()
        mock_get.return_value = mock_h
        update_health("src", result_count=5, latency_ms=120.0)
        mock_h.record_success.assert_called_once_with(120.0)
        mock_save.assert_called_once_with(mock_h)

    @patch("intelnexus.core.search.health.save_health")
    @patch("intelnexus.core.search.health.get_health")
    def test_update_health_failure(self, mock_get, mock_save):
        mock_h = MagicMock()
        mock_get.return_value = mock_h
        update_health("src", result_count=0, latency_ms=0, error="timeout")
        mock_h.record_failure.assert_called_once_with("timeout")
        mock_save.assert_called_once_with(mock_h)

    def test_from_dict_ignores_extra_fields(self):
        data = {"source_name": "x", "status": "down", "unknown_field": 123}
        h = SourceHealth.from_dict(data)
        assert h.source_name == "x"
        assert h.status == "down"
