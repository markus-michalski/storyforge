#!/usr/bin/env python3
"""Entry point for the StoryForge MCP server.

Interpreter selection happens in bin/run-server(.cmd) before this script runs —
this script assumes it is already running under the correct venv Python.
"""

import os
import runpy
import sys
from pathlib import Path


def main() -> None:
    """Set up import paths and launch server.py."""
    # Set plugin root for template/reference resolution
    plugin_root = os.environ.get("CLAUDE_PLUGIN_ROOT", str(Path(__file__).resolve().parent.parent.parent))
    os.environ["CLAUDE_PLUGIN_ROOT"] = plugin_root

    # Add plugin root to Python path so `tools` can be imported as a package
    if plugin_root not in sys.path:
        sys.path.insert(0, plugin_root)

    server_path = Path(__file__).resolve().parent / "server.py"
    runpy.run_path(str(server_path), run_name="__main__")


if __name__ == "__main__":
    main()
