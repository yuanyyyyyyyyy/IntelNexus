"""
IntelNexus - AI Multi-Source Network Intelligence Platform
=========================================================
Unified CLI composing intel-search and intel-briefing sub-projects.
"""

import os
import sys
import logging
import threading
import webbrowser
from typing import Dict, List

# Suppress the harmless torch.classes probe warning emitted during Streamlit
# reloads ("Examining the path of torch.classes raised: Tried to instantiate
# class '__path__._path'..."). It is a known no-op message, not an error.
# We filter it at the stderr stream level so real errors stay visible.
class _StderrNoiseFilter:
    """过滤 stderr 中的已知无害噪音（torch / langchain-openai 等）。

    多行消息处理：匹配到噪音首行后进入抑制模式，直到遇到空行或
    新的标准日志行（[timestamp 前缀）才恢复输出，避免多行警告的
    后续行泄漏。
    """
    def __init__(self, stream):
        self._stream = stream
        self._buf = ""
        self._suppress = False

    _NOISE_PREFIXES = (
        "Examining the path of torch.classes raised",
        "Tried to instantiate class '__path__._path'",
        "langchain-openai injected a custom httpx transport",
    )

    def _is_noise_start(self, line: str) -> bool:
        return any(line.startswith(p) for p in self._NOISE_PREFIXES)

    @staticmethod
    def _is_noise_end(line: str) -> bool:
        """空行或新日志行（[20... 前缀）标志噪音消息结束。"""
        stripped = line.strip()
        if not stripped:
            return True
        if stripped.startswith("[20"):
            return True
        return False

    def write(self, data):
        self._buf += data
        while "\n" in self._buf:
            line, self._buf = self._buf.split("\n", 1)
            if self._suppress:
                if self._is_noise_end(line):
                    self._suppress = False
                    self._stream.write(line + "\n")
            elif self._is_noise_start(line):
                self._suppress = True
            else:
                self._stream.write(line + "\n")

    def flush(self):
        if self._buf:
            if not self._suppress:
                self._stream.write(self._buf)
            self._buf = ""
        self._stream.flush()

    def __getattr__(self, name):
        return getattr(self._stream, name)


if not getattr(sys, "frozen", False):
    sys.stderr = _StderrNoiseFilter(sys.stderr)

logging.getLogger("torch").setLevel(logging.CRITICAL + 1)

# langchain-openai 注入自定义 httpx transport 后会禁用 httpx 的代理自动检测，
# 并在每次导入时输出一行 warning。本地部署不需要此行为，提前关闭。
os.environ.setdefault("LANGCHAIN_OPENAI_TCP_KEEPALIVE", "0")
# 双重保险：即便 env var 未生效，也抑制 langchain 系列的 INFO/WARNING 日志，
# 只保留 ERROR 及以上级别（真正的错误不应被吞掉）。
logging.getLogger("langchain").setLevel(logging.ERROR)
logging.getLogger("langchain_openai").setLevel(logging.ERROR)
logging.getLogger("langchain_core").setLevel(logging.ERROR)

# Ensure root project dir resolves first so root-level config.py and the
# intelnexus/ package are importable. The single-package layout removes the
# old sys.path hacks that worked around duplicated sub-project modules.
_ROOT = os.path.dirname(os.path.abspath(__file__))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

# 动态解析：data/search_settings.json(UI 显式保存) > 环境变量(.env 兜底)
from intelnexus.config.search_settings import get_news_api_key as NEWS_API_KEY

# Inject config into shared library
from intelnexus.core.settings import set as set_config
set_config({
    "OLLAMA_BASE_URL": os.getenv("OLLAMA_BASE_URL", "http://localhost:11434"),
    "OPENROUTER_BASE_URL": os.getenv("OPENROUTER_BASE_URL", ""),
    "OPENROUTER_API_KEY": os.getenv("OPENROUTER_API_KEY", ""),
    "GOOGLE_API_KEY": os.getenv("GOOGLE_API_KEY", ""),
    "NEWS_API_KEY": NEWS_API_KEY(),
})

import click
from datetime import datetime

from intelnexus.core.logger import get_logger
from intelnexus.core.search.scraper import scrape_multiple
from intelnexus.core.search.registry import SearchSourceRegistry
from intelnexus.core.search.modes import SEARCH_MODES_LABELS

import config as app_config

from intelnexus.core.llm.core import get_llm, expand_query, expand_query_for_search, generate_summary
from intelnexus.core.search.registry import get_registry

logger = get_logger(__name__)

# 向后兼容：CLI 回显用（值不变）
SEARCH_MODES = SEARCH_MODES_LABELS

# CLI 进程内搜索结果缓存（同一查询参数下跳过重复检索）
_cli_search_cache: Dict[tuple, List[Dict]] = {}


def execute_search(mode, query, max_workers):
    """按 mode 遍历注册表并发检索（统一源抽象，无硬编码分支）。

    复用进程内 SearchSourceRegistry 单例，并对相同
    (mode, query, max_workers) 的检索结果做进程内缓存，
    避免 CLI 连续检索、或重复检索时的重复磁盘读取与网络开销。
    """
    cache_key = (mode, query, max_workers)
    cached = _cli_search_cache.get(cache_key)
    if cached is not None:
        logger.debug("CLI 搜索命中进程内缓存，跳过重复检索: %s", query)
        return cached

    registry = get_registry(
        news_api_key=NEWS_API_KEY(),
        darkweb_advanced=app_config.ENABLE_DARKWEB,
        tor_port=app_config.TOR_PROXY_PORT,
        web_threads=max_workers,
    )
    results = registry.collect(mode, query, max_results=20, threads=max_workers)
    _cli_search_cache[cache_key] = results
    return results


@click.group()
@click.version_option()
def intelnexus():
    """IntelNexus: AI-Powered Multi-Source Network Intelligence Platform."""
    pass


# --- Search commands from intel-search ---
def _register_search_commands():
    """Register search commands on the root CLI."""

    @intelnexus.command()
    @click.option("--model", "-m", default="qwen2.5:7b", show_default=True, help="Select LLM model (local or cloud)")
    @click.option("--query", "-q", required=True, type=str, help="Search query")
    @click.option("--mode", "-s", default="all", type=click.Choice(["web", "news", "darkweb", "threat", "all"]), help="Search mode")
    @click.option("--threads", "-t", default=5, show_default=True, type=int, help="Number of threads")
    @click.option("--output", "-o", type=str, help="Output filename")
    @click.option("--no-credibility", is_flag=True, help="Disable credibility assessment & knowledge graph")
    def search(model, query, mode, threads, output, no_credibility):
        """Run multi-source intelligence search."""
        click.echo(f"IntelNexus - {SEARCH_MODES.get(mode, mode)} Mode")
        click.echo(f"Model: {model}")
        click.echo(f"Query: {query}")

        try:
            llm = get_llm(model)
        except ValueError as e:
            click.echo(f"Error: {e}")
            return

        click.echo(f"[1/4] Refining query...")
        refined_variants = expand_query(query)
        click.echo(f"    Refined: {' | '.join(refined_variants)}")

        click.echo(f"[2/4] Searching {mode}...")
        # expand_query 返回多语言变体列表；搜索串取首个最贴近原意的变体
        # （修复：曾直接把 list 传入 execute_search，缓存键 unhashable 导致 CLI 搜索必崩）
        refined_query = expand_query_for_search(refined_variants)
        search_results = execute_search(mode, refined_query, threads)
        click.echo(f"    Found {len(search_results)} results")

        if not search_results:
            click.echo("No results found.")
            return

        search_filtered = search_results
        click.echo(f"[3/4] Keeping all {len(search_filtered)} results")

        click.echo("[4/4] Scraping content...")
        scraped_results = scrape_multiple(search_filtered, max_workers=threads)
        click.echo("    Done")

        credibility_context = ""
        kg_context = ""
        conflicts_context = ""

        if not no_credibility:
            click.echo("[4.5/5] Analyzing credibility...")
            from intelnexus.analysis.credibility import SourceScorer, ConflictDetector
            scorer = SourceScorer()
            scorer.evaluate(search_filtered, scraped_results)
            cred_lines = []
            for r in search_filtered[:15]:
                score = r.get("credibility_score", 0.5)
                details = r.get("credibility_details", {})
                reason = details.get("reason", "")
                source = r.get("source", "Unknown")
                cred_lines.append(f"- {source}: score {score:.2f} ({reason})")
            credibility_context = "\n".join(cred_lines)

            detector = ConflictDetector()
            conflicts_list = detector.detect(search_filtered, scraped_results)
            if conflicts_list:
                conflicts_context = "\n".join(
                    [f"- [{c['type']}] {c['description']}" for c in conflicts_list[:5]])

            click.echo("[4.6/5] Building knowledge graph...")
            from intelnexus.analysis.intelligence_graph import EntityExtractor, IntelligenceGraph
            extractor = EntityExtractor()
            kg_raw = extractor.extract(scraped_results)
            kg = IntelligenceGraph()
            kg.build(kg_raw["entities"], kg_raw["relations"])
            top_entities = sorted(kg_raw["entities"], key=lambda e: e["importance"], reverse=True)[:10]
            kg_context = "\n".join([f"- {e['name']} ({e['type']})" for e in top_entities])
            kg_path = kg.export_html(f"report_kg_{datetime.now().strftime('%Y%m%d%H%M%S')}.html")
            if kg_path:
                click.echo(f"    Knowledge graph saved to {kg_path}")

        click.echo("[5/5] Generating summary...")
        summary = generate_summary(llm, query, scraped_results,
                                   credibility_context=credibility_context,
                                   kg_context=kg_context,
                                   conflicts_context=conflicts_context)

        if not output:
            now = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
            filename = f"report_{now}.md"
        else:
            filename = output + ".md"

        with open(filename, "w", encoding="utf-8") as f:
            f.write(summary)
            click.echo(f"\n[OUTPUT] Report saved to {filename}")


# --- Briefing commands from intel-briefing ---
def _register_briefing_commands():
    """Register briefing commands on the root CLI."""

    @intelnexus.command()
    @click.option("--model", "-m", default="qwen2.5:7b", help="LLM model to use")
    @click.option("--notify-only", is_flag=True, help="Only send notifications, don't generate report")
    @click.option("--format", "-f", "export_format", type=click.Choice(["md", "html", "pdf", "all"]), default="all", help="Export format")
    def briefing(model, notify_only, export_format):
        """Generate and send AI briefing to all subscribers."""
        try:
            from intelnexus.config.paths import migrate_legacy_data_files
            migrate_legacy_data_files()

            from intelnexus.briefing.collector import AIBriefingCollector
            from intelnexus.briefing.analyzer import AIBriefingAnalyzer
            from intelnexus.briefing.notifier import AIBriefingNotifier
            from intelnexus.briefing.config import BRIEFING_CONFIG
            from intelnexus.config.subscriptions import get_active_subscribers, update_last_sent
            from intelnexus.briefing.templates import render_markdown_briefing, render_email_html, markdown_to_html_sections

            click.echo("AI Briefing Generator")
            click.echo("=" * 50)

            subscribers = get_active_subscribers()
            if not subscribers:
                click.echo("No active subscribers found.")
                return

            click.echo(f"Found {len(subscribers)} active subscribers")

            collector = AIBriefingCollector()
            llm = get_llm(model)
            analyzer = AIBriefingAnalyzer(llm=llm)

            click.echo("\n[1/4] Collecting data...")
            collected_data = collector.collect_all_categories()
            for cat, results in collected_data.items():
                click.echo(f"  - {cat}: {len(results)} results")

            click.echo("\n[2/4] Generating briefing...")
            organization_name = BRIEFING_CONFIG["organization"]["name"]
            briefing_md = analyzer.generate_briefing(collected_data, organization_name)

            briefing_html = None
            try:
                sections = markdown_to_html_sections(briefing_md)
                briefing_html = render_email_html(
                    generated_date=datetime.now().strftime("%Y年%m月%d日"),
                    organization=BRIEFING_CONFIG["organization"], **sections)
            except Exception as e:
                click.echo(f"  Warning: Could not generate HTML: {e}")

            from intelnexus.config.briefing_history import get_briefing_history
            briefing_filename = get_briefing_history().save_briefing(
                markdown_content=briefing_md, html_content=briefing_html,
                organization_name=organization_name,
                categories=list(collected_data.keys()),
                subscribers_count=len(subscribers))
            click.echo(f"  Briefing saved to: data/briefings/{briefing_filename}")

            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            if export_format in ("md", "all"):
                md_path = f"data/briefings/briefing_{timestamp}.md"
                with open(md_path, "w", encoding="utf-8") as f:
                    f.write(briefing_md)
                click.echo(f"  MD exported: {md_path}")
            if export_format in ("html", "all") and briefing_html:
                html_path = f"data/briefings/briefing_{timestamp}.html"
                with open(html_path, "w", encoding="utf-8") as f:
                    f.write(briefing_html)
                click.echo(f"  HTML exported: {html_path}")
            if export_format in ("pdf", "all"):
                try:
                    from intelnexus.briefing.export.briefing_export import export_briefing_pdf
                    pdf_path = f"data/briefings/briefing_{timestamp}.pdf"
                    export_briefing_pdf(briefing_md, pdf_path)
                    click.echo(f"  PDF exported: {pdf_path}")
                except Exception as e:
                    click.echo(f"  Warning: Could not export PDF: {e}")

            click.echo("\n[3/4] Sending notifications...")
            email_config = {
                "smtp_server": os.getenv("SMTP_SERVER", ""),
                "smtp_port": int(os.getenv("SMTP_PORT", "587")),
                "username": os.getenv("SMTP_USERNAME", ""),
                "password": os.getenv("SMTP_PASSWORD", ""),
                "use_tls": os.getenv("SMTP_USE_TLS", "true").lower() == "true"
            }
            notifier = AIBriefingNotifier(email_config=email_config)
            success_count = 0
            for subscriber in subscribers:
                click.echo(f"  Sending to: {subscriber['name']} ({subscriber['email']})")
                results = notifier.notify(subscriber, briefing_md, briefing_html)
                if any(results.values()):
                    success_count += 1
                    update_last_sent(subscriber["id"])
                    click.echo(f"    Sent successfully")
                else:
                    click.echo(f"    Failed to send")

            click.echo("\n[4/4] Complete!")
            click.echo(f"  Sent {success_count}/{len(subscribers)} briefings")

        except ImportError as e:
            click.echo(f"Error: Required module not found: {e}")
        except Exception as e:
            click.echo(f"Error: {e}")

    @intelnexus.command()
    def scheduler():
        """Run the AI briefing scheduler in background."""
        try:
            from intelnexus.briefing.scheduler import AIBriefingScheduler

            click.echo("AI Briefing Scheduler")
            click.echo("=" * 50)

            scheduler_instance = AIBriefingScheduler()
            scheduler_instance.start()
            click.echo("Scheduler started. Press Ctrl+C to stop.")

            try:
                while True:
                    import time
                    time.sleep(1)
            except KeyboardInterrupt:
                click.echo("\nStopping scheduler...")
                scheduler_instance.stop()
                click.echo("Scheduler stopped.")

        except ImportError as e:
            click.echo(f"Error: Required module not found: {e}")
        except Exception as e:
            click.echo(f"Error: {e}")


# --- UI command (combined search + briefing) ---
_ai_scheduler = None


def _start_ai_scheduler():
    """Start the AI briefing scheduler for UI mode."""
    global _ai_scheduler
    try:
        # 一次性迁移旧数据目录（仓库外）到仓库内 data/，幂等可重复调用
        from intelnexus.config.paths import migrate_legacy_data_files
        migrate_legacy_data_files()

        from intelnexus.briefing.scheduler import AIBriefingScheduler
        # 与手动推送共用持久化邮件配置（文件 + 环境变量合并），不再只读环境变量
        from intelnexus.config.email_settings import get_active_email_config
        email_config = get_active_email_config()
        _ai_scheduler = AIBriefingScheduler(email_config=email_config)
        _ai_scheduler.start()
        # 注册到调度器注册表：订阅者增删改后可热更新定时任务（无需重启）
        from intelnexus.briefing.scheduler_registry import register_scheduler
        register_scheduler(_ai_scheduler)
    except Exception:
        pass


def _auto_open_browser(port: int, delay: float = 1.5) -> None:
    """后台线程：等待 Streamlit 服务器就绪后自动打开浏览器。

    对非技术用户最关键的一步——双击 EXE 后浏览器自动弹出，
    无需手动输入地址。轮询 localhost 直到收到 HTTP 响应，
    超时 30 秒放弃（避免无限阻塞）。
    """
    import time
    import urllib.request
    url = f"http://localhost:{port}"
    deadline = time.monotonic() + 30
    time.sleep(delay)  # 给 Streamlit 一点启动时间
    while time.monotonic() < deadline:
        try:
            urllib.request.urlopen(url, timeout=2)
            webbrowser.open(url)
            return
        except Exception:
            time.sleep(0.5)


@intelnexus.command()
@click.option("--ui-port", default=8501, show_default=True, type=int, help="Port for Streamlit UI")
@click.option("--ui-host", default="localhost", show_default=True, type=str, help="Host for Streamlit UI")
@click.option("--no-scheduler", is_flag=True, help="Disable AI briefing scheduler")
@click.option("--no-browser", is_flag=True, help="Disable auto-open browser")
def ui(ui_port, ui_host, no_scheduler, no_browser):
    """Run IntelNexus in Web UI mode."""
    from streamlit.web import cli as stcli

    if getattr(sys, "frozen", False):
        base = sys._MEIPASS
    else:
        base = os.path.dirname(__file__)

    if not no_scheduler:
        _start_ai_scheduler()

    # 自动打开浏览器：对 EXE 用户（非技术人员）最关键，
    # 源码模式也受益（省去手动输入地址的步骤）。
    if not no_browser:
        t = threading.Thread(
            target=_auto_open_browser,
            args=(ui_port,),
            daemon=True,
        )
        t.start()

    ui_script = os.path.join(base, "ui.py")
    # 用环境变量传 server 配置，避免 CLI --server.* 参数与 config.toml
    # [server] 段冲突触发 "An update to the [server] config option..." 警告。
    os.environ["STREAMLIT_SERVER_PORT"] = str(ui_port)
    os.environ["STREAMLIT_SERVER_ADDRESS"] = ui_host
    sys.argv = [
        "streamlit", "run", ui_script,
        "--global.developmentMode=false",
    ]
    sys.exit(stcli.main())


# Register sub-project commands
_register_search_commands()
_register_briefing_commands()


# EXE 双击启动：无参数时默认进入 Web UI（与 run.bat 行为一致）
if getattr(sys, "frozen", False) and len(sys.argv) == 1:
    sys.argv.append("ui")

if __name__ == "__main__":
    intelnexus()
