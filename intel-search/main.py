"""
IntelNexus - AI Multi-Source Network Intelligence Platform (Search)
=================================================================
A unified search interface for news and web content.
"""

import os
import sys

# Add shared library to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "shared"))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from config import NEWS_API_KEY

# Inject config into shared library
from shared.settings import set as set_config
set_config({
    "OLLAMA_BASE_URL": os.getenv("OLLAMA_BASE_URL", "http://localhost:11434"),
    "OPENROUTER_BASE_URL": os.getenv("OPENROUTER_BASE_URL", ""),
    "OPENROUTER_API_KEY": os.getenv("OPENROUTER_API_KEY", ""),
    "GOOGLE_API_KEY": os.getenv("GOOGLE_API_KEY", ""),
    "NEWS_API_KEY": NEWS_API_KEY,
})

import click
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor, as_completed

from shared.logger import get_logger
from shared.search.scraper import scrape_multiple
from shared.search.web import get_web_results
from shared.search.news import get_news_results
from src.search.darkweb import get_darkweb_results, is_available as darkweb_available

from shared.llm.core import get_llm, expand_query, generate_summary
from shared.llm.utils import get_model_choices

logger = get_logger(__name__)


SEARCH_MODES = {
    "web": "Web Search",
    "news": "News Articles",
    "darkweb": "Dark Web (Optional)",
    "all": "All Sources"
}


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
    refined_query = expand_query(query)
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
def ui(ui_port, ui_host):
    """Run IntelNexus in Web UI mode."""
    from streamlit.web import cli as stcli
    
    if getattr(sys, "frozen", False):
        base = sys._MEIPASS
    else:
        base = os.path.dirname(__file__)
    
    ui_script = os.path.join(base, "ui.py")
    sys.argv = [
        "streamlit", "run", ui_script,
        f"--server.port={ui_port}",
        f"--server.address={ui_host}",
        "--global.developmentMode=false",
    ]
    sys.exit(stcli.main())


if __name__ == "__main__":
    intelnexus()
