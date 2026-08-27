"""
简报历史管理
===========
保存和查看 AI 简报历史记录
"""

import io
import json
import os
import zipfile
from datetime import datetime, timedelta
from typing import List, Optional

from intelnexus.core.settings.file_lock import safe_read_json, safe_write_json
from intelnexus.core.logger import get_logger

logger = get_logger(__name__)


class BriefingHistory:
    """简报历史管理器"""
    
    def __init__(self, storage_dir: str = None):
        from intelnexus.config.paths import get_data_dir
        storage_dir = storage_dir or get_data_dir()
        self.storage_dir = storage_dir
        self.briefings_dir = os.path.join(storage_dir, "briefings")
        self.history_file = os.path.join(storage_dir, "briefing_history.json")
        self._ensure_dirs()
    
    def _ensure_dirs(self):
        """确保目录存在"""
        os.makedirs(self.briefings_dir, exist_ok=True)
    
    # 历史索引上限：超出后最老条目被挤出索引（.md 文件保留在磁盘，仅不可见）
    _MAX_HISTORY_ENTRIES = 100

    def save_briefing(
        self,
        markdown_content: str,
        html_content: str = None,
        organization_name: str = "",
        categories: List[str] = None,
        subscribers_count: int = 0
    ) -> str:
        """
        保存简报
        
        Args:
            markdown_content: Markdown 格式简报
            html_content: HTML 格式简报（可选）
            organization_name: 组织名称
            categories: 采集的类别列表
            subscribers_count: 推送的订阅者数量
        
        Returns:
            str: 保存的文件名
        """
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"briefing_{timestamp}.md"
        filepath = os.path.join(self.briefings_dir, filename)
        
        with open(filepath, "w", encoding="utf-8") as f:
            f.write(markdown_content)
        
        html_filename = None
        if html_content:
            html_filename = f"briefing_{timestamp}.html"
            html_filepath = os.path.join(self.briefings_dir, html_filename)
            with open(html_filepath, "w", encoding="utf-8") as f:
                f.write(html_content)
        
        entry = {
            "id": timestamp,
            "filename": filename,
            "html_filename": html_filename,
            "organization": organization_name,
            "categories": categories or [],
            "subscribers_count": subscribers_count,
            "created_at": datetime.now().isoformat(),
            "content_length": len(markdown_content)
        }
        
        # 读全量索引做截断判断（limit=1 会把 100 条之外的旧条目永久挤出）
        # include_deleted=True：软删除条目也占位，防止删除后索引缩减导致新条目被误挤出
        history = self.get_briefings(limit=self._MAX_HISTORY_ENTRIES + 500, include_deleted=True)
        if len(history) >= self._MAX_HISTORY_ENTRIES:
            logger.warning(
                f"Briefing history has {len(history)} entries (max {self._MAX_HISTORY_ENTRIES}), "
                f"oldest {len(history) - self._MAX_HISTORY_ENTRIES + 1} will be dropped from the index"
            )
        history.insert(0, entry)
        history = history[:self._MAX_HISTORY_ENTRIES]
        safe_write_json(self.history_file, history)
        
        logger.info(f"Briefing saved: {filename}")
        return filename
    
    def get_briefings(self, limit: int = 20, include_deleted: bool = False) -> List[dict]:
        """获取简报历史"""
        history = safe_read_json(self.history_file)
        if not isinstance(history, list):
            return []
        if not include_deleted:
            history = [h for h in history if not h.get("deleted")]
        return history[:limit]
    
    def load_briefing(self, filename: str) -> Optional[str]:
        """加载简报内容"""
        filepath = os.path.realpath(os.path.join(self.briefings_dir, filename))
        if not filepath.startswith(os.path.realpath(self.briefings_dir)):
            logger.warning(f"Path traversal attempt blocked: {filename}")
            return None
        if not os.path.exists(filepath):
            logger.warning(f"Briefing not found: {filename}")
            return None
        with open(filepath, "r", encoding="utf-8") as f:
            return f.read()
    
    def delete_briefing(self, filename: str) -> bool:
        """软删除简报（标记 deleted，文件保留）"""
        history = self.get_briefings(limit=self._MAX_HISTORY_ENTRIES + 500, include_deleted=True)
        for entry in history:
            if entry.get("filename") == filename:
                if entry.get("deleted"):
                    return False
                entry["deleted"] = True
                entry["deleted_at"] = datetime.now().isoformat()
                safe_write_json(self.history_file, history)
                return True
        return False

    def restore_briefing(self, filename: str) -> bool:
        """恢复软删除的简报"""
        history = self.get_briefings(limit=self._MAX_HISTORY_ENTRIES + 500, include_deleted=True)
        for entry in history:
            if entry.get("filename") == filename:
                if not entry.get("deleted"):
                    return False
                entry["deleted"] = False
                entry["deleted_at"] = None
                safe_write_json(self.history_file, history)
                return True
        return False

    def purge_deleted(self, days: int = 30) -> int:
        """清理超过指定天数的软删除条目及其物理文件，返回清理数量"""
        history = self.get_briefings(limit=self._MAX_HISTORY_ENTRIES + 500, include_deleted=True)
        cutoff = datetime.now() - timedelta(days=days)
        kept = []
        purged = 0
        for entry in history:
            if entry.get("deleted") and entry.get("deleted_at"):
                try:
                    deleted_at = datetime.fromisoformat(entry["deleted_at"])
                except (ValueError, TypeError):
                    kept.append(entry)
                    continue
                if deleted_at < cutoff:
                    # 物理删除文件
                    fp = os.path.realpath(os.path.join(self.briefings_dir, entry["filename"]))
                    if fp.startswith(os.path.realpath(self.briefings_dir)) and os.path.exists(fp):
                        os.remove(fp)
                    df = self._data_filename(entry["filename"])
                    if os.path.exists(df):
                        os.remove(df)
                    purged += 1
                    continue
            kept.append(entry)
        if purged:
            safe_write_json(self.history_file, kept)
        return purged

    def export_briefings(self, filenames: List[str]) -> Optional[bytes]:
        """将多个简报打包为 ZIP，返回字节流；无有效文件时返回 None"""
        buf = io.BytesIO()
        count = 0
        with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
            for fn in filenames:
                fp = os.path.realpath(os.path.join(self.briefings_dir, fn))
                if not fp.startswith(os.path.realpath(self.briefings_dir)):
                    continue
                if not os.path.exists(fp):
                    continue
                zf.write(fp, arcname=fn)
                count += 1
        if count == 0:
            return None
        return buf.getvalue()

    def update_entry(self, filename: str, fields: dict) -> bool:
        """按文件名更新历史索引条目的元数据字段（如 subscribers_count/source）。

        仅合并已知键；条目不存在时返回 False。
        """
        history = self.get_briefings(limit=self._MAX_HISTORY_ENTRIES + 500, include_deleted=True)
        found = False
        for entry in history:
            if entry.get("filename") == filename:
                entry.update(fields)
                found = True
                break
        if not found:
            logger.warning(f"update_entry: entry not found: {filename}")
            return False
        return safe_write_json(self.history_file, history)

    # ---- 条目数据存取（反向飞轮：简报条目 → 一键取证） ----

    @staticmethod
    def _data_filename(md_filename: str) -> str:
        """由简报文件名推导条目数据 JSON 文件名"""
        base = os.path.splitext(md_filename)[0]
        return f"{base}_entries.json"

    def save_briefing_data(self, md_filename: str, entries: list) -> str:
        """保存简报条目数据（含可信度评分与冲突标记）

        Args:
            md_filename: 简报 .md 文件名（如 briefing_20260807_235000.md）
            entries: 条目列表 [{title, url, source, category,
                     credibility_score, has_conflict, conflict_severity, ...}]

        Returns:
            str: 数据文件名
        """
        data_filename = self._data_filename(md_filename)
        filepath = os.path.join(self.briefings_dir, data_filename)
        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(entries, f, ensure_ascii=False, indent=2)
        logger.info(f"Briefing entries saved: {data_filename} ({len(entries)} entries)")
        return data_filename

    def load_briefing_data(self, md_filename: str) -> list:
        """加载简报条目数据

        Args:
            md_filename: 简报 .md 文件名

        Returns:
            list: 条目列表，文件不存在时返回空列表
        """
        data_filename = self._data_filename(md_filename)
        filepath = os.path.realpath(os.path.join(self.briefings_dir, data_filename))
        if not filepath.startswith(os.path.realpath(self.briefings_dir)):
            return []
        if not os.path.exists(filepath):
            return []
        try:
            with open(filepath, "r", encoding="utf-8") as f:
                data = json.load(f)
            return data if isinstance(data, list) else []
        except Exception as e:
            logger.warning(f"Failed to load briefing data {data_filename}: {e}")
            return []


_briefing_history_instance = None


def get_briefing_history() -> BriefingHistory:
    """获取简报历史管理器单例"""
    global _briefing_history_instance
    if _briefing_history_instance is None:
        _briefing_history_instance = BriefingHistory()
    return _briefing_history_instance
