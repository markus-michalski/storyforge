# StoryForge — AI Book Writing Plugin

## Overview

StoryForge is a Claude Code plugin for writing fiction: from brainstorming through concept, plot, characters, world-building, chapter-by-chapter writing, to export as EPUB/PDF/MOBI. Author profiles ensure authentic voice — not generic AI output.

## Configuration

- Config: `~/.storyforge/config.yaml`
- Cache: `~/.storyforge/cache/state.json`
- Authors: `~/.storyforge/authors/{slug}/`
- Venv: `~/.storyforge/venv/`
- Content: `~/projekte/book-projects/` (configurable)
- `{plugin_root}` = directory containing this CLAUDE.md

## MCP Server

Server name: `storyforge-mcp`

Use MCP tools for ALL state operations. Never parse project files directly in skills.

## Skill Routing

| User Intent | Skill |
|------------|-------|
| "New book" / "Neues Buch" | `/storyforge:new-book` IMMEDIATELY |
| "Brainstorm" / "Idee" / "Was könnte ich schreiben?" | `/storyforge:brainstorm` |
| "Meine Ideen" / "Ideas" / "Was habe ich gespeichert?" | `/storyforge:ideas` |
| Book title/name mentioned | `/storyforge:resume [name]` |
| "What's next?" / "Was steht an?" | `/storyforge:next-step` |
| "Dashboard" / "Status" / "Fortschritt" | `/storyforge:book-dashboard` |
| "Konzept" / "Develop concept" | `/storyforge:book-conceptualizer` |
| "Serie planen" / "Series" | `/storyforge:series-planner` |
| "Autor anlegen" / "Create author" | `/storyforge:create-author` |
| "Buch studieren" / "Study this PDF" | `/storyforge:study-author` |
| "Plot" / "Handlung" / "Struktur" | `/storyforge:plot-architect` |
| "Charakter" / "Character" | `/storyforge:character-creator` |
| "Welt" / "World" / "Setting" / "Magic System" | `/storyforge:world-builder` |
| "Kapitel schreiben" / "Write chapter" | `/storyforge:chapter-writer` |
| "Kapitel reviewen" / "Review chapter" | `/storyforge:chapter-reviewer` |
| "Continuity prüfen" / "Check continuity" / "Zeitlinie prüfen" / "Timeline prüfen" | `/storyforge:continuity-checker` |
| "Voice check" / "Klingt das nach AI?" | `/storyforge:voice-checker` |
| "Manuscript check" / "Prose check" / "Repetition check" / "Wiederholungen prüfen" / "Prose tics" / "Buch prüfen" | `/storyforge:manuscript-checker` |
| "Beta feedback" / "ARC feedback" / "Reader feedback" / "Beta-Feedback verarbeiten" | `/storyforge:beta-feedback` |
| "Recherche" / "Research" | `/storyforge:researcher` |
| "Sensitivity" / "Problematisch?" | `/storyforge:sensitivity-reader` |
| "Export" / "EPUB" / "PDF" / "MOBI" | `/storyforge:export-engineer` |
| "Übersetzen" / "Translate" | `/storyforge:translator` |
| "Cover" / "Buchcover" | `/storyforge:cover-artist` |
| "Promo" / "Social Media" / "Marketing" / "bewerben" | `/storyforge:promo-writer` |
| "Klappentext" / "Blurb" / "Back cover" / "Back-cover copy" | `/storyforge:promo-writer` (starts at blurb step) |
| "Neues Genre" / "Genre-Mix" | `/storyforge:genre-creator` |
| `Regel:` / `Workflow:` / `Callback:` prefix, "merke dir" | `/storyforge:register-callback` |
| "Hilfe" / "Help" | `/storyforge:help` |
| "Setup" / "Einrichten" | `/storyforge:setup` |
| "Config" / "Konfiguration" | `/storyforge:configure` |

## Workflow Pipeline

```
1. Create Author Profile → Study PDFs (optional)
2. Brainstorm → New Book → Concept
3. Plot Architecture → Characters → World
4. Chapter Writing → Chapter Review → Voice Check
5. Revision → Export → Translation (optional)
```

### Standard Workflow
1. `/storyforge:create-author` — Define writing style
2. `/storyforge:study-author` — (Optional) Analyze PDFs for style extraction
3. `/storyforge:new-book` — Create project scaffold
4. `/storyforge:book-conceptualizer` — Develop concept in 5 phases
5. `/storyforge:plot-architect` — Structure plot with acts, beats, arcs + tonal document
6. `/storyforge:character-creator` — Build characters with depth
7. `/storyforge:world-builder` — Setting, rules, history
8. `/storyforge:chapter-writer` — Write chapters in author's voice (loads timeline + travel matrix + tonal document + chapter timeline)
9. `/storyforge:continuity-checker` — (Optional, after several chapters) Validate timeline and location consistency
9. `/storyforge:chapter-reviewer` — Review each chapter
9b. `/storyforge:manuscript-checker` — (At drafting → revision transition) Scan the whole manuscript for book-rule violations, clichés, dialogue punctuation, filter words, adverb density, and cross-chapter repetition
9c. `/storyforge:beta-feedback` — (After eBook/ARC stage) Process curated beta-reader feedback, triage, revision plan
10. `/storyforge:voice-checker` — Verify authenticity
11. `/storyforge:cover-artist` — Generate cover prompts
12. `/storyforge:export-engineer` — EPUB/PDF/MOBI via Pandoc
13. `/storyforge:promo-writer` — Social media campaign (FB, Instagram, TikTok, X, Bluesky, Newsletter)
14. `/storyforge:translator` — Translate to other languages

## Project Structure

Books live at `{content_root}/projects/{slug}/`:
```
{book-slug}/
├── README.md           # Book metadata (YAML frontmatter)
├── synopsis.md         # Back-cover blurb + long synopsis
├── plot/               # outline.md, acts.md, timeline.md (story calendar), tone.md (tonal guard rails), canon-log.md (story bible), arcs.md
├── characters/         # INDEX.md + individual character files
├── world/              # setting.md (incl. Travel Matrix), rules.md, history.md, glossary.md
├── research/           # sources.md + notes/
├── chapters/
│   └── {NN-slug}/
│       ├── README.md   # Chapter metadata + outline
│       └── draft.md    # The actual prose
├── cover/              # brief.md, prompts.md, art/
├── export/             # front-matter.md, back-matter.md, output/
└── translations/       # {lang}/ with glossary.md + chapters/
```

## Status Progressions

### Book
```
Idea → Concept → Research → Plot Outlined → Characters Created →
World Built → Drafting → Revision → Editing → Proofread → Export Ready → Published
```

**Auto-derivation from chapter state** (Issue #21): the indexer derives an effective book status from chapter aggregates. It only ever escalates forward — never moves backward. Rules:

| Book tier | Trigger |
|-----------|---------|
| `Drafting` | any chapter past `Outline` |
| `Revision` | every chapter at Revision rank or higher (incl. alias `review`) |
| `Proofread` | every chapter `Final` |

`Editing`, `Export Ready`, and `Published` remain **explicit** — they require qualitative judgment beyond chapter-state aggregation.

**Auto-sync to disk** (Issue #25): `rebuild_state()` writes the derived status back to README frontmatter when it's a **forward move** from the on-disk value. Floor rule — a user-set higher tier (`Export Ready`, `Published`) is never silently downgraded by chapter aggregates. Sync events are returned in the `synced` field of the rebuild response. Books without any frontmatter block get a minimal one created. `book.status_disk` remains as a debug signal (after auto-sync it always matches `book.status`).

Chapter-status aliases for ranking (display string is preserved):

| Alias | Canonical rank |
|-------|----------------|
| `review`, `reviewed` | Revision |
| `drafting` | Draft |
| `polishing` | Polished |
| `done` | Final |

### Chapter
```
Outline → Draft → Revision → Polished → Final
```

### Character
```
Concept → Profile → Backstory → Arc Defined → Final
```

## Author Profiles

Authors live at `~/.storyforge/authors/{slug}/`:
- `profile.md` — Style, voice, techniques (YAML frontmatter)
- `vocabulary.md` — Preferred/banned words, signature phrases
- `studied-works/` — Analysis files from PDF imports
- `examples/` — Sample texts

## Genre System

Genres at `{plugin_root}/genres/{name}/README.md`. Three types:
1. **Base genres** — Standalone: horror, fantasy, sci-fi, thriller, mystery, romance, drama, literary-fiction, historical, contemporary, supernatural
2. **Cross-cutting** — Always combined: lgbtq
3. **Mix genres** — Pre-defined combos: dark-fantasy, paranormal-romance

Books can combine 1-3 genres.

## Craft Knowledge Base

`{plugin_root}/reference/craft/` contains 18 reference documents on writing craft.
`{plugin_root}/reference/genre/` contains genre-specific craft guides.

Skills MUST load relevant craft references before generating creative content:
- `chapter-writer` → loads: chapter-construction, dialog-craft, show-dont-tell, pacing-guide, anti-ai-patterns, prose-style, simile-discipline + genre craft
- `chapter-reviewer` → loads: dos-and-donts, anti-ai-patterns, chapter-construction, dialog-craft, show-dont-tell, simile-discipline
- `plot-architect` → loads: story-structure, plot-craft, tension-and-suspense
- `character-creator` → loads: character-creation, character-arcs
- `world-builder` → loads: world-building
- `voice-checker` → loads: anti-ai-patterns, prose-style, dos-and-donts
- `promo-writer` → loads: genre README(s) for blurb tone guidance

## Important Rules

1. ALWAYS use MCP tools for state operations — never parse files directly
2. ALWAYS load the author profile before writing ANY prose
3. ALWAYS load relevant craft references before creative skills
4. ALWAYS load genre README(s) before genre-specific work
5. NEVER generate prose that sounds like AI — check anti-ai-patterns.md
6. ALL prose must be written in the author's voice (tone, vocabulary, rhythm)
7. Writing language is ENGLISH by default (configurable per book)
8. Code comments in English, user-facing output follows CLAUDE.md global settings
9. ALWAYS load `plot/timeline.md` before writing any chapter — temporal consistency is mandatory
10. ALWAYS load `world/setting.md` (Travel Matrix) before any scene involving travel or location
11. ALWAYS update `plot/timeline.md` after writing a chapter — one row per story-day
12. ALWAYS load `plot/canon-log.md` before writing any chapter — never contradict established facts
13. ALWAYS update `plot/canon-log.md` after writing or revising a chapter — track new and changed facts
14. NEVER blindly accept user corrections — verify the claim, check context, assess impact, and push back if the user is wrong or misunderstood. The user's English comprehension may miss nuances in prose. Quote the relevant text and explain.
15. ALWAYS load `plot/tone.md` before writing any chapter (if it exists) — tonal consistency is mandatory
16. ALWAYS update the `## Chapter Timeline` section in the chapter's README.md after writing — intra-day time tracking prevents temporal inconsistencies
17. ALWAYS load the book's `CLAUDE.md` via MCP `get_book_claudemd()` before writing or reviewing a chapter — it contains persisted workflow rules and callbacks that survive session compaction
18. Prefix grammar for persistence: messages starting with `Regel:`, `Workflow:`, or `Callback:` are extracted by the PreCompact hook and written to the book's CLAUDE.md. Unprefixed messages are never persisted automatically.
19. **NEVER trust the file-change `system-reminder` diff in iterative review workflows** (GH#27). When the user signals that review comments (`Markus:` blocks or equivalent) are ready, always call the `Read` tool on the full file first. Claude Code truncates long-file diffs in the system-reminder, which has caused end-of-file comments to be silently dropped. After reading, count the comments you see and report the count — if it mismatches expectation, re-read before processing.

## Code Style

- Python: English comments, type hints, PEP 8
- Markdown: English for reference docs
- YAML frontmatter: always present in project/chapter/character files
