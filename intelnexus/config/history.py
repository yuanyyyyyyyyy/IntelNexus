"""
Search History Module
====================
Manage search history and saved reports.
"""

import os
import json
from datetime import datetime
from typing import List, Dict, Optional
from pathlib import Path


class SearchHistory:
    def __init__(self, storage_dir: str = None):
        from intelnexus.config.paths import get_data_dir
        storage_dir = storage_dir or get_data_dir()
        self.storage_dir = Path(storage_dir)
        self.history_file = self.storage_dir / "search_history.json"
        self.reports_dir = self.storage_dir / "reports"
        self._ensure_dirs()
    
    def _ensure_dirs(self):
        self.storage_dir.mkdir(exist_ok=True)
        self.reports_dir.mkdir(exist_ok=True)
    
    def add_search(self, query: str, mode: str, results_count: int, model: str,
                   selected_url: str = "", report_content: str = "") -> Dict:
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
        """
        entry = {
            "id": self._generate_id(),
            "query": query,
            "mode": mode,
            "results_count": results_count,
            "model": model,
            "timestamp": datetime.now().isoformat(),
            "status": "completed",
            "selected_url": selected_url,
            "report_content": report_content,
        }
        
        history = self.get_history(include_deleted=False)
        history.insert(0, entry)
        
        if len(history) > 100:
            history = history[:100]
        
        self._save_history(history)
        return entry
    
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
        """软删除单条记录：标记 deleted + deleted_at。"""
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
        """物理清除所有软删除条目。返回清除数量。"""
        all_entries = self.get_history(limit=9999, include_deleted=True)
        kept = [e for e in all_entries if not e.get("deleted")]
        purged_count = len(all_entries) - len(kept)
        if purged_count > 0:
            self._save_history(kept)
        return purged_count
    
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
        """物理清除所有条目（含软删除）。"""
        self._save_history([])
    
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
