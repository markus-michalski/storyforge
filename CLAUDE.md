# StoryForge — AI Book Writing Plugin

## Overview

StoryForge is a Claude Code plugin for writing fiction **and memoir**: from brainstorming through concept, plot, characters, world-building, chapter-by-chapter writing, to export as EPUB/PDF/MOBI. Author profiles ensure authentic voice — not generic AI output.

Books carry a `book_category` field (`fiction` | `memoir`) that gates category-specific craft and skill behavior. See **Book Category** below.

## Configuration

- Config: `~/.storyforge/config.yaml`
- Cache: `~/.storyforge/cache/state.json`
- Authors: `~/.storyforge/authors/{slug}/`
- Venv: `~/.storyforge/venv/`
- Content: `~/projekte/book-projects/` (configurable)
- `{plugin_root}` = directory containing this CLAUDE.md

## MCP Server

Server name: `storyforge-mcp`

Use MCP tools for ALL state operations. Direct file parsing in skills bypasses caching and validation — go through MCP.

## Book Category

Every book carries a `book_category` field in its README frontmatter:

| Value | Meaning | Default |
|-------|---------|---------|
| `fiction` | Invented narrative, fiction-shaped craft | ✓ default for new books and for legacy books missing the field |
| `memoir` | Personal narrative shaped from lived experience | Set explicitly via `create_book_structure(book_category="memoir")` |

Category-specific knowledge lives at `{plugin_root}/book_categories/{category}/`:

- `book_categories/fiction/README.md` — pointer to canonical fiction docs (this file, `reference/craft/`)
- `book_categories/memoir/README.md` — memoir conventions, structure types, craft index
- `book_categories/memoir/craft/` — five memoir-specific craft references (structure types, scene vs. summary, emotional truth, real-people ethics, memoir anti-AI patterns)
- `book_categories/{fiction,memoir}/status-model.md` — per-category status interpretation

Resolve the path from a skill via MCP `get_book_category_dir(category)`.

`book_category` is **orthogonal** to `book_type` (length class: `short-story | novelette | novella | novel | epic`). A "memoir novella" is valid; the two fields don't constrain each other.

Phase 1 (#54–#56, #67) adds the field plus knowledge scaffold. Skill branching by category lands in Phase 2+ (epic #97). Until those phases ship, all skills behave the same regardless of `book_category`.

## Skill Routing

| User Intent | Skill |
|------------|-------|
| "New book" / "Neues Buch" | `/storyforge:new-book` IMMEDIATELY |
| "Buch-Idee" / "Story-Idee" / "Roman-Idee" / "Fiction-Idee" / "Brainstorm a story/book/novel" / "Was könnte ich schreiben?" / "neue Geschichte" | `/storyforge:brainstorm` (only when fiction context is clear; defer if ambiguous) |
| "Meine Buch-Ideen" / "Story-Ideen" / "Was habe ich an Buchideen gespeichert?" | `/storyforge:ideas` |
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
| "problem:" / "recurring issue:" / "report issue" / "regel melden" / "Regel eintragen" | `/storyforge:report-issue` |
| "promote rule" / "rule global machen" / "Regel hochstufen" / "promote to author" / "promote to global" | `/storyforge:promote-rule` |
| "Recherche" / "Research" | `/storyforge:researcher` |
| "Sensitivity" / "Problematisch?" | `/storyforge:sensitivity-reader` |
| "Export" / "EPUB" / "PDF" / "MOBI" | `/storyforge:export-engineer` |
| "Übersetzen" / "Translate" | `/storyforge:translator` |
| "Cover" / "Buchcover" | `/storyforge:cover-artist` |
| "Promo" / "Social Media" / "Marketing" / "bewerben" | `/storyforge:promo-writer` |
| "Klappentext" / "Blurb" / "Back cover" / "Back-cover copy" | `/storyforge:promo-writer` (starts at blurb step) |
| "Neues Genre" / "Genre-Mix" | `/storyforge:genre-creator` |
| "I'm stuck" / "Ich komme nicht weiter" / "blockiert" / "kann nicht schreiben" / "keine Motivation" / "Schreibblockade" / "keine Lust" | `/storyforge:unblock` |
| "Rolling planner" / "Next scene" / "Was kommt als nächstes?" / "Nächste Szene planen" / "Discovery writer" | `/storyforge:rolling-planner` |
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

### Standard Workflow (Outliner)
1. `/storyforge:create-author` — Define writing style (incl. `author_writing_mode`)
2. `/storyforge:study-author` — (Optional) Analyze PDFs for style extraction
3. `/storyforge:new-book` — Create project scaffold + resolve writing mode
4. `/storyforge:book-conceptualizer` — Develop concept in 5 phases
5. `/storyforge:plot-architect` — Structure plot with acts, beats, arcs + tonal document
6. `/storyforge:character-creator` — Build characters with depth
7. `/storyforge:world-builder` — Setting, rules, history

### Discovery Writer Workflow (Pantser)
1. `/storyforge:create-author` — Define writing style (`author_writing_mode: discovery`)
2. `/storyforge:new-book` — Create project scaffold (skips `plot-architect` suggestion)
3. `/storyforge:book-conceptualizer` — Concept only (premise + protagonist + core tension)
4. `/storyforge:character-creator` — Core characters (no arc planning required)
5. `/storyforge:rolling-planner` — Before each writing session: scene recipe (Goal / Conflict / Consequence)
6. (repeat 5 → chapter-writer for each chapter)

### Plantser Workflow (Hybrid)
1. `/storyforge:create-author` — Define writing style (`author_writing_mode: plantser`)
2. `/storyforge:new-book` — Create project scaffold
3. `/storyforge:book-conceptualizer` — Concept in 5 phases
4. `/storyforge:plot-architect` — Minimal Viable Outline only (6 key beats, no full chapter plan)
5. `/storyforge:character-creator` — Core characters
6. `/storyforge:rolling-planner` — Scene-by-scene planning buffer (3-5 scenes ahead)
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

### Memoir Workflows (Phase 2+ — forthcoming)

Phase 1 ships memoir knowledge under `book_categories/memoir/` but does **not** yet branch the skills above. Memoir books currently flow through the same fiction workflows; skills will branch on `book_category` once Phase 2 (#57–#60, #63), Phase 3 (#61, #62, #65, #66) and Phase 4 (#64) land.

Memoir-aware skills already wired:

- `/storyforge:new-book` — scaffolds memoir-shaped tree (`people/` instead of `characters/`, no `world/`, structure-types outline) when `book_category: memoir` is selected (Issue #63)
- `/storyforge:book-dashboard` — surfaces `Category` and `Length` separately, re-labels people table for memoir (Issue #63)
- `/storyforge:book-conceptualizer` (memoir mode) — runs the 5-phase concept with Phase 3 *Scope* (time window / cast / deliberate exclusions) instead of Phase 3 *Conflict*, memoir-blurb conventions in Phase 5 (Issue #60)

The forthcoming memoir-specific routing (not yet wired):

- `/storyforge:memoir-ethics-checker` — consent/defamation/anonymization scan (Issue #65)
- `/storyforge:emotional-truth-prompt` — render-the-felt-sense pass (Issue #66)
- `/storyforge:character-creator` (memoir mode) — real-people handler with consent tracking (Issue #59)
- `/storyforge:plot-architect` (memoir mode) — narrative-arc shaping with structure-type selection (Issue #58)
- `/storyforge:chapter-writer` (memoir mode) — loads memoir craft, scene-vs-summary discipline (Issue #57)

Until those land, when working on a memoir book, manually load `book_categories/memoir/README.md` and the relevant `craft/` files at the start of any creative skill.

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

For `book_category: memoir` projects, the same paths carry **shifted meaning** (characters/ = real people; plot/outline.md = narrative arc shaped from truth, not invented; world/setting.md = real places + eras). See `book_categories/memoir/README.md` for the full mapping. The on-disk layout itself is unchanged in Phase 1 — Phase 2 (#59) may introduce a `people/` alias for memoir; until then `characters/` works for both categories.

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

### Memoir status interpretation

The book status sequence is **identical** for `book_category: memoir`. Several stages carry shifted intent (e.g., `Plot Outlined` = narrative arc identified; `Characters Created` = people profiles drafted with consent decisions). Phase 3 quality gates (consent verification, emotional-truth pass) are documented in `book_categories/memoir/status-model.md` and will be enforced by `memoir-ethics-checker` (#65) once Phase 3 lands.

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

- `{plugin_root}/reference/craft/` — 19 universal/fiction-craft reference documents
- `{plugin_root}/reference/genre/` — genre-specific craft guides
- `{plugin_root}/book_categories/memoir/craft/` — 5 memoir-specific craft documents (structure types, scene vs. summary, emotional truth, real-people ethics, memoir anti-AI patterns)

Each doc in `reference/craft/` carries a `book_categories: [...]` frontmatter (Issue #56) that declares whether it applies to `[fiction]`, `[fiction, memoir]`, or other future categories. Most apply to both; the four pure-invention docs (`character-creation`, `character-arcs`, `plot-craft`, `world-building`) are tagged `[fiction]` because memoir handles those concerns differently (see `book_categories/memoir/craft/real-people-ethics.md`).

Skills MUST load relevant craft references before generating creative content. Until Phase 2+ wires automatic filtering by `book_category`, skills should also manually skip docs whose frontmatter excludes the current category.

- `book-conceptualizer` → loads: theme-development for both modes; fiction adds story-structure + plot-craft; memoir adds (via `book_categories/memoir/craft/`) memoir-structure-types, emotional-truth, scene-vs-summary, real-people-ethics, memoir-anti-ai-patterns. Memoir replaces Phase 3 (Conflict) with Phase 3 (Scope).
- `chapter-writer` → loads: chapter-construction, dialog-craft, show-dont-tell, pacing-guide, anti-ai-patterns, prose-style, simile-discipline + genre craft (memoir mode adds: `book_categories/memoir/craft/scene-vs-summary.md`, `emotional-truth.md`, `memoir-anti-ai-patterns.md`)
- `chapter-reviewer` → loads: dos-and-donts, anti-ai-patterns, chapter-construction, dialog-craft, show-dont-tell, simile-discipline (memoir mode adds: `book_categories/memoir/craft/memoir-anti-ai-patterns.md`)
- `plot-architect` → loads: story-structure, plot-craft, tension-and-suspense (memoir mode loads `book_categories/memoir/craft/memoir-structure-types.md` instead of `plot-craft.md`)
- `character-creator` → loads: character-creation, character-arcs (memoir mode loads `book_categories/memoir/craft/real-people-ethics.md` instead — Phase 2 #59 splits this into a dedicated `real-people-handler` skill)
- `world-builder` → loads: world-building (memoir typically skips this skill — real settings are documented in `world/setting.md` via research, not invention)
- `voice-checker` → loads: anti-ai-patterns, prose-style, dos-and-donts (memoir mode adds: `book_categories/memoir/craft/memoir-anti-ai-patterns.md`)
- `manuscript-checker` → memoir mode adds memoir-specific patterns (Phase 3 #61)
- `promo-writer` → loads: genre README(s) for blurb tone guidance, `reference/promo/platforms.md` for platform characteristics

## Important Rules

1. ALWAYS use MCP tools for state operations — direct file parsing bypasses caching and validation
2. ALWAYS load the author profile before writing ANY prose
3. ALWAYS load relevant craft references before creative skills
4. ALWAYS load genre README(s) before genre-specific work
5. ALWAYS generate prose in the author's voice — check anti-ai-patterns.md before writing. Generic vocabulary, smooth-but-flat rhythm, and AI-tells destroy authenticity.
6. ALL prose must be written in the author's voice (tone, vocabulary, rhythm)
7. Writing language is ENGLISH by default (configurable per book)
8. Code comments in English, user-facing output follows CLAUDE.md global settings
9. ALWAYS load `plot/timeline.md` before writing any chapter — temporal consistency is mandatory
10. ALWAYS load `world/setting.md` (Travel Matrix) before any scene involving travel or location
11. ALWAYS update `plot/timeline.md` after writing a chapter — one row per story-day
12. ALWAYS load `plot/canon-log.md` before writing any chapter — preserve established facts. Contradictions break canon and reader trust.
13. ALWAYS update `plot/canon-log.md` after writing or revising a chapter — track new and changed facts
14. ALWAYS verify user corrections before applying — quote the relevant text, check context, assess impact, and push back when the user is wrong or has misunderstood. The user's English comprehension may miss prose nuances; blind acceptance corrupts drafts.
15. ALWAYS load `plot/tone.md` before writing any chapter (if it exists) — tonal consistency is mandatory
16. ALWAYS update the `## Chapter Timeline` section in the chapter's README.md after writing — intra-day time tracking prevents temporal inconsistencies
17. ALWAYS load the book's `CLAUDE.md` via MCP `get_book_claudemd()` before writing or reviewing a chapter — it contains persisted workflow rules and callbacks that survive session compaction
18. Prefix grammar for persistence: messages starting with `Regel:`, `Workflow:`, or `Callback:` are extracted by the PreCompact hook and written to the book's CLAUDE.md. Unprefixed messages are never persisted automatically.
19. **ALWAYS `Read` the full file when processing review comments** (GH#27). When the user signals that review comments (`{review_handle}:` blocks) are ready, call the `Read` tool on the full file first. The file-change `system-reminder` diff is truncated for long files — end-of-file comments get silently dropped. After reading, count the comments you see and report the count; re-read if the count mismatches expectation.
20. **ALWAYS check `book_category` before creative work on a book** (Path E #54/#67). Read it from `get_book_full(slug).book_category`. For `memoir`, additionally load `book_categories/memoir/README.md` and the relevant `book_categories/memoir/craft/*.md` docs at the start of any creative skill. Phase 1 wires the field but does not yet auto-branch skills — the manual load is the bridge until Phase 2+ ships the automatic routing. For named living people in memoir scenes, surface `consent_status` decisions explicitly (Phase 3 #65 will enforce this automatically).

## Code Style

- Python: English comments, type hints, PEP 8
- Markdown: English for reference docs
- YAML frontmatter: always present in project/chapter/character files
