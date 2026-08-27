"""源健康状态模块测试。"""
import pytest
from unittest.mock import patch, MagicMock

from intelnexus.core.search import health as health_mod
from intelnexus.core.search.health import (
    SourceHealth, get_health, save_health, update_health, record_probe_result,
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


@pytest.fixture
def tmp_health_file(tmp_path, monkeypatch):
    """将 HEALTH_FILE 隔离到临时目录，避免污染真实 data/source_health.json。"""
    f = tmp_path / "source_health.json"
    monkeypatch.setattr(health_mod, "HEALTH_FILE", str(f))
    return f


class TestRecordProbeResult:
    """record_probe_result：主动连通性探测（批量测试）落盘语义。

    失败语义：单次探测失败立即置 degraded（绕过被动攒满 3 次的积累），
    但不置 down——down 仅由被动连续失败阈值产生（down 会被搜索管线剔除且无自愈路径）。
    """

    def test_probe_failure_sets_degraded_bypassing_threshold(self, tmp_health_file):
        # 单次探测失败即 degraded，不受被动连续失败阈值（攒满 3 次）限制；
        # consecutive_failures 抬升至至少 DEGRADE_THRESHOLD，同时累加 fail_count / last_error；
        # 绝不置 down（避免瞬时网络抖动把源从搜索管线整体剔除）
        record_probe_result("SrcDown", success=False, latency_ms=0, error="请求超时 (8s)")
        h = get_health("SrcDown")
        assert h.status == "degraded"
        assert h.consecutive_failures >= DEGRADE_THRESHOLD
        assert h.fail_count == 1
        assert h.last_error == "请求超时 (8s)"
        assert h.last_success is None

    def test_probe_failure_then_passive_failure_stays_degraded(self, tmp_health_file):
        # 评审实证的矛盾场景回归：探测失败后再发生一次被动 update_health 失败，
        # 状态仍为 degraded（不得翻回 healthy）——两条路径共用 _update_status 推导，
        # consecutive_failures 持续累计保证状态演化自洽
        record_probe_result("SrcSticky", success=False, latency_ms=0, error="探测失败")
        assert get_health("SrcSticky").status == "degraded"

        update_health("SrcSticky", result_count=0, latency_ms=0, error="被动失败")
        h = get_health("SrcSticky")
        assert h.status == "degraded"
        assert h.consecutive_failures >= DEGRADE_THRESHOLD + 1
        assert h.fail_count == 2

    def test_probe_failure_keeps_last_success(self, tmp_health_file):
        # 先成功一次建立 last_success，再失败：last_success 不被覆盖/清除，
        # 但 status 立即翻为 degraded；fail_count 累计
        record_probe_result("SrcFlaky", success=True, latency_ms=100.0)
        ok_entry = get_health("SrcFlaky")
        assert ok_entry.status == "healthy"
        assert ok_entry.last_success is not None

        record_probe_result("SrcFlaky", success=False, latency_ms=0, error="HTTP 503")
        bad_entry = get_health("SrcFlaky")
        assert bad_entry.status == "degraded"
        assert bad_entry.fail_count == 1
        assert bad_entry.success_count == 1
        assert bad_entry.last_success == ok_entry.last_success

    def test_probe_error_truncated_to_200_chars(self, tmp_health_file):
        # last_error 截断语义：传入 500 字符，落盘后长度为 200（与 record_failure 一致）
        long_error = "x" * 500
        record_probe_result("SrcTrunc", success=False, latency_ms=0, error=long_error)
        assert len(get_health("SrcTrunc").last_error) == 200

    def test_probe_success_recovers_to_healthy(self, tmp_health_file):
        # degraded 之后成功一次：走 record_success 路径，清零连败并恢复 healthy，
        # 刷新 last_success、清除 last_error
        record_probe_result("SrcRecover", success=False, latency_ms=0, error="down")
        assert get_health("SrcRecover").status == "degraded"

        record_probe_result("SrcRecover", success=True, latency_ms=250.0)
        h = get_health("SrcRecover")
        assert h.status == "healthy"
        assert h.consecutive_failures == 0
        assert h.success_count == 1
        assert h.avg_latency_ms == 250.0
        assert h.last_success is not None
        assert h.last_error is None

    def test_probe_result_persists_to_disk(self, tmp_health_file):
        # 落盘持久化：不经 get_health 内存缓存，直接重读 JSON 验证；
        # 失败→成功序列后终态为 healthy（degraded 仅为中间态）
        record_probe_result("SrcPersist", success=False, latency_ms=0, error="连接失败")
        record_probe_result("SrcPersist", success=True, latency_ms=80.0)

        import json
        data = json.loads(tmp_health_file.read_text(encoding="utf-8"))
        entry = data["sources"]["SrcPersist"]
        assert entry["status"] == "healthy"
        assert entry["success_count"] == 1
        assert entry["fail_count"] == 1
        assert entry["last_success"] is not None
        assert "updated_at" in data

    def test_probe_failure_capped_below_down_threshold(self, tmp_health_file):
        # 封顶语义：被动失败已累计到 DOWN_THRESHOLD - 1 后，一次探测失败仍应停留在
        # degraded——consecutive_failures 封顶于 DOWN_THRESHOLD - 1，绝不推导为 down
        #（down 会被搜索管线剔除且无自愈路径，与探测语义矛盾）
        for i in range(DOWN_THRESHOLD - 1):
            update_health("SrcCapped", result_count=0, latency_ms=0,
                          error=f"passive-{i}")
        h = get_health("SrcCapped")
        assert h.consecutive_failures == DOWN_THRESHOLD - 1
        assert h.status == "degraded"

        record_probe_result("SrcCapped", success=False, latency_ms=0, error="探测失败")
        h = get_health("SrcCapped")
        assert h.status == "degraded"
        assert h.consecutive_failures == DOWN_THRESHOLD - 1
        assert h.fail_count == DOWN_THRESHOLD  # 5 次被动 + 1 次探测均计入

    def test_probe_internal_error_never_raises(self, tmp_health_file, monkeypatch):
        # 全异常兜底：内部写盘异常只记日志不抛出（单段失败不影响整体），
        # 且确实尝试过写盘（断言 mock 被调用，证明异常来自写盘路径而非提前短路）
        mock_save = MagicMock(side_effect=RuntimeError("disk full"))
        monkeypatch.setattr(health_mod, "_save_health_data", mock_save)
        record_probe_result("SrcErr", success=False, latency_ms=0, error="x")  # 不抛
        assert mock_save.called
        # 写盘失败不应污染健康表内容（真实提供回归信号：异常后磁盘状态未被写入探测条目）
        import json
        data = json.loads(tmp_health_file.read_text(encoding="utf-8"))
        assert data.get("sources") == {}
