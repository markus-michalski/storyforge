"""Pytest configuration for StoryForge tests."""

import sys
from pathlib import Path

# Add tools and hooks to Python path for imports
plugin_root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(plugin_root / "tools"))
sys.path.insert(0, str(plugin_root))

# The MCP server directory has a hyphen in its name, which is not a valid Python
# module identifier. Add it directly to sys.path so tests can import it as "server".
sys.path.insert(0, str(plugin_root / "servers" / "storyforge-server"))
