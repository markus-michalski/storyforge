---
name: setup
description: |
  First-time setup for StoryForge: create virtual environment, install dependencies, copy config template, verify Pandoc.
  Use when: (1) Plugin just installed, (2) MCP server not responding, (3) User says "setup" or "einrichten".
model: claude-sonnet-4-6
user-invocable: true
---

# StoryForge Setup

First-time setup and repair for the StoryForge plugin.

## Workflow

**Multi-line Python — write a file, don't inline it.** Never pass multi-line
content via `<PY> -c "<script>"` — a `-c` argument containing literal newlines
parses differently across bash, PowerShell, and cmd, and reliably breaks
under PowerShell. Any script longer than one line: write it to a file with
your own file-write capability first, then run `<PY> <path-to-that-file>` —
a plain file-path argument, portable across every shell. Single-line
`<PY> -c "..."` commands below are unaffected and can stay exactly as shown.

### Step 0: Detect Platform and Resolve a Working Python Interpreter

Try each of the following in order and use the **first one that actually runs**
(prints a platform string, doesn't error):

```bash
python3 -c "import sys; print(sys.platform)"
python -c "import sys; print(sys.platform)"
py -3 -c "import sys; print(sys.platform)"
```

**Do not stop at the first failure.** On Windows, `python3`/`python` frequently
fail with **exit code 49 and no output** even when Python is genuinely
installed — this is the Microsoft Store app-execution-alias stub, not a
missing-Python error. It's common on Intune/SCCM-managed devices where Python
was pushed via MSI/EXE without adding it to `PATH`. `py` (the Python Launcher
for Windows) is a separate executable that always lives in `C:\Windows\` — on
`PATH` regardless of how Python itself was installed — so try it before
concluding Python is missing.

If all three fail, check known install locations as a last resort (Windows,
PowerShell syntax): `$env:ProgramFiles\Python3*\python.exe`,
`${env:ProgramFiles(x86)}\Python3*\python.exe`,
`$env:LocalAppData\Programs\Python\Python3*\python.exe` — use the first one
that exists. Only if *every* option above fails is Python genuinely not
installed or not locatable — see Error Handling.

Call whichever command succeeded `<PY>` — use it verbatim for every
subsequent system-level Python invocation in this skill (Steps 1 and 2),
until the venv exists. From Step 3 onward the venv's *own* interpreter is
used instead, resolved via the OS branch below (including Step 8's MCP
verification, which must run against the venv interpreter, not `<PY>`).

**Windows quoting note:** `python3`/`python`/`py -3` need no special handling.
But if `<PY>` came from the known-install-path fallback, it's a full path that
may contain spaces (e.g. `C:\Program Files\Python313\python.exe`). On
Windows, invoke it via the call operator with quotes: `& "<PY>" -c "..."`,
not bare `<PY> -c "..."`.

Output `win32` means Windows (venv layout: `venv\Scripts\python.exe`,
`venv\Scripts\pip.exe`); any other output means POSIX (Linux/macOS/WSL, venv
layout: `venv/bin/python3`, `venv/bin/pip`). Use this result for every
POSIX/Windows choice below.

### Step 1: Check Python Version

Verify Python 3.10+ is available via `<PY> --version`.

### Step 2: Create Venv (if missing)

Use `<PY>` — the same interpreter resolved in Step 0, not a hardcoded
`python`/`python3`.

- POSIX: `<PY> -m venv ~/.storyforge/venv`
- Windows: `<PY> -m venv "$env:USERPROFILE\.storyforge\venv"`

### Step 3: Install Dependencies

From `{plugin_root}/requirements.txt`:

- POSIX: `~/.storyforge/venv/bin/pip install -r {plugin_root}/requirements.txt`
- Windows: `& "$env:USERPROFILE\.storyforge\venv\Scripts\pip.exe" install -r {plugin_root}\requirements.txt`

### Step 4: Create Directories

- POSIX: `mkdir -p ~/.storyforge/cache ~/.storyforge/authors`
- Windows: `New-Item -ItemType Directory -Force -Path "$env:USERPROFILE\.storyforge\cache", "$env:USERPROFILE\.storyforge\authors"`

### Step 5: Copy Config

If `~/.storyforge/config.yaml` doesn't exist, copy from
`{plugin_root}/config/config.example.yaml`:

- POSIX: `[ -f ~/.storyforge/config.yaml ] || cp {plugin_root}/config/config.example.yaml ~/.storyforge/config.yaml`
- Windows: `if (-not (Test-Path "$env:USERPROFILE\.storyforge\config.yaml")) { Copy-Item "{plugin_root}\config\config.example.yaml" "$env:USERPROFILE\.storyforge\config.yaml" }`

### Step 6: Check Pandoc

Run `pandoc --version` (identical command on both platforms). If not found,
inform user:
> Pandoc is required for EPUB/PDF export. Install via: `sudo apt install pandoc`
> (Linux), `winget install --id JohnMacFarlane.Pandoc` (Windows), or download
> from https://pandoc.org

### Step 7: Check Calibre (optional)

Run `ebook-convert --version` (identical command on both platforms). If not
found, inform user it's needed for MOBI format only.

### Step 8: Verify MCP

Test that imports work using the venv's own interpreter:

- POSIX: `~/.storyforge/venv/bin/python3 -c "from mcp.server.fastmcp import FastMCP; print('MCP OK')"`
- Windows: `& "$env:USERPROFILE\.storyforge\venv\Scripts\python.exe" -c "from mcp.server.fastmcp import FastMCP; print('MCP OK')"`

### Step 9: Create Content Root

Create the book projects directory if it doesn't exist:

- POSIX: `mkdir -p ~/projekte/book-projects/projects`
- Windows: `New-Item -ItemType Directory -Force -Path "$env:USERPROFILE\projekte\book-projects\projects"`

### Step 10: Report Status

Show what was set up, what's missing, suggest next step:
`/storyforge:create-author` or `/storyforge:help`

## Error Handling

- `python3` not found (POSIX), and no other interpreter in Step 0's chain
  works either → Python is genuinely not installed. Tell user to install
  Python 3.10+.
- On Windows, `python`/`python3` exiting with code 49 and no output is
  **not** "Python not found" — it's the Microsoft Store app-execution-alias
  stub. Do not tell the user to install Python; instead fall through Step 0's
  chain (`py -3`, then known install paths).
- Only if **every** entry in Step 0's fallback chain fails is Python actually
  missing on Windows → tell the user to install Python 3.10+ from python.org
  and check "Add python.exe to PATH" during install.
- `pip install` fails → Show the exact error and suggest running manually.
