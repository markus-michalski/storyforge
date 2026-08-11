"""Issue #534 — routers/__init__.py must register every @mcp.tool module, including canon.

server.py additionally imports routers.canon by hand (line ~127), which masks a missing
entry in routers/__init__.py's own side-effect import list during normal test runs, since
canon then ends up registered on the shared mcp instance anyway. This subprocess probe
imports only the routers package — the way its own docstring claims covers "every
@mcp.tool() decorated function" — to prove canon registers without server.py's help.
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

_PROJECT_ROOT = Path(__file__).resolve().parents[2]
_SERVER_DIR = _PROJECT_ROOT / "servers" / "storyforge-server"

_PROBE = f"""
import sys
sys.path.insert(0, {str(_PROJECT_ROOT)!r})
sys.path.insert(0, {str(_SERVER_DIR)!r})
import routers
from routers._app import mcp
names = {{t.name for t in mcp._tool_manager.list_tools()}}
print("add_canon_fact" in names)
"""


def test_importing_routers_package_alone_registers_canon_tool():
    result = subprocess.run(
        [sys.executable, "-c", _PROBE],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, result.stderr
    assert result.stdout.strip() == "True", (
        f"add_canon_fact not registered by importing routers alone "
        f"(stdout={result.stdout!r}, stderr={result.stderr!r})"
    )
