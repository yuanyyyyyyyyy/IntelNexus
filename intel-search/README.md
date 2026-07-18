# IntelNexus - Multi-Source Intelligence Search & Analysis

A unified search interface for news and web content with AI-powered analysis.

## Features

- **Multi-source search**: Web, news, and dark web (Tor) search
- **Query refinement**: AI-optimized search queries
- **Credibility assessment**: Source scoring and conflict detection
- **Knowledge graph**: Entity extraction and relationship mapping
- **Report generation**: AI-powered intelligence reports
- **Export formats**: PDF, Word, Markdown

## Quick Start

```bash
# Install dependencies
pip install -r requirements.txt

# Run CLI search
python main.py search --query "your query" --mode all

# Run Web UI
python main.py ui
```

## Commands

| Command | Description |
|---------|-------------|
| `search` | CLI search with report generation |
| `ui` | Launch Streamlit web interface |

## Configuration

Copy `config.example.py` to `config.py` and set your API keys:

```python
NEWS_API_KEY = "your-news-api-key"
```

## Architecture

```
intel-search/
├── main.py              # CLI entry point
├── ui.py                # Streamlit UI entry point
├── config.py            # Configuration
├── src/
│   ├── analysis/        # Credibility, knowledge graph, evidence tracing
│   ├── config/          # File locking, caching
│   ├── export/          # PDF, Word, Excel export
│   ├── llm/             # LLM integration (OpenAI, Ollama, etc.)
│   ├── search/          # Web, news, dark web search
│   └── ui/              # Streamlit UI components
└── tests/               # Test suite
```
