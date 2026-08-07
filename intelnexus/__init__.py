"""IntelNexus: unified AI multi-source network intelligence platform.

Single-package layout consolidating the former intel-search and intel-briefing
sub-projects:
  - core: search + LLM primitives (was shared/)
  - analysis: credibility / evidence / knowledge graph (was intel-search/src/analysis)
  - search_app: forensic search workbench UI + pipeline (was intel-search/src/ui + darkweb)
  - briefing: patrol/scheduling engine (was intel-briefing/ai_briefing)
  - topics: Topic Registry hub (search<->briefing closed loop)
  - config: JSON-backed config/data accessors
  - ui: unified shell (search + briefing tabs)
"""
