"""
IntelNexus - AI Daily Briefing System
=====================================
Automated AI intelligence briefing generation and distribution.
"""

import os
import sys

# Add shared library to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "shared"))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# Inject config into shared library
from shared.settings import set as set_config
set_config({
    "OLLAMA_BASE_URL": os.getenv("OLLAMA_BASE_URL", "http://localhost:11434"),
    "OPENROUTER_BASE_URL": os.getenv("OPENROUTER_BASE_URL", ""),
    "OPENROUTER_API_KEY": os.getenv("OPENROUTER_API_KEY", ""),
    "GOOGLE_API_KEY": os.getenv("GOOGLE_API_KEY", ""),
    "NEWS_API_KEY": os.getenv("NEWS_API_KEY", ""),
})

import click
from datetime import datetime

from shared.logger import get_logger
from shared.llm.core import get_llm

logger = get_logger(__name__)

# AI简报调度器全局实例
_ai_scheduler = None


@click.group()
@click.version_option()
def intelnexus():
    """IntelNexus: AI Daily Briefing System."""
    pass


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
            from ai_briefing.analyzer import format_briefing_date
            org_cfg = dict(BRIEFING_CONFIG["organization"])
            generated_date = format_briefing_date()
            sections = markdown_to_html_sections(briefing_md)
            briefing_html = render_email_html(
                generated_date=generated_date,
                organization=org_cfg,
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
                export_briefing_pdf(briefing_md, pdf_path, organization=org_cfg)
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
