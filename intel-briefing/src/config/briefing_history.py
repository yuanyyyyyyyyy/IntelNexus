"""
简报历史管理
============
保存和查看 AI 简报历史记录
"""

import os
from datetime import datetime
from typing import List, Optional

from shared.settings.file_lock import safe_read_json, safe_write_json
from shared.logger import get_logger

logger = get_logger(__name__)


class BriefingHistory:
    """简报历史管理器"""
    
    def __init__(self, storage_dir: str = "data"):
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
            history = self.get_briefings(limit=100)
            history = [h for h in history if h.get("filename") != filename]
            safe_write_json(self.history_file, history)
            return True
        return False


_briefing_history_instance = None


def get_briefing_history() -> BriefingHistory:
    """获取简报历史管理器单例"""
    global _briefing_history_instance
    if _briefing_history_instance is None:
        _briefing_history_instance = BriefingHistory()
    return _briefing_history_instance
