"""Pytest configuration for StoryForge tests."""

import sys
from pathlib import Path

# Add tools and hooks to Python path for imports
plugin_root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(plugin_root / "tools"))
sys.path.insert(0, str(plugin_root))
