"""Tests for project split verification.

These tests verify that the project was correctly split into
intel-search and intel-briefing sub-projects.
"""

import os
import inspect
from pathlib import Path

import pytest


# Root directory
ROOT_DIR = Path(__file__).parent.parent
INTEL_SEARCH_DIR = ROOT_DIR / "intel-search"
INTEL_BRIEFING_DIR = ROOT_DIR / "intel-briefing"


class TestFileIntegrity:
    """Verify both sub-projects have required files."""

    def test_intel_search_has_required_files(self):
        """intel-search should have all core files."""
        required_files = [
            "main.py",
            "ui.py",
            "config.py",
            "requirements.txt",
            "README.md",
            "src/__init__.py",
            "src/analysis/__init__.py",
            "src/analysis/credibility.py",
            "src/analysis/evidence_tracer.py",
            "src/analysis/intelligence_graph.py",
            "src/search/darkweb.py",
            "src/ui/__init__.py",
            "src/ui/i18n.py",
            "src/ui/sidebar.py",
            "src/ui/search_pipeline.py",
            "src/ui/results.py",
            "src/ui/download.py",
            "src/ui/results_detail.py",
            "src/export/__init__.py",
            "src/export/report.py",
            "tests/__init__.py",
        ]
        for file_path in required_files:
            full_path = INTEL_SEARCH_DIR / file_path
            assert full_path.exists(), f"Missing: intel-search/{file_path}"

    def test_intel_briefing_has_required_files(self):
        """intel-briefing should have all core files."""
        required_files = [
            "main.py",
            "ui.py",
            "config.py",
            "requirements.txt",
            "README.md",
            "src/__init__.py",
            "ai_briefing/__init__.py",
            "ai_briefing/analyzer.py",
            "ai_briefing/collector.py",
            "ai_briefing/config.py",
            "ai_briefing/notifier.py",
            "ai_briefing/prompts.py",
            "ai_briefing/scheduler.py",
            "ai_briefing/templates.py",
            "src/config/sources.py",
            "src/config/subscriptions.py",
            "src/config/briefing_history.py",
            "src/ui/__init__.py",
            "src/ui/i18n.py",
            "src/ui/sidebar.py",
            "src/ui/briefing_viewer.py",
            "src/export/__init__.py",
            "src/export/briefing_export.py",
            "tests/__init__.py",
        ]
        for file_path in required_files:
            full_path = INTEL_BRIEFING_DIR / file_path
            assert full_path.exists(), f"Missing: intel-briefing/{file_path}"

    def test_intel_search_no_ai_briefing_module(self):
        """intel-search should NOT have ai_briefing directory."""
        assert not (INTEL_SEARCH_DIR / "ai_briefing").exists()

    def test_intel_briefing_no_darkweb(self):
        """intel-briefing should NOT have darkweb.py."""
        assert not (INTEL_BRIEFING_DIR / "src" / "search" / "darkweb.py").exists()


class TestNoCrossImports:
    """Verify no cross-project imports exist."""

    def test_intel_search_no_ai_briefing_imports(self):
        """intel-search should not import from ai_briefing."""
        search_dir = INTEL_SEARCH_DIR / "src"
        for py_file in search_dir.rglob("*.py"):
            content = py_file.read_text(encoding="utf-8")
            assert "from ai_briefing" not in content, (
                f"{py_file.relative_to(INTEL_SEARCH_DIR)} imports from ai_briefing"
            )
            assert "import ai_briefing" not in content, (
                f"{py_file.relative_to(INTEL_SEARCH_DIR)} imports ai_briefing"
            )

    def test_intel_briefing_no_darkweb_imports(self):
        """intel-briefing should not import from search.darkweb."""
        briefing_dir = INTEL_BRIEFING_DIR / "src"
        for py_file in briefing_dir.rglob("*.py"):
            content = py_file.read_text(encoding="utf-8")
            assert "from src.search.darkweb" not in content, (
                f"{py_file.relative_to(INTEL_BRIEFING_DIR)} imports from darkweb"
            )
            assert "import src.search.darkweb" not in content, (
                f"{py_file.relative_to(INTEL_BRIEFING_DIR)} imports darkweb"
            )

    def test_intel_briefing_main_no_search_command(self):
        """intel-briefing main.py should not have search command."""
        main_file = INTEL_BRIEFING_DIR / "main.py"
        content = main_file.read_text(encoding="utf-8")
        assert "def search(" not in content
        assert "@intelnexus.command()\ndef search" not in content


class TestI18nSplit:
    """Verify i18n files are correctly split."""

    def test_search_i18n_has_search_keys(self):
        """intel-search i18n should have search-related keys."""
        i18n_file = INTEL_SEARCH_DIR / "src" / "ui" / "i18n.py"
        content = i18n_file.read_text(encoding="utf-8")
        search_keys = [
            "search_placeholder",
            "search_button",
            "search_mode",
            "mode_all",
            "mode_web",
            "mode_news",
            "mode_darkweb",
            "darkweb_warning",
            "darkweb_settings",
            "tor_port",
        ]
        for key in search_keys:
            assert f'"{key}"' in content, f"Missing search key: {key}"

    def test_briefing_i18n_has_briefing_keys(self):
        """intel-briefing i18n should have briefing-related keys."""
        i18n_file = INTEL_BRIEFING_DIR / "src" / "ui" / "i18n.py"
        content = i18n_file.read_text(encoding="utf-8")
        briefing_keys = [
            "briefing_generating",
            "briefing_no_subscribers",
            "briefing_success",
            "briefing_failed",
            "briefing_preview",
            "briefing_history",
            "generate_briefing",
            "subscription_management",
            "smtp_server",
        ]
        for key in briefing_keys:
            assert f'"{key}"' in content, f"Missing briefing key: {key}"

    def test_search_i18n_no_briefing_keys(self):
        """intel-search i18n should NOT have briefing-specific keys."""
        i18n_file = INTEL_SEARCH_DIR / "src" / "ui" / "i18n.py"
        content = i18n_file.read_text(encoding="utf-8")
        briefing_only_keys = [
            "briefing_generating",
            "briefing_no_subscribers",
            "briefing_success",
            "generate_briefing",
            "subscription_management",
            "smtp_server",
        ]
        for key in briefing_only_keys:
            assert f'"{key}"' not in content, (
                f"intel-search i18n has briefing key: {key}"
            )

    def test_briefing_i18n_no_search_keys(self):
        """intel-briefing i18n should NOT have search-specific keys."""
        i18n_file = INTEL_BRIEFING_DIR / "src" / "ui" / "i18n.py"
        content = i18n_file.read_text(encoding="utf-8")
        search_only_keys = [
            "darkweb_warning",
            "darkweb_settings",
            "tor_port",
            "tor_running",
            "tor_not_running",
            "mode_darkweb",
        ]
        for key in search_only_keys:
            assert f'"{key}"' not in content, (
                f"intel-briefing i18n has search key: {key}"
            )


class TestCLICommands:
    """Verify CLI commands are correctly split."""

    def test_intel_search_has_search_command(self):
        """intel-search main.py should have search command."""
        main_file = INTEL_SEARCH_DIR / "main.py"
        content = main_file.read_text(encoding="utf-8")
        assert "def search(" in content
        assert "@intelnexus.command()" in content

    def test_intel_search_no_briefing_command(self):
        """intel-search main.py should NOT have briefing command."""
        main_file = INTEL_SEARCH_DIR / "main.py"
        content = main_file.read_text(encoding="utf-8")
        assert "def briefing(" not in content
        assert "def scheduler(" not in content

    def test_intel_briefing_has_briefing_command(self):
        """intel-briefing main.py should have briefing command."""
        main_file = INTEL_BRIEFING_DIR / "main.py"
        content = main_file.read_text(encoding="utf-8")
        assert "def briefing(" in content
        assert "def scheduler(" in content

    def test_intel_briefing_no_search_command(self):
        """intel-briefing main.py should NOT have search command."""
        main_file = INTEL_BRIEFING_DIR / "main.py"
        content = main_file.read_text(encoding="utf-8")
        assert "def search(" not in content
        assert "execute_search" not in content


class TestDependencies:
    """Verify requirements.txt files are correct."""

    def test_intel_search_has_requirements(self):
        """intel-search should have requirements.txt."""
        req_file = INTEL_SEARCH_DIR / "requirements.txt"
        assert req_file.exists()

    def test_intel_briefing_has_requirements(self):
        """intel-briefing should have requirements.txt."""
        req_file = INTEL_BRIEFING_DIR / "requirements.txt"
        assert req_file.exists()

    def test_intel_search_requirements_has_core_deps(self):
        """intel-search requirements should include core dependencies."""
        req_file = INTEL_SEARCH_DIR / "requirements.txt"
        content = req_file.read_text(encoding="utf-8")
        core_deps = [
            "requests",
            "beautifulsoup4",
            "streamlit",
            "click",
            "langchain-core",
            "numpy",
            "sentence-transformers",
            "networkx",
        ]
        for dep in core_deps:
            assert dep in content, f"Missing dep in intel-search: {dep}"

    def test_intel_briefing_requirements_has_core_deps(self):
        """intel-briefing requirements should include core dependencies."""
        req_file = INTEL_BRIEFING_DIR / "requirements.txt"
        content = req_file.read_text(encoding="utf-8")
        core_deps = [
            "requests",
            "beautifulsoup4",
            "streamlit",
            "click",
            "langchain-core",
            "apscheduler",
            "portalocker",
        ]
        for dep in core_deps:
            assert dep in content, f"Missing dep in intel-briefing: {dep}"

    def test_intel_search_no_apscheduler(self):
        """intel-search should NOT require apscheduler."""
        req_file = INTEL_SEARCH_DIR / "requirements.txt"
        content = req_file.read_text(encoding="utf-8")
        assert "apscheduler" not in content

    def test_intel_briefing_no_sentence_transformers(self):
        """intel-briefing should NOT require sentence-transformers."""
        req_file = INTEL_BRIEFING_DIR / "requirements.txt"
        content = req_file.read_text(encoding="utf-8")
        assert "sentence-transformers" not in content
