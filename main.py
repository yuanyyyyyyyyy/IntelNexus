"""
IntelNexus - AI Multi-Source Network Intelligence Platform
=========================================================
A unified search interface for news and web content.
"""

import os
import click
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor, as_completed

from scrape import scrape_multiple
from web_search import get_web_results
from news_search import get_news_results
from darkweb_search import get_darkweb_results, is_available as darkweb_available

from llm import get_llm, refine_query, generate_summary
from llm_utils import get_model_choices


MODEL_CHOICES = get_model_choices()

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
            futures.append(executor.submit(get_news_results, query, 15))
        
        if mode in ["darkweb", "all"] and darkweb_available():
            futures.append(executor.submit(get_darkweb_results, query, max_workers))
        
        for future in as_completed(futures):
            try:
                source = future.result()
                if source:
                    results.extend(source)
            except Exception as e:
                print(f"Search error: {e}")
    
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
    type=click.Choice(MODEL_CHOICES),
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
def search(model, query, mode, threads, output):
    """Run IntelNexus in CLI mode."""
    
    click.echo(f"IntelNexus - {SEARCH_MODES.get(mode, mode)} Mode")
    click.echo(f"Model: {model}")
    click.echo(f"Query: {query}")
    
    llm = get_llm(model)
    
    click.echo("[1/4] Refining query...")
    refined_query = refine_query(llm, query)
    click.echo(f"    Refined: {refined_query}")
    
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
    
    click.echo("[5/5] Generating summary...")
    summary = generate_summary(llm, query, scraped_results)
    
    if not output:
        now = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
        filename = f"report_{now}.md"
    else:
        filename = output + ".md"
    
    with open(filename, "w", encoding="utf-8") as f:
        f.write(summary)
        click.echo(f"\n[OUTPUT] Report saved to {filename}")


@intelnexus.command()
def ui():
    """Run IntelNexus in GUI mode."""
    from gui import run_gui
    run_gui()


if __name__ == "__main__":
    intelnexus()
