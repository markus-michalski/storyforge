#!/usr/bin/env python3
"""Cross-platform launcher for the StoryForge MCP server.

Locates the correct Python venv and launches server.py with it.
"""

import os
import runpy
import sys
from pathlib import Path

VENV_PATH = Path.home() / ".storyforge" / "venv"


def main() -> None:
    """Find venv python and launch server."""
    # Set plugin root for template/reference resolution
    plugin_root = os.environ.get(
        "CLAUDE_PLUGIN_ROOT", str(Path(__file__).resolve().parent.parent.parent)
    )
    os.environ["CLAUDE_PLUGIN_ROOT"] = plugin_root

    # Add tools directory to Python path
    tools_path = str(Path(plugin_root) / "tools")
    if tools_path not in sys.path:
        sys.path.insert(0, tools_path)

    venv_python = VENV_PATH / "bin" / "python3"
    server_path = Path(__file__).resolve().parent / "server.py"

    # Re-exec with venv python if we're not already using it
    if Path(sys.executable).resolve() != venv_python.resolve() and venv_python.exists():
        os.execv(
            str(venv_python),
            [str(venv_python), str(server_path)],
        )
    else:
        # Already in venv or no venv — run as proper module
        runpy.run_path(str(server_path), run_name="__main__")


if __name__ == "__main__":
    main()
