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

# When running with the system pytest (not the venv's pytest), mcp and other
# dependencies may be missing. Inject the plugin venv's site-packages so that
# `pytest -q` from the project root works regardless of which Python is active.
_venv_site = Path.home() / ".storyforge" / "venv" / "lib" / "python3.12" / "site-packages"
if _venv_site.is_dir() and str(_venv_site) not in sys.path:
    sys.path.insert(0, str(_venv_site))
