# IntelNexus - Interview Q&A Cheat Sheet

> 40+ high-frequency interview questions covering project overview, architecture, core modules, tech choices, and challenges.
> Review 5 minutes before interview.

---

## Part 1: Project Overview (5 Questions)

### Q1: What does this project do?

**A:** IntelNexus is an AI-powered multi-source intelligence analysis platform for cybersecurity and AI policy analysts. It automates the entire pipeline: Search, Analyze, Report, Deliver. It collects intelligence from 15 sources (web, news, dark web, vulnerability databases, security vendors), uses LLMs for credibility scoring and conflict detection, generates structured reports, and pushes briefings to subscribers via Email/WeChat/DingTalk.

**Follow-up: Why did you build this?**
**A:** Analysts manually collect and cross-reference information from dozens of sources daily - it is inefficient and easy to miss critical intel. My platform automates the repetitive work so humans can focus on decision-making.

---

### Q2: What was your role? How much code?

**A:** Sole full-stack developer. Architecture, core algorithms, frontend, and deployment - all me.

Key metrics:
- 127 Python files, 21,526 lines of code
- Core package: 18,205 lines, Tests: 2,738 lines (30 test files)
- 15 search source adapters
- 6 briefing categories

---

### Q3: What are the technical highlights?

**A:** Three core innovations:

1. **Topic Registry Bidirectional Flywheel** - Search and briefing are connected. User search queries become persistent topics driving briefings; high-severity briefing items trigger forensic searches.
2. **M-SCORE Credibility Scoring** - 4-dimension scoring (Domain Authority 30% + Freshness 25% + Depth 25% + Cross-source Consistency 25%).
3. **CIDAR Conflict Detection** - Automatically detects numeric discrepancies, temporal inconsistencies, and stance conflicts across sources.

---

### Q4: What are the main modules?

**A:** Four modules:

| Module | Function |
|--------|----------|
| **Search Engine Layer** | 15 search adapters + Registry dispatcher + Health monitoring |
| **Analysis Engine Layer** | M-SCORE scoring + CIDAR conflict detection + Knowledge graph |
| **Briefing Engine Layer** | 6-category parallel collection + LLM analysis + Delta diff + Multi-channel push |
| **Knowledge Management Layer** | Topic Registry flywheel + RAG retrieval + Knowledge base |

---

### Q5: What did you learn?

**A:** Three areas:

1. **Architecture Design** - Practical application of Registry pattern, pipeline pattern, singleton + double-check locking.
2. **NLP Engineering** - From theory to practice: NER entity extraction, knowledge graph construction, semantic similarity computation.
3. **System Design** - Concurrency, error isolation, graceful degradation, incremental awareness.

---

## Part 2: Architecture Design (8 Questions)

### Q6: What is the overall architecture?

**A:** Three-layer architecture:

`
Search Layer (15-source Registry + Concurrent Dispatch)
    |
Analysis Layer (M-SCORE + CIDAR + Knowledge Graph)
    |
Output Layer (LLM Reports + Auto Briefing + Multi-channel Push)
`

Topic Registry sits in the middle as the hub connecting search and briefing. Two frontends (Streamlit Web UI and CLI) share the same core logic.

---

### Q7: Why layered architecture?

**A:** Separation of concerns. Each layer does one thing: search layer only collects, analysis layer only scores, output layer only generates and pushes. Each layer can be tested independently. Swapping LLM only changes the output layer - search and analysis remain untouched.

---

### Q8: What is the Topic Registry? Why is it the core?

**A:** Topic Registry is the bridge between search and briefing. Traditionally, search tools and briefing tools are disconnected. My design connects them through Topic Registry:

- **Forward:** User searches a query, can pin it as a persistent Topic, this Topic appears in automated briefing patrol
- **Reverse:** Briefing detects high-severity item, can trigger a forensic search task

This is the bidirectional flywheel - the more you use it, the more precise it gets.

---

### Q9: How does the bidirectional flywheel work?

**A:** Example:

1. User searches "AI chip export controls" - system returns results
2. User clicks "Pin" - this query becomes a persistent Topic (origin="user_search")
3. Next briefing patrol - this Topic is included as a collection target
4. Briefing generates - discovers "Company X violated export controls" (high-severity)
5. User clicks "Forensics" - system automatically searches using this item as a query

This creates a closed loop where user behavior continuously optimizes system output.

---

### Q10: Why the Registry pattern?

**A:** 15 search sources with different formats. Without Registry, you would need if-else chains with 15 branches. With Registry, each source extends BaseSearchSource, implements search() and normalize_result(). SearchSourceRegistry dispatches uniformly, runs concurrently, deduplicates automatically. Adding a new source = writing one adapter class, zero changes to dispatch logic.

---

### Q11: How do you handle concurrency?

**A:** ThreadPoolExecutor. Each search source gets its own thread. collect() method unifies the output. Why threads instead of asyncio?

1. Search is IO-bound - threads are sufficient
2. asyncio has steep learning curve and worse readability
3. Third-party libraries (requests) have inconsistent async support

---

### Q12: How do you handle errors?

**A:** Multi-level fault tolerance:

1. **Source level:** SourceHealth tracks success/fail counts. 3 consecutive failures = degraded (skipped), 6 = down (disabled)
2. **Module level:** Each stage has independent try/except. Single module failure does not break the whole pipeline
3. **Data level:** spaCy missing = NER returns empty, LLM unavailable = error template, KB unavailable = empty RAG context

This is **graceful degradation**.

---

### Q13: How is data persisted?

**A:** JSON files + portalocker file locking.

Why:
- Single-user desktop tool, no database service needed
- JSON is human-readable for debugging
- portalocker provides cross-platform file locking for concurrent safety
- Zero deployment dependencies

Persisted data: sources.json, subscriptions.json, topics.json, source_health.json, briefings/.

---

## Part 3: Search Module (6 Questions)

### Q14: What are the 15 search sources?

**A:**

| Category | Sources |
|----------|---------|
| **General** | WebSearchSource, NewsSearchSource, UserSource |
| **Dark Web** | DarkWebSource |
| **Vulnerability Intel** | NVDSearchSource, CISAKEVSource, CNVDSource, ExploitDBSource |
| **Threat Intel** | AlienVaultOTXSource, QianxinSource |
| **Community/Academic** | HackerNewsSource, ArxivSource, HuggingFaceSource, TechCommunitySource |
| **Security Vendors** | SecurityNewsSource |

All extend BaseSearchSource with unified output: {title, url, description, source, category, published_at, metadata}.

---

### Q15: What does it take to add a new search source?

**A:** Three steps:

1. Create intelnexus/core/search/sources/my_source.py
2. Extend BaseSearchSource, implement search() and normalize_result()
3. Register one line in registry.py

No changes to dispatch logic. This is the Open/Closed Principle - open for extension, closed for modification.

---

### Q16: How does deduplication work?

**A:** Two layers:

1. **Intra-source:** Each source does internal blacklist/relevance filtering
2. **Cross-source:** registry.collect() deduplicates by normalized URL (unified scheme, strip trailing slash, lowercase domain)

Why layered: avoids changing result set semantics. Intra-source filtering = "this source should not return this", Registry dedup = "this result was already returned by another source".

---

### Q17: What does query expansion do?

**A:** LLM-driven query enhancement:

1. **Spell correction:** "CVE-2024-1234" auto-completes to "CVE-2024-12345"
2. **Cross-lingual variants:** Chinese query generates English variants and vice versa
3. **Synonym expansion:** vulnerability-related terms

Purpose: improve search recall, avoid missing critical intel due to language differences.

---

### Q18: How does health monitoring work?

**A:** SourceHealth class tracks each source:

- success_count / fail_count: cumulative counts
- consecutive_failures: consecutive failure streak
- avg_latency_ms: sliding average latency

Degradation rules:
- consecutive_failures >= 3: status = "degraded" (Registry skips)
- consecutive_failures >= 6: status = "down" (fully disabled)
- Each success resets consecutive_failures = 0

Auto-recovery: if a degraded source succeeds later, it automatically returns to healthy.

---

### Q19: How does dark web search work?

**A:** Through Tor proxy accessing .onion sites. DarkWebSource routes requests via SocksProxy to local Tor (default port 9150), then parses HTML with BeautifulSoup. Requires user to have Tor Browser installed locally.

---

## Part 4: Analysis Module (6 Questions)

### Q20: What is M-SCORE?

**A:** M-SCORE = Multi-Source Credibility Oriented Ranking and Evaluation. A 4-dimension credibility scoring system:

| Dimension | Weight | Calculation |
|-----------|--------|-------------|
| Domain Authority | 30% | TLD bonus (.gov=0.9) then Trusted domain DB (reuters=0.9) then Default 0.5 |
| Content Freshness | 25% | More recent = higher score |
| Content Depth | 25% | Length, keyword density, structure |
| Cross-source Consistency | 25% | sentence-transformers semantic similarity |

Final score 0-1, attached to every search result for analyst decision-making.

---

### Q21: How is domain authority calculated?

**A:** Three tiers:

1. **TLD tier:** .gov/.gov.cn = 0.90, .mil = 0.85, .edu = 0.80, .org = 0.70
2. **Trusted domain DB:** Covers government, authoritative media (reuters, bbc), security vendors (kaspersky, mandiant), academic (arxiv), etc.
3. **Default:** 0.5 for unknown domains

Reference credibility assessment frameworks from intelligence analysis domain.

---

### Q22: How is cross-source consistency calculated?

**A:** sentence-transformers semantic similarity:

1. Embed texts from multiple sources about the same event
2. Compute pairwise cosine similarity
3. Average similarity = consistency score

Why better than TF-IDF: sentence-transformers understands semantics. Different words with same meaning get high similarity.

---

### Q23: What does CIDAR detect?

**A:** CIDAR = Cross-source Inconsistency Detection with Adaptive Reasoning. Three conflict types:

1. **Numeric discrepancies:** Source A says "10 injured", Source B says "100 injured"
2. **Temporal inconsistencies:** Source A says "yesterday", Source B says "last month"
3. **Stance conflicts:** Source A says "attack succeeded", Source B says "attack blocked"

Uses regex + rule engine. Outputs conflict list to help analysts identify contradictions.

---

### Q24: How is the knowledge graph built?

**A:** Four steps:

1. **NER entity extraction:** spaCy bilingual models (zh_core_web_sm + en_core_web_sm), extracts PERSON/ORG/GPE etc.
2. **Co-occurrence relations:** Entities appearing in the same document get an edge, weight = co-occurrence count
3. **Graph construction:** NetworkX undirected weighted graph
4. **Analysis:** PageRank finds key entities (more documents mentioned = more important), community detection finds entity clusters

Visualization: PyVis generates interactive HTML with one line of code.

---

### Q25: Why NetworkX instead of Neo4j?

**A:** Context-appropriate choice:

- IntelNexus is a desktop analysis tool, not a web service
- NetworkX: Python-native, zero deployment overhead, in-memory, sufficient
- Neo4j: Requires server installation, suited for large-scale graph database scenarios

If building a SaaS with persistent large-scale graph data, would consider Neo4j.

---

## Part 5: Briefing Module (5 Questions)

### Q26: How many briefing categories?

**A:** Six:

| Category | Content |
|----------|---------|
| AI Government Usage | Government AI application dynamics |
| AI China Narrative | China AI development reports |
| Legislation | AI-related policies and regulations |
| Data Leaks | Data security incidents |
| Cyber Vulnerabilities | CVE/CNVD vulnerability alerts |
| Cyber Attacks | APT/Ransomware attack events |

Each has bilingual keywords for cross-language collection.

---

### Q27: What is delta diff (incremental awareness)?

**A:** Solves "information overload."

How: Compares URL sets between current and previous briefing, outputs "new/removed" items.

Implementation:
1. Extract previous briefing Markdown from history archive
2. Regex extract all URLs
3. Normalize URLs (strip UTM parameters etc.)
4. Compute set difference with current URLs

Result: analysts see "what is new today" at a glance.

---

### Q28: How does personalized push work?

**A:** Filter briefing content by subscriber's interests field.

Filtering logic:
- TOP3 highlights, delta overview, trend analysis: Always preserved (universal sections)
- Category details: Only keep sections matching interests
- Non-matching sections: Collapsed to "omitted" hint

---

### Q29: What push channels are available?

**A:** Three channels:

1. **SMTP Email:** TLS encryption via smtplib
2. **WeChat Work Webhook:** Push Markdown messages via Webhook URL
3. **DingTalk Webhook:** Push Markdown messages with signature

Each subscriber configures their preferred channel. One briefing can push to multiple channels simultaneously.

---

### Q30: How is scheduling implemented?

**A:** APScheduler background scheduler.

Config: Supports cron expressions (e.g., "8am daily"), runs in-process, no system-level cron needed.

Implementation: scheduler.py creates BackgroundScheduler, adds CronTrigger job, auto-triggers run_briefing_pipeline() at scheduled time.

Why not Celery: Too heavy - requires Redis/RabbitMQ as broker. APScheduler is lightweight, suitable for single-machine scenarios.

---

## Part 6: Tech Choices (8 Questions)

### Q31: Why Streamlit?

**A:** Three reasons:

1. **Rapid prototyping:** Pure Python, no HTML/CSS/JS needed
2. **Ecosystem fit:** Seamless integration with other Python code
3. **Sufficient:** Components like st.status, st.expander, st.columns meet all needs

For complex frontend interactions (drag-and-drop, real-time editing), would consider React + FastAPI.

---

### Q32: Why JSON instead of a database?

**A:** Context-appropriate:

- Single-user desktop tool, no multi-user concurrency needed
- JSON is human-readable for debugging
- portalocker file locking handles concurrent safety
- Zero deployment dependencies

For multi-user/multi-tenant: would migrate to SQLite (lightweight) or PostgreSQL (full-featured).

---

### Q33: Why spaCy instead of NLTK?

**A:** Three reasons:

1. **Speed:** spaCy is 10-100x faster (industrial optimization)
2. **Chinese support:** spaCy has zh_core_web_sm model, NLTK has weak Chinese support
3. **API design:** spaCy's nlp(text) one-liner vs NLTK's multi-step tokenization/POS/NER

NER accuracy: spaCy achieves ~90% F1 on CoNLL-2003, sufficient for intelligence analysis.

---

### Q34: Why Ollama instead of OpenAI?

**A:** Three reasons:

1. **Privacy first:** Intelligence analysis involves sensitive data - cannot send to cloud
2. **Offline capable:** No network dependency, suitable for secure environments
3. **Zero API cost:** No payment required

Model choice: Default to Ollama local models (e.g., qwen2.5:7b), also supports user-configured OpenAI/Anthropic/Google as fallback.

---

### Q35: Why sentence-transformers?

**A:** Semantic similarity computation.

Comparison:
- **TF-IDF:** Word frequency-based, cannot handle synonyms. "vulnerability" vs different phrasing gets 0 similarity
- **sentence-transformers:** Semantic understanding. Different words with same meaning get high similarity

Used in: M-SCORE cross-source consistency, Knowledge base RAG retrieval.

---

### Q36: Why PyVis?

**A:** One line of code generates interactive knowledge graph visualization:

`python
from pyvis.network import Network
net = Network()
# ... add nodes and edges
net.show("knowledge_graph.html")
`

100x simpler than D3.js, better interactivity than matplotlib. Generated HTML can be embedded in Streamlit.

---

### Q37: Why APScheduler?

**A:** Three reasons:

1. **Lightweight:** Runs in-process, no external services needed
2. **Flexible:** Supports cron, interval, and date triggers
3. **Good integration:** Seamless Python integration

Comparison:
- Celery: Requires Redis/RabbitMQ as broker, too heavy
- System cron: Not cross-platform, cannot call Python functions directly

---

### Q38: Why portalocker?

**A:** Solves JSON file concurrent read/write safety.

Scenario: Multiple threads reading/writing topics.json simultaneously may read inconsistent data.

portalocker provides cross-platform file locking (Windows: LockFileEx, Unix: fcntl):
- safe_read_json(): locked reads
- safe_write_json(): locked writes

Stronger than threading.Lock: threading.Lock only locks within process, portalocker locks across processes.

---

## Part 7: Challenges and Innovation (4 Questions)

### Q39: What was the biggest technical challenge?

**A:** Search source heterogeneity.

15 search sources return completely different formats: some return JSON APIs (NVD, HackerNews), some need web scraping (security vendor blogs), some need Tor proxy (dark web), some have official SDKs (arXiv).

Solution: Designed BaseSearchSource ABC + SearchSourceRegistry unified dispatcher. Each source only needs to implement search() and normalize_result(), dispatch logic knows nothing about specifics.

This pattern reduced adding a new source from "modify 10 files" to "add 1 file."

---

### Q40: How did you solve information overload?

**A:** Two mechanisms:

1. **Delta diff (incremental awareness):** Compares current vs previous briefing, only pushes new items. Analysts see "what is new today" at a glance.
2. **Personalized filtering (interests):** Each subscriber configures their interest categories, only receives relevant sections. People not interested in AI policy do not get AI governance briefings.

---

### Q41: What is the biggest innovation?

**A:** Topic Registry bidirectional flywheel.

Market tools are either search tools (Google Scholar) or briefing tools (Feedly) - they are disconnected.

My innovation connects them through Topic Registry:
- User search behavior becomes persistent topics, driving briefing content
- High-severity briefing items trigger forensic searches, reverse-optimizing search

This creates a self-improving flywheel - the more you use it, the more precise it gets.

---

### Q42: What would you redesign?

**A:** Three things:

1. **Add database support:** JSON is fine for prototype, but large-scale data needs SQLite/PostgreSQL
2. **Add permission system:** Currently single-user, multi-user needs role-based access
3. **Add more visualizations:** Timeline view, geographic distribution map beyond knowledge graph
4. **Add WebSocket:** Real-time search progress push instead of polling

---

## Part 8: Design Regrets and Shortcomings (3 Questions)

### Q43: Any architecture regrets?

**A:** Two regrets:

1. **Did not abstract from the start:** Early search sources were functional code, refactored to classes later. If I had used ABC+Registry from the beginning, would have saved significant refactoring time.
2. **JSON persistence limitations:** No transaction support, concurrent writes may lose data even with file locking. SQLite would have been safer.

---

### Q44: Where are the performance bottlenecks?

**A:** Two bottlenecks:

1. **Web scraping:** 15 sources search concurrently, but web scraping waits for HTTP responses. Slowest source drags down overall speed. Currently controlled via max_workers.
2. **LLM inference:** Report generation depends on local LLM. 7B model takes 30-60 seconds per report. Solution: streaming output shows real-time progress.

---

### Q45: What are the project shortcomings?

**A:** Three shortcomings:

1. **Test coverage:** 30 test files, 2,738 lines. Core algorithms (M-SCORE, CIDAR) need more boundary tests.
2. **Error handling:** Some search sources lack detailed exception handling for edge cases (network timeout, API rate limiting).
3. **Documentation:** Code comments mix Chinese and English, API docs incomplete.

---

## Quick Reference Cards

### 30-Second Elevator Pitch

"I built an AI-powered intelligence analysis platform that searches 15 sources concurrently, scores credibility with a 4-dimension system, detects cross-source conflicts, builds knowledge graphs, and generates structured reports with LLMs. The key innovation is a Topic Registry bidirectional flywheel - user search behavior feeds into automated briefings, and high-severity briefing items trigger forensic searches, creating a self-improving loop."

### Key Numbers

- **15** search source adapters
- **6** briefing categories
- **4** credibility dimensions
- **3** conflict detection types
- **21,526** lines of code
- **30** test files

### Core Design Patterns

- **Registry Pattern** - Search source management
- **ABC Abstract Base Class** - Unified search source interface
- **Singleton + Double-Check Lock** - LLM instances, Registry instances, NER extractor
- **Pipeline Pattern** - Search flow, briefing flow
- **Observer Pattern** - Health monitoring callbacks
