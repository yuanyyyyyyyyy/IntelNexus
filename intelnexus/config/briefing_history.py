"""
简报历史管理
============
保存和查看 AI 简报历史记录
"""

import json
import os
from datetime import datetime
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
        
        history = self.get_briefings(limit=100)
        if len(history) >= 100:
            logger.warning(f"Briefing history has {len(history)} entries, oldest will be dropped")
        history.insert(0, entry)
        safe_write_json(self.history_file, history)
        
        logger.info(f"Briefing saved: {filename}")
        return filename
    
    def get_briefings(self, limit: int = 20) -> List[dict]:
        """获取简报历史"""
        history = safe_read_json(self.history_file)
        if not isinstance(history, list):
            return []
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
        """删除简报"""
        filepath = os.path.realpath(os.path.join(self.briefings_dir, filename))
        if not filepath.startswith(os.path.realpath(self.briefings_dir)):
            logger.warning(f"Path traversal attempt blocked: {filename}")
            return False
        if os.path.exists(filepath):
            os.remove(filepath)
            # 同步删除条目数据文件
            data_file = self._data_filename(filename)
            if os.path.exists(data_file):
                os.remove(data_file)
            history = self.get_briefings(limit=100)
            history = [h for h in history if h.get("filename") != filename]
            safe_write_json(self.history_file, history)
            return True
        return False

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
