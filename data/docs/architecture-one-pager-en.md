# IntelNexus — Architecture One-Pager

## Project Vision

**AI-powered multi-source intelligence analysis platform** that automates the entire pipeline: Search → Analyze → Report → Deliver — for cybersecurity and AI policy analysts.

---

## System Architecture

```
┌─────────────────────────────────────────────────────────────────────┐
│                     User Interface (Streamlit / CLI)                │
├─────────────────────────────────────────────────────────────────────┤
│                                                                     │
│  ┌─────────────┐    ┌──────────────────┐    ┌─────────────────┐    │
│  │ Search       │    │ Auto-Briefing    │    │ Knowledge Base  │    │
│  │ Workbench    │    │ System           │    │ Manager (RAG)   │    │
│  │ (Forensics)  │    │ (Daily Patrol)   │    │                 │    │
│  └──────┬──────┘    └────────┬─────────┘    └────────┬────────┘    │
│         │                    │                       │              │
│         ▼                    ▼                       ▼              │
│  ┌─────────────────────────────────────────────────────────────┐   │
│  │           Topic Registry (Intelligence Hub)                 │   │
│  │     Search Queries ←→ Persistent Topics ←→ Briefing Cats   │   │
│  └─────────────────────────────────────────────────────────────┘   │
│         │                    │                       │              │
│         ▼                    ▼                       ▼              │
│  ┌─────────────┐    ┌──────────────────┐    ┌─────────────────┐    │
│  │ Search       │    │ Analysis Engine  │    │ Output Engine   │    │
│  │ Engine       │    │ M-SCORE / CIDAR  │    │ LLM + Push      │    │
│  │ (15 Sources) │    │                  │    │                 │    │
│  └─────────────┘    └──────────────────┘    └─────────────────┘    │
│                                                                     │
└─────────────────────────────────────────────────────────────────────┘
```

---

## Data Flow

### Search Pipeline (10 Steps)

```
User Query
    │
    ▼
① Model Preflight → ② Query Expansion (cross-lingual + spellcheck)
    │
    ▼
③ Registry Dispatch → ④ Parallel Search (15 sources) → ⑤ Cross-source Dedup
    │
    ▼
⑥ Parallel Web Scraping → ⑦ M-SCORE Credibility Scoring → ⑧ CIDAR Conflict Detection
    │
    ▼
⑨ Knowledge Graph Construction (spaCy NER + NetworkX)
    │
    ▼
⑩ LLM Structured Report Generation
```

### Briefing Pipeline (5 Steps)

```
6 Intelligence Categories (AI Gov / China Narrative / Legislation / Data Leak / Vuln / Attack)
    │
    ▼
① Parallel Collection → ② LLM Analysis → ③ Delta Diff (incremental awareness)
    │
    ▼
④ Personalized Filtering (per-subscriber interests) → ⑤ Multi-channel Push (Email/WeChat/DingTalk)
```

---

## Core Module Reference

| Module | Path | Purpose |
|--------|------|---------|
| **Search Source ABC** | `core/search/source.py` | Abstract base class for all search adapters |
| **Search Registry** | `core/search/registry.py` | Unified dispatcher for 15 search sources |
| **Source Health** | `core/search/health.py` | Auto-degradation (3=degraded, 6=down) |
| **Search Modes** | `core/search/modes.py` | Mode definitions (all/web/news/dark/threat) |
| **M-SCORE** | `analysis/credibility.py` | 4-dimension credibility scoring |
| **CIDAR** | `analysis/credibility.py` | 3-type conflict detection |
| **Knowledge Graph** | `analysis/intelligence_graph.py` | spaCy NER + NetworkX + PageRank |
| **Topic Registry** | `topics/registry.py` | Bidirectional flywheel hub |
| **Delta Diff** | `topics/diff.py` | Briefing incremental comparison |
| **Briefing Pipeline** | `briefing/pipeline.py` | Collect → Generate → Save → Push |
| **Briefing Collector** | `briefing/collector.py` | Parallel 6-category data collection |
| **Briefing Analyzer** | `briefing/analyzer.py` | LLM structured briefing generation |
| **Notifier** | `briefing/notifier.py` | Email/WeChat/DingTalk push |
| **Knowledge Retrieval** | `knowledge/retrieval.py` | RAG semantic search for KB |
| **LLM Core** | `core/llm/core.py` | Model instantiation, query expansion, report gen |

---

## Tech Stack

| Layer | Technology |
|-------|-----------|
| **Language** | Python 3.10+ |
| **Frontend** | Streamlit (Web) / Click (CLI) |
| **LLM Framework** | LangChain + Ollama (local-first) |
| **NLP** | spaCy (bilingual NER) + sentence-transformers |
| **Knowledge Graph** | NetworkX + PyVis (HTML visualization) |
| **Search/Scraping** | requests + BeautifulSoup4 + lxml |
| **Storage** | JSON + portalocker (file locking) |
| **Export** | fpdf2/reportlab (PDF) + python-docx (Word) |
| **Scheduling** | APScheduler (cron-based) |
| **Push** | SMTP + WeChat Work / DingTalk Webhooks |

---

## Key Design Decisions

### 1. Registry Pattern (Search Source Management)

**Problem:** 15 heterogeneous search sources with different formats

**Solution:** `BaseSearchSource` ABC + `SearchSourceRegistry` unified dispatcher

**Outcome:** Adding a new source = implement `search()`, zero changes to dispatch logic

### 2. Topic Registry Bidirectional Flywheel (Architectural Core)

**Problem:** Search tools and briefing tools are disconnected

**Solution:** Topic Registry as the hub — search queries become persistent topics driving briefings; high-severity briefing items trigger forensic searches

**Outcome:** Self-improving flywheel — the more you use it, the more precise it gets

### 3. M-SCORE Multi-Dimension Credibility Scoring

**Problem:** Multi-source intelligence varies in quality, hard to assess quickly

**Solution:** 4-dimension scoring (Domain Authority 30% + Freshness 25% + Depth 25% + Cross-source Consistency 25%)

**Outcome:** Every result carries a credibility score to assist decision-making

---

## Key Metrics

| Metric | Value |
|--------|-------|
| Python Files | 127 |
| Total Lines of Code | 21,526 |
| Core Package Lines | 18,205 |
| Test Lines | 2,738 |
| Test Files | 30 |
| Search Source Adapters | 15 |
| Briefing Categories | 6 |
| Credibility Dimensions | 4 |
| Conflict Detection Types | 3 |
| Supported Languages | 2 (Chinese / English) |
| Push Channels | 3 (Email / WeChat / DingTalk) |
| LLM Providers | 6+ (Ollama/OpenAI/Anthropic/Google/DeepSeek/...) |
