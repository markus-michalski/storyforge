---
name: setup
description: |
  First-time setup for StoryForge: create virtual environment, install dependencies, copy config template, verify Pandoc.
  Use when: (1) Plugin just installed, (2) MCP server not responding, (3) User says "setup" or "einrichten".
model: claude-sonnet-4-6
user-invocable: true
---

# StoryForge Setup

## Workflow

1. **Check Python version** — Verify Python 3.10+ is available
2. **Create venv** at `~/.storyforge/venv/`
   ```bash
   python3 -m venv ~/.storyforge/venv
   ```
3. **Install dependencies** from `{plugin_root}/requirements.txt`
   ```bash
   ~/.storyforge/venv/bin/pip install -r {plugin_root}/requirements.txt
   ```
4. **Create directories**
   - `~/.storyforge/cache/`
   - `~/.storyforge/authors/`
5. **Copy config** — If `~/.storyforge/config.yaml` doesn't exist, copy from `{plugin_root}/config/config.example.yaml`
6. **Check Pandoc** — Run `pandoc --version`. If not found, inform user:
   > Pandoc is required for EPUB/PDF export. Install via: `sudo apt install pandoc` or download from https://pandoc.org
7. **Check Calibre** (optional) — Run `ebook-convert --version`. If not found, inform user it's needed for MOBI format only.
8. **Verify MCP** — Test that imports work:
   ```bash
   ~/.storyforge/venv/bin/python3 -c "from mcp.server.fastmcp import FastMCP; print('MCP OK')"
   ```
9. **Create content root** — Create `~/projekte/book-projects/projects/` if it doesn't exist
10. **Report status** — Show what was set up, what's missing, suggest next step: `/storyforge:create-author` or `/storyforge:help`
