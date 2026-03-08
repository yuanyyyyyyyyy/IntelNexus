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
    def __init__(self, storage_dir: str = "data"):
        self.storage_dir = Path(storage_dir)
        self.history_file = self.storage_dir / "search_history.json"
        self.reports_dir = self.storage_dir / "reports"
        self._ensure_dirs()
    
    def _ensure_dirs(self):
        self.storage_dir.mkdir(exist_ok=True)
        self.reports_dir.mkdir(exist_ok=True)
    
    def add_search(self, query: str, mode: str, results_count: int, model: str) -> Dict:
        """Add a new search to history."""
        entry = {
            "id": self._generate_id(),
            "query": query,
            "mode": mode,
            "results_count": results_count,
            "model": model,
            "timestamp": datetime.now().isoformat(),
            "status": "completed"
        }
        
        history = self.get_history()
        history.insert(0, entry)
        
        if len(history) > 100:
            history = history[:100]
        
        self._save_history(history)
        return entry
    
    def get_history(self, limit: int = 20) -> List[Dict]:
        """Get search history."""
        if not self.history_file.exists():
            return []
        
        try:
            with open(self.history_file, 'r', encoding='utf-8') as f:
                return json.load(f)[:limit]
        except:
            return []
    
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
        filepath = self.reports_dir / filename
        if not filepath.exists():
            return None
        
        try:
            with open(filepath, 'r', encoding='utf-8') as f:
                return f.read()
        except:
            return None
    
    def delete_report(self, filename: str) -> bool:
        """Delete a saved report."""
        filepath = self.reports_dir / filename
        if filepath.exists():
            filepath.unlink()
            return True
        return False
    
    def clear_history(self):
        """Clear search history."""
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
