"""Shared test fixtures for IntelNexus test suite."""

import os
import sys

# Add project dirs first (so `import config` resolves to root config.py)
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))
# Then add shared library
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "shared"))

# Inject config for shared library
from shared.settings import set as set_config
set_config({
    "OLLAMA_BASE_URL": os.getenv("OLLAMA_BASE_URL", "http://localhost:11434"),
    "OPENROUTER_BASE_URL": os.getenv("OPENROUTER_BASE_URL", ""),
    "OPENROUTER_API_KEY": os.getenv("OPENROUTER_API_KEY", ""),
    "GOOGLE_API_KEY": os.getenv("GOOGLE_API_KEY", ""),
    "NEWS_API_KEY": os.getenv("NEWS_API_KEY", ""),
})

import pytest
