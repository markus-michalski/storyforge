---
name: backfill-style-principles
description: |
  Backfill style_principles Writing Discoveries from existing studied-works
  analysis files — for authors studied before Phase 1.5 (#260) shipped.
  Reads Distinctive Patterns, Signature Techniques, Positive Style Markers,
  and Words & Phrases to Adopt sections, then promotes concrete positive
  patterns to style_principles via write_author_discovery (idempotent).
  Use when: (1) User says "backfill style principles", "style principles
  nachfüllen", "/storyforge:backfill-style-principles", (2) Author has
  studied works but empty or thin style_principles Writing Discoveries,
  (3) Positive patterns documented in analysis files are not reaching
  chapter-writer, (4) Author check finds style_principles section empty
  after multiple studied works.
model: claude-opus-4-7
user-invocable: true
argument-hint: "[author-slug]"
---

# Backfill Style Principles

One-time extraction pass that reads existing `studied-works/analysis-*.md`
files and promotes positive patterns to `style_principles` Writing
Discoveries — **without re-reading the original books**.

The analysis files are the distilled artifact. Re-reading source PDFs is
unnecessary — the extraction work was already done at study time. This pass
promotes what was documented but never wired into the living profile.

## What This Solves

Authors studied before PR #260 have rich analysis archives but empty
`style_principles` Writing Discoveries. Phase 1.5 (positive extraction) did
not exist yet — patterns were documented in `## Distinctive Patterns` and
`## Signature Techniques` but never promoted to the profile that
chapter-writer acts on. The result: banter, sarcasm, found-family dynamics,
and other genre-specific craft patterns silently omitted across dozens of
chapters.

## Step 1: Resolve Author

If the user passed an author slug as the first argument, use it directly.
Otherwise:

1. Check active session via MCP `get_session()` — if there's a session
   author context, propose it.
2. If no session author or user wants a different one, use AskUserQuestion
   with the output of `list_authors()`.

## Step 2: Load Author Profile

MCP `get_author(slug)`. Read:
- `primary_genres` — to build the extraction checklist
- `tone` — tone-derived markers (e.g. `sarcastic`, `dark-humor`)
- Current `writing_discoveries.style_principles` — baseline of what's
  already present (origin tags in existing entries are advisory context
  for which files may already have been partially processed; they are not
  a reliable completeness signal — the MCP dedup handles that at write time)

## Step 3: Build Phase 1.5 Checklist

Replicate the Phase 1.5 checklist from `study-author` — this is the
extraction target that drives the pass.

1. For each genre in `primary_genres`: MCP `get_genre(name)`.
   Read the `## study-author: Positive Markers` section.
2. Combine:
   - Genre-derived positive markers from each genre's Positive Markers section
   - Tone-derived markers from the author profile (e.g. `tone: sarcastic` →
     explicitly look for sarcasm deployment patterns; `tone: dark-humor` →
     look for gallows-humor techniques)

Present the checklist to the user. Show what will be tracked positively across
all analysis files, and allow additions or removals before proceeding.

## Step 4: Build Analysis File List

List `~/.storyforge/authors/{slug}/studied-works/analysis-*.md`.

For each file, derive the book_slug from the filename:
- `analysis-grave-intentions.md` → `grave-intentions`
- `analysis-chosen-one-universe.md` → `chosen-one-universe`

If no analysis files exist:
> "No studied-works analysis files found for {slug}. Nothing to backfill."

Exit.

Show the user the list. If any existing `style_principles` discoveries carry
origin tags matching a file's book_slug, note it as advisory context only
(origin-tag matching is not a completeness guarantee — MCP dedup at write time
is the actual safety net). Confirm before proceeding.

## Step 5: Per-File Extraction Loop

For each analysis file in the list, in order:

### 5.1 Read the file

Read directly from
`~/.storyforge/authors/{slug}/studied-works/analysis-{title}.md`.

If the file is missing or empty → skip:
`[{title}] Could not read analysis file, skipping.`

### 5.2 Identify available sections

Check which sections are present. All four can coexist in the same file —
treat them as co-present sources, not a hierarchy:
- `## Positive Style Markers` — present when the file was studied with
  Phase 1.5 active; most structured source when present
- `## Distinctive Patterns` — qualitative observations beyond a checklist
- `## Signature Techniques` — what makes this source text unique
- `## Words & Phrases to Adopt` — supplementary; include only vocabulary
  patterns specific and actionable enough to be a style principle

If none of the four sections are present (e.g. corrupt or non-fiction-mode
file), record the file as skipped-empty and move on:
`[{title}] No extractable sections found, skipping.`

**Memoir scope:** This skill targets fiction-mode analysis files. Memoir
voice-excavation files have a different section structure (Natural Voice
Fingerprints, Emotional Register, etc.) and are out of scope — skip them.

**Deduplication before writing:** Before calling `write_author_discovery`,
consolidate patterns that appear across multiple sections into a single
entry. The MCP tool deduplicates by content, but pre-write consolidation
produces cleaner per-file counts and avoids noise in the report.

### 5.3 Extract positive patterns

Walk the available sections and identify patterns that meet ALL of:

1. **Positive** — describes a technique to adopt or emulate, not an
   anti-pattern or something to avoid
2. **Concrete** — measurable or observable: has a frequency, trigger, ratio,
   named technique, or specific example from the text
3. **Actionable** — chapter-writer can apply it without access to the source
   book; it describes HOW to do something, not just THAT something exists
4. **Author-transferable** — describes a craft move that can be applied to
   the resolved author's writing, not a plot-specific observation about the
   source book

Work through the Phase 1.5 checklist item by item:
- For each checklist item: does this analysis file document it? If yes,
  extract the concrete pattern and its evidence. If no: note "not found in
  this file" — absence is valid and must be documented.
- After the checklist: scan `## Distinctive Patterns` and
  `## Signature Techniques` for ADDITIONAL positive markers beyond the
  checklist — cross-genre techniques specific enough to be actionable.

Each extracted pattern must be formatted as:
```
**[Marker name]** — [concrete observation with frequency or ratio if
measurable, technique name if named, trigger or context if pattern has one].
```

Do NOT extract:
- Anti-patterns (those belong in `donts` via `write_author_banned_phrase`)
- Vague observations: "the pacing is good", "dialog feels natural"
- Metrics without technique: "short sentences" without what that achieves
- Verbatim source text (plagiarism risk — patterns only, not prose)
- Plot-specific facts that don't generalize to the resolved author's writing

### 5.3b Genre classification and example extraction (Issue #266 / #268)

For each extracted pattern, answer two questions before writing:

**1. Universal or genre-specific?**

A pattern is **genre-specific** if it is clearly tied to the tone or
register of this source book's genre and would be wrong or jarring in a
different genre. Examples:
- Banter frequency (light-fantasy/comedy) → genre-specific
- Humor-as-structural-accelerant (comedy) → genre-specific
- POV-integrity (no author-knowledge leak) → universal
- Flavor-word tic discipline → universal

For genre-specific patterns: determine the source book's genres. Read the
first lines of the analysis file for a `source_genres:` field in frontmatter
(set by `study-author` Phase 1 since Phase 5 / #283). If the field is absent
(older analysis files), fall back to a `genres:` field, or derive from context
(title, tone descriptors). If still unclear, ask the user:
> "Is '{book_slug}' primarily light-fantasy / comedy / other? I'll tag genre-
> specific patterns so chapter-writer skips them in different-genre books."

Collect the value as a comma-separated slug list (e.g.
`light-fantasy, comedy-fantasy`). Universal patterns get an empty `genres`.

**2. Is there a prose example worth preserving?**

Scan the analysis file for a short illustrative example (1–4 lines of
prose or dialogue) that demonstrates the pattern in the source author's
voice. These are typically in `## Positive Style Markers` subsections or
`## Signature Techniques` evidence blocks.

If a good example exists: extract it as plain text (no source attribution,
no character names from the source). 1–4 lines, first-person or short
exchange preferred. Do NOT invent examples; only use what the analysis file
documents.

If no clean example exists: leave `example` empty.

### 5.4 Persist discoveries

For each extracted pattern, call:

```
write_author_discovery(
  author_slug=<slug>,
  section="style_principles",
  text=<formatted pattern>,
  book_slug=<derived-slug>,
  genres=<comma-separated genre list or "" if universal>,
  example=<illustrative prose/dialogue from analysis, or "" if none>
)
```

The MCP tool deduplicates by content and returns
`{written, already_present, warnings, extracted_patterns}`. Count
`written` and `already_present` separately. When `warnings` is non-empty,
surface them inline:

```
[{title}] {new} new / {skipped} already present
  ⚠ lint: [{warning text}] — pattern written but flagged; review manually
```

Warnings indicate the entry was written but may be too vague or malformed.
The user should decide whether to keep or delete the flagged entry.

### 5.5 Anti-patterns → surface for user (do not auto-write)

If `## Anti-Patterns Observed` (or `## Anti-Patterns`) contains entries
specific enough for a banned-phrase rule, surface them after the file is
processed:

> "Found {N} anti-pattern(s) in {title} that could become Don'ts rules:
> [list]. Want me to write these via `write_author_banned_phrase`?"

Do NOT write these automatically — anti-patterns require explicit user
confirmation because they affect the manuscript scanner's banned-phrase pass.

## Step 6: Report

After the loop completes:

```
Backfill complete: {author-slug}
─────────────────────────────────────────────
Analysis files scanned:           {N}
New style_principles written:     {total_new}
Already present (skipped):        {total_skipped}
Checklist items not found anywhere: {list of items, or "none"}
─────────────────────────────────────────────
```

If any files had errors, list them.

Tell the user:
- `/storyforge:author-check` will now surface `style_principles` compliance
  findings on the next chapter draft
- chapter-writer loads `style_principles` automatically — no session restart
  needed
- Any anti-patterns surfaced in Step 5.5 can still be written via
  `write_author_banned_phrase` if the user confirms

## Cost Note

One Opus LLM extraction pass per analysis file. For 7 files that's 7 reads
of analysis documents (~10–30k words each). Opus is warranted: the extraction
requires nuanced judgment between "concrete enough to be actionable" and
"too vague to promote." Sonnet would produce marginally useful patterns with
insufficient specificity.

## Idempotency

Running this skill twice is safe. `write_author_discovery` deduplicates by
content — a pattern already in the profile returns `already_present: true`
and is counted as skipped, not double-written. The skill can be re-run after
adding new genres to the author profile to extract newly-relevant patterns
from existing analysis files.

## Related

- `write_author_discovery` MCP tool — persistence path (deduplicates
  automatically)
- `study-author` Phase 1.5 — the forward-going extractor for new studied works
- `author-check` — verification gate that makes `style_principles` actionable
- Issue #262 — feature request that introduced this skill
- Issue #259 — Phase 1.5 (positive extraction) original implementation
- Issue #260 — PR that shipped Phase 1.5 in study-author
