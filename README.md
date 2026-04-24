# StoryForge

![GitHub Tag](https://img.shields.io/github/v/tag/markus-michalski/storyforge?sort=semver&style=for-the-badge&logo=mdbook)
![License: PolyForm NC 1.0.0](https://img.shields.io/badge/license-PolyForm%20NC%201.0.0-red.svg?style=for-the-badge)

AI-powered book writing plugin for Claude Code. Author profiles, genre mixing, 33 specialized skills, anti-AI voice checker — from brainstorm to published EPUB/PDF/MOBI.

**📖 Full documentation:** [faq.markus-michalski.net/en/plugins/storyforge](https://faq.markus-michalski.net/en/plugins/storyforge)

The documentation covers every skill in detail, all three writing modes (Outliner, Plantser, Discovery), a complete workflow example, configuration, templates, and troubleshooting. Start there.

## Quick Start

```bash
# 1. Install the plugin
claude plugin add storyforge

# 2. First-time setup
/storyforge:setup

# 3. Create your author profile (the anti-AI voice engine)
/storyforge:create-author

# 4. Start a book
/storyforge:new-book

# 5. See all available commands
/storyforge:help
```

## Requirements

- Claude Code CLI
- Python 3.10+
- Pandoc (for EPUB/PDF export)
- Calibre (optional, for MOBI)

## Architecture

```
storyforge/
├── skills/       # 33 specialized skills (SKILL.md files)
├── servers/      # FastMCP server with 28 MCP tools
├── tools/        # Python backend (state, analysis, author, export)
├── genres/       # 14 genre definitions (mixable)
├── reference/    # 36+ craft & genre reference documents
├── templates/    # 16 markdown scaffolds
├── hooks/        # PreCompact & validation hooks
└── tests/        # pytest suite
```

## Contributing

Contributions are welcome under a **Benevolent Dictator For Life (BDFL)** governance model. All PRs require signing the [CLA](CLA.md) (automated via [cla-assistant.io](https://cla-assistant.io/)).

Read [CONTRIBUTING.md](CONTRIBUTING.md) before opening a PR. Bug reports and feature requests: use the [issue templates](https://github.com/markus-michalski/storyforge/issues/new/choose). Security issues: [Private Vulnerability Reporting](https://github.com/markus-michalski/storyforge/security/advisories/new).

## License

[PolyForm Noncommercial License 1.0.0](LICENSE.md) — source-available, personal and non-commercial use only. Not OSI Open Source. Commercial use requires explicit permission; contact the maintainer.
