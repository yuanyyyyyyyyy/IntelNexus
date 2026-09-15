"""
Search History Module
====================
Manage search history and saved reports.
"""

import base64
import os
import json
import shutil
from datetime import datetime
from typing import List, Dict, Optional
from pathlib import Path

from intelnexus.core.logger import get_logger

logger = get_logger(__name__)

# 最多保留的历史条目数（超出后丢弃最旧条目并回收其快照文件）
MAX_HISTORY_ENTRIES = 100

# 可回放快照包含的结构化键（与 search_pipeline._apply_search_results 写入
# session_state 的键对齐，保证历史详情页能复用同一套渲染逻辑）。
# 显式排除 scraped（抓取正文全文）：体积最大，且历史详情的任何面板都不需要它。
SNAPSHOT_KEYS = (
    "query", "refined", "results", "filtered", "streamed_summary",
    "credibility_data", "credibility_radar_chart", "conflicts",
    "structured_summary", "kg_entities", "kg_relations", "kg_html_path",
    "kg_context", "evidence_data", "action_items", "tldr_card",
    "source_stats", "source_counts", "source_info", "query_variants",
    "search_query", "report_timestamp",
)

# 快照目录内的固定文件名
_SNAPSHOT_FILE = "snapshot.json"
_KG_FILE = "kg.html"
_RADAR_FILE = "radar.png"


class SearchHistory:
    def __init__(self, storage_dir: str = None):
        from intelnexus.config.paths import get_data_dir
        storage_dir = storage_dir or get_data_dir()
        self.storage_dir = Path(storage_dir)
        self.history_file = self.storage_dir / "search_history.json"
        self.reports_dir = self.storage_dir / "reports"
        # 每条历史的完整结果快照：data/snapshots/<entry_id>/
        # 与轻量索引 search_history.json 分离，避免历史列表每次 rerun 都解析数 MB 数据
        self.snapshots_dir = self.storage_dir / "snapshots"
        self._ensure_dirs()
    
    def _ensure_dirs(self):
        self.storage_dir.mkdir(exist_ok=True)
        self.reports_dir.mkdir(exist_ok=True)
        self.snapshots_dir.mkdir(exist_ok=True)
    
    def add_search(self, query: str, mode: str, results_count: int, model: str,
                   selected_url: str = "", report_content: str = "",
                   snapshot: dict = None) -> Dict:
        """Add a new search to history.

        Args:
            query: 搜索查询
            mode: 搜索模式
            results_count: 结果数量
            model: 使用的模型
            selected_url: 搜索完成时相关性排序首位的结果 URL（当前 UI 无逐条
                点击入口，以排序首位作为用户兴趣的近似信号；未来若增加
                结果点击埋点，应在此字段记录用户实际点击的 URL）
            report_content: 结构化报告内容（可选，用于查看历史时显示完整内容）
            snapshot: 结构化结果快照（可选）。传入后落盘到
                ``snapshots/<entry_id>/``，历史详情页据此完整还原搜索结果页；
                落盘失败时降级为仅报告文本（不影响历史条目本身）。
        """
        entry_id = self._generate_id()
        entry = {
            "id": entry_id,
            "query": query,
            "mode": mode,
            "results_count": results_count,
            "model": model,
            "timestamp": datetime.now().isoformat(),
            "status": "completed",
            "selected_url": selected_url,
            "report_content": report_content,
        }

        if snapshot and self._write_snapshot(entry_id, snapshot):
            entry["has_snapshot"] = True
            entry["snapshot_dir"] = f"{self.snapshots_dir.name}/{entry_id}"
        
        # 读全量（含软删除）以确定会被淘汰的条目：索引重写会丢弃软删除条目
        # （既有语义），其快照目录必须同步回收，否则成为无法访问的孤儿文件，
        # 造成磁盘无上限泄漏。limit 取足够大值，避免与 get_history 的默认
        # limit 隐式耦合而漏读、漏回收。
        all_entries = self.get_history(limit=9999, include_deleted=True)
        visible = [e for e in all_entries if not e.get("deleted")]
        dropped_ids = [e.get("id", "") for e in all_entries if e.get("deleted")]

        visible.insert(0, entry)
        if len(visible) > MAX_HISTORY_ENTRIES:
            # 超出上限的旧条目不再有查看入口，同步回收其快照目录
            for dropped in visible[MAX_HISTORY_ENTRIES:]:
                dropped_ids.append(dropped.get("id", ""))
            visible = visible[:MAX_HISTORY_ENTRIES]

        for dropped_id in dropped_ids:
            self._remove_snapshot(dropped_id)
        self._save_history(visible)
        return entry

    # ------------------------------------------------------------------
    # 快照（完整结果回放）
    # ------------------------------------------------------------------

    @staticmethod
    def build_snapshot(result: dict) -> Optional[dict]:
        """从搜索计算结果中抽取可回放的结构化快照。

        只保留历史详情页渲染所需的键（见 ``SNAPSHOT_KEYS``），显式排除
        ``scraped`` 抓取正文。返回值中 ``kg_html_path`` 仍是临时绝对路径、
        ``credibility_radar_chart`` 仍是 base64 字符串，实际落盘转换由
        ``_write_snapshot`` 完成。
        """
        if not isinstance(result, dict):
            return None
        snapshot = {}
        for key in SNAPSHOT_KEYS:
            value = result.get(key)
            if value is not None:
                snapshot[key] = value
        # 双保险：即使 SNAPSHOT_KEYS 误收录也不写入抓取正文
        snapshot.pop("scraped", None)
        return snapshot or None

    def _safe_snapshot_dir(self, entry_id: str) -> Optional[Path]:
        """解析快照目录并做路径穿越校验。

        ``entry_id`` 最终来自 ``search_history.json``（可被外部篡改），
        因此读取/删除前必须确认目标仍在 snapshots 目录内；越界返回 None，
        调用方按「无快照」处理（对齐 load_report / delete_report 的既有防护）。
        """
        if not entry_id:
            return None
        root = self.snapshots_dir.resolve()
        target = (root / str(entry_id)).resolve()
        if target == root or not target.is_relative_to(root):
            return None
        return target

    def _write_snapshot(self, entry_id: str, snapshot: dict) -> bool:
        """把快照落盘，成功返回 True。

        大体积产物拆成独立文件，避免 JSON 膨胀：
        - 知识图谱 HTML 从临时路径复制为 ``kg.html``（``temp/kg_*.html`` 会被
          prune_kg_html 清理，必须留持久副本，否则历史图谱必然失效）；
        - 可信度雷达图 base64 PNG 解码写入 ``radar.png``。

        任何环节失败都会清理半成品目录并返回 False，由调用方降级处理。
        """
        target = self._safe_snapshot_dir(entry_id)
        if target is None:
            logger.warning(f"快照目录名非法，跳过落盘: {entry_id!r}")
            return False
        try:
            data = dict(snapshot or {})
            data.pop("scraped", None)
            target.mkdir(parents=True, exist_ok=True)

            # 知识图谱：复制持久副本，JSON 中只留相对文件名
            kg_path = data.get("kg_html_path") or ""
            if kg_path and os.path.exists(kg_path):
                shutil.copyfile(kg_path, target / _KG_FILE)
                data["kg_html_path"] = _KG_FILE
            else:
                data["kg_html_path"] = ""

            # 雷达图：base64 解码为 PNG 文件，JSON 中不保留 base64
            radar_b64 = data.pop("credibility_radar_chart", "") or ""
            if radar_b64:
                try:
                    (target / _RADAR_FILE).write_bytes(base64.b64decode(radar_b64))
                except Exception as e:
                    logger.warning(f"可信度雷达图落盘失败（不影响快照）: {e}")

            with open(target / _SNAPSHOT_FILE, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False)
            return True
        except Exception as e:
            logger.warning(f"写入搜索快照失败，历史将降级为报告文本: {e}")
            self._remove_snapshot(entry_id)
            return False

    def get_snapshot(self, entry_id: str) -> Optional[Dict]:
        """按需加载快照；文件缺失或损坏时返回 None（调用方应降级渲染）。

        返回的 dict 中 ``kg_html_path`` 已还原为绝对路径，
        ``credibility_radar_chart`` 已还原为 base64 字符串。
        """
        target = self._safe_snapshot_dir(entry_id)
        if target is None:
            return None
        snapshot_file = target / _SNAPSHOT_FILE
        if not snapshot_file.exists():
            return None

        try:
            with open(snapshot_file, "r", encoding="utf-8") as f:
                snapshot = json.load(f)
        except Exception as e:
            logger.warning(f"加载搜索快照失败（{entry_id}）: {e}")
            return None
        if not isinstance(snapshot, dict):
            return None

        kg_file = target / _KG_FILE
        snapshot["kg_html_path"] = str(kg_file) if kg_file.exists() else ""

        radar_file = target / _RADAR_FILE
        if radar_file.exists():
            try:
                snapshot["credibility_radar_chart"] = base64.b64encode(
                    radar_file.read_bytes()).decode("ascii")
            except Exception as e:
                logger.warning(f"读取可信度雷达图失败（{entry_id}）: {e}")
        return snapshot

    def _remove_snapshot(self, entry_id: str):
        """删除单条历史的快照目录（不存在、路径越界或失败均静默）。"""
        target = self._safe_snapshot_dir(entry_id)
        if target is not None and target.exists():
            shutil.rmtree(target, ignore_errors=True)
    
    def get_history(self, limit: int = 100, include_deleted: bool = False) -> List[Dict]:
        """Get search history.

        Args:
            limit: 最大返回条数。
            include_deleted: 为 True 时包含已软删除条目。
        """
        if not self.history_file.exists():
            return []

        try:
            with open(self.history_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
        except Exception:
            return []

        if not include_deleted:
            data = [e for e in data if not e.get("deleted")]
        return data[:limit]

    def delete_entry(self, entry_id: str) -> bool:
        """软删除单条记录：标记 deleted + deleted_at。

        快照文件此处**保留**：软删除条目仍可从「已删除记录」区恢复。
        注意软删除条目会在下一次 ``add_search`` 重写索引时被丢弃（既有语义），
        届时其快照目录由 ``add_search`` 同步回收；物理清除
        （``purge_deleted`` / ``clear_history``）同样回收快照。
        """
        history = self.get_history(limit=9999, include_deleted=False)
        for entry in history:
            if entry.get("id") == entry_id:
                entry["deleted"] = True
                entry["deleted_at"] = datetime.now().isoformat()
                # 保留已删除条目在原文件中（物理清除由 purge_deleted 负责）
                all_entries = self.get_history(limit=9999, include_deleted=True)
                for ae in all_entries:
                    if ae.get("id") == entry_id:
                        ae["deleted"] = True
                        ae["deleted_at"] = datetime.now().isoformat()
                        break
                self._save_history(all_entries)
                return True
        return False

    def restore_entry(self, entry_id: str) -> bool:
        """恢复软删除条目：清除 deleted / deleted_at 字段。"""
        all_entries = self.get_history(limit=9999, include_deleted=True)
        for entry in all_entries:
            if entry.get("id") == entry_id:
                entry.pop("deleted", None)
                entry.pop("deleted_at", None)
                self._save_history(all_entries)
                return True
        return False

    def purge_deleted(self, days: int = 0) -> int:
        """物理清除所有软删除条目及其快照文件。返回清除数量。"""
        all_entries = self.get_history(limit=9999, include_deleted=True)
        kept = [e for e in all_entries if not e.get("deleted")]
        purged = [e for e in all_entries if e.get("deleted")]
        if purged:
            self._save_history(kept)
            for e in purged:
                self._remove_snapshot(e.get("id", ""))
        return len(purged)
    
    def save_report(self, query: str, content: str, mode: str) -> str:
        """Save a report to file."""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        safe_query = "".join(c for c in query if c.isalnum() or c in " -_")[:30]
        filename = f"{safe_query}_{timestamp}.md"
        filepath = self.reports_dir / filename
        
        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(f"# Intelligence Report\n\n")
            f.write(f"**Query**: {query}\n")
            f.write(f"**Mode**: {mode}\n")
            f.write(f"**Generated**: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n")
            f.write("---\n\n")
            f.write(content)
        
        return str(filepath)
    
    def get_reports(self) -> List[Dict]:
        """Get list of saved reports."""
        reports = []
        if not self.reports_dir.exists():
            return reports
        
        for f in sorted(self.reports_dir.glob("*.md"), key=lambda x: x.stat().st_mtime, reverse=True):
            stats = f.stat()
            reports.append({
                "name": f.name,
                "path": str(f),
                "size": stats.st_size,
                "modified": datetime.fromtimestamp(stats.st_mtime).isoformat()
            })
        
        return reports
    
    def load_report(self, filename: str) -> Optional[str]:
        """Load a saved report."""
        filepath = (self.reports_dir / filename).resolve()
        if not filepath.is_relative_to(self.reports_dir.resolve()):
            return None
        if not filepath.exists():
            return None
        
        try:
            with open(filepath, 'r', encoding='utf-8') as f:
                return f.read()
        except Exception:
            return None
    
    def delete_report(self, filename: str) -> bool:
        """Delete a saved report."""
        filepath = (self.reports_dir / filename).resolve()
        if not filepath.is_relative_to(self.reports_dir.resolve()):
            return False
        if filepath.exists():
            filepath.unlink()
            return True
        return False
    
    def clear_history(self):
        """物理清除所有条目（含软删除）及其快照文件。"""
        self._save_history([])
        if self.snapshots_dir.exists():
            shutil.rmtree(self.snapshots_dir, ignore_errors=True)
        self.snapshots_dir.mkdir(exist_ok=True)
    
    def _generate_id(self) -> str:
        return datetime.now().strftime("%Y%m%d%H%M%S%f")
    
    def _save_history(self, history: List[Dict]):
        with open(self.history_file, 'w', encoding='utf-8') as f:
            json.dump(history, f, ensure_ascii=False, indent=2)


_history_instance = None

def get_history_manager() -> SearchHistory:
    """Get global history manager instance."""
    global _history_instance
    if _history_instance is None:
        _history_instance = SearchHistory()
    return _history_instance
