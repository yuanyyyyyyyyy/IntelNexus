# IntelNexus - AI Daily Briefing System

Automated AI intelligence briefing generation and distribution.

## Features

- **Automated collection**: RSS feeds and web sources
- **AI analysis**: LLM-powered content summarization
- **Multi-channel delivery**: Email, WeChat Work, DingTalk
- **Scheduled execution**: Cron-based scheduling
- **History tracking**: Briefing archive with HTML preview

## Quick Start

```bash
# Install dependencies
pip install -r requirements.txt

# Generate and send briefing
python main.py briefing

# Run scheduler in background
python main.py scheduler

# Run Web UI
python main.py ui
```

## Commands

| Command | Description |
|---------|-------------|
| `briefing` | Generate and send briefing to subscribers |
| `scheduler` | Run background scheduler |
| `ui` | Launch Streamlit web interface |

## Configuration

### Environment Variables

```bash
# SMTP settings
SMTP_SERVER=smtp.example.com
SMTP_PORT=587
SMTP_USERNAME=your-email@example.com
SMTP_PASSWORD=your-password
SMTP_USE_TLS=true
```

### Data Files

- `data/subscriptions.json` - Subscriber list
- `data/sources.json` - Data sources
- `data/briefings/` - Briefing archive

## Architecture

```
intel-briefing/
├── main.py              # CLI entry point
├── ui.py                # Streamlit UI entry point
├── config.py            # Configuration
├── ai_briefing/         # Core briefing module
│   ├── analyzer.py      # LLM analysis
│   ├── collector.py     # Data collection
│   ├── config.py        # Categories and settings
│   ├── notifier.py      # Multi-channel delivery
│   ├── scheduler.py     # Cron scheduling
│   └── templates.py     # Markdown/HTML templates
├── src/
│   ├── config/          # Subscriptions, sources, history
│   ├── export/          # PDF export
│   ├── llm/             # LLM integration
│   ├── search/          # Web, news search
│   └── ui/              # Streamlit UI components
└── tests/               # Test suite
```
