# StoryForge

AI-powered book writing plugin for Claude Code. From brainstorming to published EPUB.

## What It Does

StoryForge guides you through the entire fiction writing process:

1. **Create an Author Profile** — Define your writing voice, style, and preferences
2. **Brainstorm & Concept** — Develop story ideas into workable concepts
3. **Plot Architecture** — Structure your story with acts, beats, and turning points
4. **Character Creation** — Build deep characters with arcs, flaws, and voice
5. **World-Building** — Create settings, magic systems, societies
6. **Chapter Writing** — Write chapters in your author's authentic voice
7. **Review & Polish** — 20-point quality checklist + AI-tell detection
8. **Export** — Generate EPUB, PDF, or MOBI via Pandoc
9. **Translation** — Translate chapter by chapter, preserving voice

## Key Features

- **Author Profiles** — Define writing personas with style, tone, vocabulary. Import PDFs to extract style patterns. The anti-AI-detection engine.
- **Genre System** — 14 genres, mixable (e.g., LGBTQ+ Supernatural). Create custom genre combinations.
- **Craft Knowledge Base** — 27 reference documents (73,000+ words) on writing craft, from story structure to dialog to anti-AI patterns.
- **Voice Checker** — Scores text for AI-tells across 7 dimensions. Zero tolerance for generic output.
- **Series Support** — Plan multi-book series with shared canon, characters, and timelines.

## Quick Start

```bash
# 1. Install the plugin
claude plugin add storyforge

# 2. First-time setup
/storyforge:setup

# 3. Create your writing persona
/storyforge:create-author

# 4. Start a book
/storyforge:new-book

# 5. See all available commands
/storyforge:help
```

## Requirements

- Claude Code CLI
- Python 3.10+
- Pandoc (for export)
- Calibre (optional, for MOBI format)

## Architecture

```
storyforge/
├── skills/          # 25 specialized skills (SKILL.md files)
├── servers/         # FastMCP server with 28 tools
├── tools/           # Python backend (config, state, analysis, export)
├── genres/          # 14 genre definitions
├── reference/       # 30+ craft & genre reference documents
├── templates/       # Markdown templates for all project components
└── config/          # Configuration template
```

## Skills Overview

| Category | Skills |
|----------|--------|
| **Core** | new-book, session-start, resume, next-step, book-dashboard, brainstorm |
| **Author** | create-author, study-author, voice-checker |
| **Creative** | book-conceptualizer, plot-architect, character-creator, world-builder |
| **Writing** | chapter-writer, chapter-reviewer |
| **Research** | researcher, sensitivity-reader |
| **Production** | export-engineer, promo-writer, translator, cover-artist |
| **Utility** | genre-creator, series-planner, help, setup, configure |

## License

MIT
