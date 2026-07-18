"""
IntelNexus - AI Multi-Source Network Intelligence Platform
=========================================================
A unified search interface for news and web content.
"""

import os
import sys
import click
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor, as_completed

from src.logger import get_logger
from src.search.scraper import scrape_multiple
from src.search.web import get_web_results
from src.search.news import get_news_results
from src.search.darkweb import get_darkweb_results, is_available as darkweb_available

from src.llm.core import get_llm, refine_query, generate_summary
from src.llm.utils import get_model_choices
from config import NEWS_API_KEY

logger = get_logger(__name__)


SEARCH_MODES = {
    "web": "Web Search",
    "news": "News Articles",
    "darkweb": "Dark Web (Optional)",
    "all": "All Sources"
}

# AI简报调度器全局实例
_ai_scheduler = None


def execute_search(mode, query, max_workers):
    results = []
    
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = []
        
        if mode in ["web", "all"]:
            futures.append(executor.submit(get_web_results, query, max_workers, 20))
        
        if mode in ["news", "all"]:
            futures.append(executor.submit(get_news_results, query, 15, api_key=NEWS_API_KEY))
        
        if mode in ["darkweb", "all"] and darkweb_available():
            futures.append(executor.submit(get_darkweb_results, query, max_workers))
        
        for future in as_completed(futures):
            try:
                source = future.result()
                if source:
                    results.extend(source)
            except Exception as e:
                logger.warning(f"Search error: {e}")
    
    return results


@click.group()
@click.version_option()
def intelnexus():
    """IntelNexus: AI-Powered Multi-Source Network Intelligence Platform."""
    pass


@intelnexus.command()
@click.option(
    "--model", "-m",
    default="qwen2.5:7b",
    show_default=True,
    help="Select LLM model (local or cloud)"
)
@click.option("--query", "-q", required=True, type=str, help="Search query")
@click.option(
    "--mode", "-s",
    default="all",
    type=click.Choice(["web", "news", "darkweb", "all"]),
    help="Search mode"
)
@click.option("--threads", "-t", default=5, show_default=True, type=int, help="Number of threads")
@click.option("--output", "-o", type=str, help="Output filename")
@click.option("--no-credibility", is_flag=True, help="Disable credibility assessment & knowledge graph")
def search(model, query, mode, threads, output, no_credibility):
    """Run IntelNexus in CLI mode."""
    
    click.echo(f"IntelNexus - {SEARCH_MODES.get(mode, mode)} Mode")
    click.echo(f"Model: {model}")
    click.echo(f"Query: {query}")
    
    try:
        llm = get_llm(model)
    except ValueError as e:
        click.echo(f"Error: {e}")
        return
    
    click.echo("[1/4] Refining query...")
    refined_query = refine_query(query)
    click.echo(f"    Refined: {' | '.join(refined_query)}")
    
    click.echo(f"[2/4] Searching {mode}...")
    search_results = execute_search(mode, refined_query, threads)
    click.echo(f"    Found {len(search_results)} results")
    
    if not search_results:
        click.echo("No results found.")
        return
    
    # 保留所有搜索结果（不过滤）
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
        from src.analysis.credibility import SourceScorer, ConflictDetector
        scorer = SourceScorer()
        scorer.evaluate(search_filtered, scraped_results)

        # Build credibility context from scored results
        cred_lines = []
        for r in search_filtered[:15]:
            score = r.get("credibility_score", 0.5)
            details = r.get("credibility_details", {})
            reason = details.get("reason", "")
            source = r.get("source", "Unknown")
            cred_lines.append(f"- {source}: 可信度 {score:.2f} ({reason})")
        credibility_context = "\n".join(cred_lines)

        detector = ConflictDetector()
        conflicts_list = detector.detect(search_filtered, scraped_results)
        if conflicts_list:
            conflicts_context = "\n".join(
                [f"- ⚠️ [{c['type']}] {c['description']}"
                 for c in conflicts_list[:5]])

        click.echo("[4.6/5] Building knowledge graph...")
        from src.analysis.intelligence_graph import EntityExtractor, IntelligenceGraph
        extractor = EntityExtractor()
        kg_raw = extractor.extract(scraped_results)
        kg = IntelligenceGraph()
        kg.build(kg_raw["entities"], kg_raw["relations"])
        top_entities = sorted(kg_raw["entities"],
                              key=lambda e: e["importance"], reverse=True)[:10]
        kg_context = "\n".join(
            [f"- {e['name']} ({e['type']})" for e in top_entities])
        kg_path = kg.export_html(
            f"report_kg_{datetime.now().strftime('%Y%m%d%H%M%S')}.html")
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


@intelnexus.command()
@click.option("--ui-port", default=8501, show_default=True, type=int, help="Port for Streamlit UI")
@click.option("--ui-host", default="localhost", show_default=True, type=str, help="Host for Streamlit UI")
@click.option("--no-scheduler", is_flag=True, help="Disable AI briefing scheduler")
def ui(ui_port, ui_host, no_scheduler):
    """Run IntelNexus in Web UI mode."""
    from streamlit.web import cli as stcli
    
    if getattr(sys, "frozen", False):
        base = sys._MEIPASS
    else:
        base = os.path.dirname(__file__)
    
    # 启动AI简报调度器
    if not no_scheduler:
        _start_ai_scheduler()
    
    ui_script = os.path.join(base, "ui.py")
    sys.argv = [
        "streamlit", "run", ui_script,
        f"--server.port={ui_port}",
        f"--server.address={ui_host}",
        "--global.developmentMode=false",
    ]
    sys.exit(stcli.main())


def _start_ai_scheduler():
    """启动AI简报调度器"""
    global _ai_scheduler
    try:
        from ai_briefing.scheduler import AIBriefingScheduler
        
        # 从环境变量读取邮件配置（与 briefing 命令一致）
        email_config = {
            "smtp_server": os.getenv("SMTP_SERVER", ""),
            "smtp_port": int(os.getenv("SMTP_PORT", "587")),
            "username": os.getenv("SMTP_USERNAME", ""),
            "password": os.getenv("SMTP_PASSWORD", ""),
            "use_tls": os.getenv("SMTP_USE_TLS", "true").lower() == "true"
        }
        # 如果 SMTP 未配置，传 None
        if not email_config.get("smtp_server") or not email_config.get("username"):
            email_config = None

        _ai_scheduler = AIBriefingScheduler(
            email_config=email_config
        )
        _ai_scheduler.start()
        logger.info("AI Briefing Scheduler started")
    except ImportError as e:
        logger.warning(f"Could not start AI scheduler: {e}")
    except Exception as e:
        logger.error(f"Error starting AI scheduler: {e}")


@intelnexus.command()
@click.option("--model", "-m", default="qwen2.5:7b", help="LLM model to use")
@click.option("--notify-only", is_flag=True, help="Only send notifications, don't generate report")
@click.option("--format", "-f", "export_format", type=click.Choice(["md", "html", "pdf", "all"]), default="all", help="Export format")
def briefing(model, notify_only, export_format):
    """Generate and send AI briefing to all subscribers."""
    try:
        from ai_briefing.collector import AIBriefingCollector
        from ai_briefing.analyzer import AIBriefingAnalyzer
        from ai_briefing.notifier import AIBriefingNotifier
        from ai_briefing.config import BRIEFING_CONFIG
        from src.config.subscriptions import get_active_subscribers, update_last_sent
        from ai_briefing.templates import render_markdown_briefing, render_email_html, markdown_to_html_sections
        
        click.echo("AI Briefing Generator")
        click.echo("=" * 50)
        
        # 1. 获取活跃订阅者
        subscribers = get_active_subscribers()
        if not subscribers:
            click.echo("No active subscribers found.")
            return
        
        click.echo(f"Found {len(subscribers)} active subscribers")
        
        # 2. 初始化模块
        collector = AIBriefingCollector()
        llm = get_llm(model)
        analyzer = AIBriefingAnalyzer(llm=llm)
        
        # 3. 采集数据
        click.echo("\n[1/4] Collecting data...")
        collected_data = collector.collect_all_categories()
        for cat, results in collected_data.items():
            click.echo(f"  - {cat}: {len(results)} results")
        
        # 4. 生成简报
        click.echo("\n[2/4] Generating briefing...")
        organization_name = BRIEFING_CONFIG["organization"]["name"]
        briefing_md = analyzer.generate_briefing(collected_data, organization_name)
        
        # 5. 生成HTML版本
        briefing_html = None
        try:
            sections = markdown_to_html_sections(briefing_md)
            briefing_html = render_email_html(
                generated_date=datetime.now().strftime("%Y年%m月%d日"),
                organization_name=organization_name,
                **sections
            )
        except Exception as e:
            click.echo(f"  Warning: Could not generate HTML: {e}")
        
        # 6. 保存简报到历史
        from src.config.briefing_history import get_briefing_history
        briefing_filename = get_briefing_history().save_briefing(
            markdown_content=briefing_md,
            html_content=briefing_html,
            organization_name=organization_name,
            categories=list(collected_data.keys()),
            subscribers_count=len(subscribers)
        )
        click.echo(f"  Briefing saved to: data/briefings/{briefing_filename}")
        
        # 7. 导出简报文件
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
                from src.export.briefing_export import export_briefing_pdf
                pdf_path = f"data/briefings/briefing_{timestamp}.pdf"
                export_briefing_pdf(briefing_md, pdf_path)
                click.echo(f"  PDF exported: {pdf_path}")
            except Exception as e:
                click.echo(f"  Warning: Could not export PDF: {e}")
        
        # 8. 推送简报
        click.echo("\n[3/4] Sending notifications...")
        
        # 获取邮件配置（从环境变量或配置文件）
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
                click.echo(f"    ✓ Sent successfully")
            else:
                click.echo(f"    ✗ Failed to send")
        
        # 9. 完成
        click.echo("\n[4/4] Complete!")
        click.echo(f"  Sent {success_count}/{len(subscribers)} briefings")
        click.echo(f"  Briefing saved to: data/briefings/{briefing_filename}")
        
    except ImportError as e:
        click.echo(f"Error: Required module not found: {e}")
        click.echo("Please install dependencies: pip install -r requirements.txt")
    except Exception as e:
        click.echo(f"Error: {e}")


@intelnexus.command()
def scheduler():
    """Run the AI briefing scheduler in background."""
    try:
        from ai_briefing.scheduler import AIBriefingScheduler
        import signal
        
        click.echo("AI Briefing Scheduler")
        click.echo("=" * 50)
        
        scheduler_instance = AIBriefingScheduler()
        scheduler_instance.start()
        
        click.echo("Scheduler started. Press Ctrl+C to stop.")
        
        # 保持运行
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


if __name__ == "__main__":
    intelnexus()
