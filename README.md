# StoryForge

[![GitHub release](https://img.shields.io/github/v/release/markus-michalski/storyforge)](https://github.com/markus-michalski/storyforge/releases/latest)

AI-powered book writing plugin for Claude Code. From brainstorming to published EPUB/PDF/MOBI.

## What It Does

StoryForge guides you through the entire fiction writing process in your authentic author voice — not generic AI output:

1. **Create an Author Profile** — Define voice, style, vocabulary, and writing mode
2. **Brainstorm & Concept** — Develop story ideas into workable premises with theme and conflict architecture
3. **Plot Architecture** — Structure your story with acts, beats, arcs, and tonal guard rails. Supports 8 methods including 3-Act, Hero's Journey, Save the Cat, and Snowflake Method
4. **Character Creation** — Build 3D characters via 14 steps: GMC, psychology, fatal flaw, voice, arc
5. **World-Building** — Settings, magic systems, societies, Travel Matrix for location consistency
6. **Chapter Writing** — Write in your author's voice with mandatory timeline, canon, and tonal checks
7. **Review & Polish** — 28-point quality checklist, 13-point first-chapter gate, AI-tell detection
8. **Manuscript Gate** — Full-manuscript scan for cross-chapter repetition, clichés, filter words, adverb density
9. **Beta Feedback** — Triage reader feedback against canon/timeline/tone, produce revision plan
10. **Export** — Generate EPUB, PDF, or MOBI via Pandoc/Calibre
11. **Translation & Promo** — Translate preserving voice; social media campaigns for 6 platforms

## Key Features

- **Author Profiles** — Voice, tone, sentence style, vocabulary, banned/preferred words. Import PDFs/EPUB/DOCX to extract style patterns. The core anti-AI-detection engine.
- **3 Writing Modes** — Outliner (full upfront plan), Plantser (minimal outline + rolling buffer), Discovery Writer (scene-by-scene, no plan required)
- **Genre System** — 14 genres, freely mixable (e.g., LGBTQ+ Supernatural, Dark Fantasy). Create custom genre combinations.
- **Craft Knowledge Base** — 36+ reference documents (73,000+ words): story structure, pacing, dialog, POV, anti-AI patterns, simile discipline, plus 10 genre-specific craft guides
- **Voice Checker** — Scores text for AI-tells across 7 dimensions: vocabulary, sentence variance, paragraph structure, dialog authenticity, emotional expression, specificity, author-profile match
- **Simile Discipline** — Enforced in chapter-writer and chapter-reviewer; no repeated figurative language across scenes
- **Timeline & Canon** — Mandatory timeline.md (story calendar) and canon-log.md (story bible) loaded before every chapter. Auto-validated for consistency.
- **Per-Book Rules** — Rules, workflows, and callbacks persisted to the book's own CLAUDE.md via PreCompact hook — survive session compaction
- **Manuscript Checker** — Cross-chapter repetition scanner (similes, character tells, blocking tics, structural patterns, signature phrases), cliché detector, dialogue punctuation audit, filter-word and adverb density analysis
- **Beta Feedback Triage** — Parse, categorize, cross-reference against canon/timeline/tone/arcs; deliver verdicts (valid / disagree / cosmetic); produce revision plan
- **Series Support** — Multi-book canon, character evolution, overarching arc planning
- **Writer's Block Recovery** — Diagnose block type (fear/perfectionism/procrastination/distraction) and deliver targeted interventions

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
- Pandoc (for EPUB/PDF export)
- Calibre (optional, for MOBI format)

## Writing Mode Workflows

### Outliner (Full Plan First)
```
create-author → new-book → book-conceptualizer → plot-architect →
character-creator → world-builder → chapter-writer → chapter-reviewer →
[manuscript-checker at revision gate] → export-engineer
```

### Plantser (Minimal Outline + Rolling Buffer)
```
create-author → new-book → book-conceptualizer → plot-architect (6 beats only) →
character-creator → rolling-planner (3-5 scene buffer) → chapter-writer →
chapter-reviewer → manuscript-checker → export-engineer
```

### Discovery Writer (No Plan Required)
```
create-author → new-book → book-conceptualizer (premise + protagonist + core tension) →
character-creator (core cast, no arc planning) →
[rolling-planner → chapter-writer] repeat per chapter →
continuity-checker → manuscript-checker → export-engineer
```

## Architecture

```
storyforge/
├── skills/          # 33 specialized skills (SKILL.md files)
├── servers/         # FastMCP server with 28 MCP tools
├── tools/           # Python backend (state, analysis, author, export)
├── genres/          # 14 genre definitions (11 base + 2 mix + 1 cross-cutting)
├── reference/       # 36+ craft & genre reference documents
├── templates/       # 16 markdown scaffolds for all project components
├── hooks/           # 3 PreCompact & validation hooks
├── tests/           # 17 pytest test files
└── config/          # Configuration template
```

## Skills Overview

| Category | Skills |
|----------|--------|
| **Core** | new-book, session-start, resume, next-step, book-dashboard, brainstorm, ideas |
| **Author** | create-author, study-author, voice-checker |
| **Creative** | book-conceptualizer, plot-architect, character-creator, world-builder, rolling-planner |
| **Writing** | chapter-writer, chapter-reviewer, continuity-checker, manuscript-checker, beta-feedback |
| **Research** | researcher, sensitivity-reader |
| **Production** | export-engineer, promo-writer, translator, cover-artist |
| **Series** | series-planner |
| **Utility** | genre-creator, unblock, register-callback, help, setup, configure |

## Skill Highlights

### Writing
- **`/storyforge:chapter-writer`** — Loads author profile, book data, outline, previous chapter, 8 craft references, character/world files, timeline, canon log, tonal document, and per-book CLAUDE.md before writing a single word. Scene-by-scene mode recommended with inline review handles. Includes mandatory simile discipline scan per scene.
- **`/storyforge:plot-architect`** — Supports 8 structure methods including Snowflake Method: 10-step iterative workflow building premise → sentence summary → page synopsis → character sheets → full scene list.
- **`/storyforge:rolling-planner`** — Scene-by-scene planning for discovery writers and plantsers. Goal / Conflict / Consequence recipe for each scene.
- **`/storyforge:continuity-checker`** — Validates all chapters against timeline and Travel Matrix. Reconstructs both if missing. Flags all temporal and spatial conflicts.
- **`/storyforge:manuscript-checker`** — Full-manuscript gate before revision. Detects: book-rule violations, cross-chapter repetition (similes, blocking tics, structural patterns), clichés, dialogue punctuation anomalies, POV filter-word density, adverb density. Interactive fix mode.
- **`/storyforge:beta-feedback`** — Triage ARC/beta-reader feedback: categorize (plot / character / pacing / prose / continuity / genre-expectation), cross-reference against canon and arc plans, deliver verdicts, produce revision plan.
- **`/storyforge:unblock`** — Diagnose writer's block (fear / perfectionism / procrastination / distraction) and deliver targeted exercises to get writing again.

### Production
- **`/storyforge:promo-writer`** — Full campaign: back-cover blurb → campaign strategy → platform-specific content → quote cards → hashtag strategy + calendar. Targets: Facebook, Instagram, Twitter/X, TikTok, Bluesky, Newsletter.

### Persistence
- **`/storyforge:register-callback`** — Messages prefixed with `Regel:`, `Workflow:`, or `Callback:` are automatically extracted by the PreCompact hook and written to the book's own CLAUDE.md — rules survive compaction and are reloaded before every chapter.

## Configuration

Config lives at `~/.storyforge/config.yaml` (outside the plugin directory, survives updates):

| Setting | Default | Description |
|---------|---------|-------------|
| `content_root` | `~/projekte/book-projects` | Where book projects are stored |
| `authors_root` | `~/.storyforge/authors` | Author profile directory |
| `default_language` | `en` | Writing language |
| `default_book_type` | `novel` | short-story / novelette / novella / novel / epic |
| `export_format` | `epub` | epub / pdf / mobi |
| `pdf_engine` | `xelatex` | xelatex / pdflatex / wkhtmltopdf |
| `cover_platform` | `midjourney` | midjourney / dall-e |

Author profiles support `author_writing_mode: outliner | plantser | discovery`.

## Project Structure (Per Book)

```
{book-slug}/
├── README.md              # Book metadata (YAML frontmatter)
├── synopsis.md            # Back-cover blurb + long synopsis
├── plot/
│   ├── outline.md         # Act/beat structure
│   ├── timeline.md        # Story calendar (day-by-day events)
│   ├── tone.md            # Tonal guard rails + litmus test
│   ├── canon-log.md       # Story bible (established facts)
│   └── arcs.md            # Character arc overview
├── characters/            # INDEX.md + individual character files
├── world/                 # setting.md (incl. Travel Matrix), rules.md, history.md
├── chapters/
│   └── {NN-slug}/
│       ├── README.md      # Chapter metadata + outline + Chapter Timeline
│       └── draft.md       # Prose
├── CLAUDE.md              # Per-book rules/workflows/callbacks (auto-synced)
├── cover/                 # brief.md, prompts.md
├── export/                # front-matter.md, back-matter.md, output/
└── translations/          # {lang}/ with glossary.md + chapters/
```

## Status Model

**Book status** (auto-derived from chapter aggregates, never regresses):
```
Idea → Concept → Research → Plot Outlined → Characters Created →
World Built → Drafting → Revision → Editing → Proofread → Export Ready → Published
```

**Chapter status**: `Outline → Draft → Revision → Polished → Final`

**Idea status**: `raw → explored → developed → ready → promoted` (or `shelved`)

## License

MIT
