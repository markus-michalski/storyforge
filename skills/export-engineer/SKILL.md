---
name: export-engineer
description: |
  Generate EPUB, PDF, or MOBI from a book project via Pandoc — including an ARC
  (Advance Reader Copy / uncorrected proof) variant for beta-reader platforms.
  This PRODUCES the ARC file — for processing feedback that already came back from ARC
  readers, use /storyforge:beta-feedback instead.
  Use when: (1) User says "Export", "EPUB", "PDF", "MOBI", "create/generate/build an ARC",
  "Advance Reader Copy",
  (2) Book is in "Export Ready" status or user wants a draft export,
  (3) User wants a beta-reader/reviewer copy before the book is finished (e.g. for
  StoryOrigin, NetGalley, BookFunnel ARC teams).
model: claude-sonnet-4-6
user-invocable: true
argument-hint: "<book-slug> [format] [--arc]"
---

# Export Engineer

## Prerequisites
- Parse `--arc` out of the arguments first, if present — the remaining positional arguments are
  `<book-slug> [format]`. `--arc` is never a format value; don't let it fall into the `format` slot.
- Load book data via MCP `get_book_full()` — needed first to read `book_category`, since Step 0
  gates memoir books before pre-export gates ever run. Reuse this same result in Step 0 — don't
  call it again.
- Resolve the author display name once, here, and reuse it everywhere below (`metadata.yaml` in
  Step 3, both modes; the ARC front-matter template in Step 2.1). `get_book_full()`'s `author`
  field is the author-profile **slug** (e.g. `jane-doe`), not a display name — never write it
  directly wherever an author's name is supposed to appear. Call MCP `get_author(author_slug)` and
  take its `name` field instead.
  - `author_slug` empty, or `get_author()` returns an `error` key: **ARC mode** — **stop**, the
    disclaimer template has no other source for the author's name; tell the user to fix the book's
    author profile link first. **Non-ARC mode** — don't stop here. The non-ARC front-matter gate in
    Step 2.1 already guarantees `export/front-matter.md`'s own YAML `author:` field is non-empty, so
    that file's hand-authored value is a sufficient fallback; a book whose linked author profile was
    since deleted (see `delete-author`'s `force=True` path) shouldn't lose the ability to export.
    Just note "using the author name from `export/front-matter.md` — its linked author profile
    could not be resolved" alongside the export result, and use that YAML value in `metadata.yaml`
    instead of a resolved display name.
- Verify Pandoc is installed: `pandoc --version`
- For MOBI: verify Calibre's ebook-convert is installed

Pre-export gates (`run_pre_export_gates()`) are run in Step 1, not here — for memoir books, only
*after* Step 0's consent gate has passed.

**ARC mode (`--arc`).** An ARC is the same EPUB/PDF/MOBI file as the finished eBook — it differs
in front matter (an "uncorrected proof" disclaimer, built from `get_book_full()`/`get_author()`
data rather than `export/front-matter.md`), back matter (skipped unless the author opts in via a
hand-created `export/back-matter-arc.md` — no sales links/release-date content that isn't final
yet), the output filename (`{book_slug}-arc.{ext}`, so it can never collide with the release file),
the Step 5 next-step message, and in tolerating chapters that haven't cleared their final revision
pass (but never chapters with raw editorial comments still inline — see Step 2.2). `--arc` never
reads, modifies, or writes back `export/front-matter.md` or `export/back-matter.md` on disk — it
only changes what gets assembled into `manuscript.md` and the output filename for this run. Note
the ARC EPUB's own metadata (`dc:title` etc.) is otherwise identical to the release version — only
the rendered disclaimer page and the filename mark it as a proof, not the file's metadata. See
Steps 1, 2, 3, and 5 below for the specific differences.

## Workflow

### Step 0: Memoir consent gate _(memoir books only)_

Read `book_category` from the `get_book_full()` result already loaded in Prerequisites — don't
call it again.

If `book_category == "memoir"`: call MCP `check_memoir_consent(book_slug)`
**before** running pre-export gates.

- Overall `FAIL` → **hard stop**. Do not proceed. Tell the user:
  > Export blocked — at least one person has `consent_status: refused`.
  > Resolve via `/storyforge:memoir-ethics-checker` before exporting.
- Overall `WARN` → surface the warnings, ask the user to confirm they want
  to export anyway. Proceed only on explicit confirmation.
- Overall `PASS` → continue to Step 1.

### Step 1: Pre-Flight Check
Run MCP `run_pre_export_gates()`. If BLOCKED, show the issues and stop — **unless** `--arc` is set
and the *only* blocking gate with `"status": "FAIL"` is `"All chapters Final"`. ARCs are commonly
sent out before every chapter has cleared its final revision pass — that's what "uncorrected proof"
means. Any other blocking gate (e.g. `"Has chapters"`) still hard-stops regardless of `--arc` — this
override applies to that one specific gate only.

When the override applies:
1. Call MCP `get_book_progress(book_slug)` and cross-reference its per-chapter statuses against the
   non-final chapter slugs listed in the gate's `"detail"` field (`"Not final: {slugs}"`). Split them
   into two groups: chapters at `"Outline"` status (essentially undrafted — `create_chapter()`
   scaffolds these as just a bare `# Chapter N: Title` heading with no prose) vs. everything else
   (drafted but not yet finalized — the normal, expected ARC state).
2. Show both groups to the user. If any chapter is at `"Outline"` status, say so explicitly and
   plainly — e.g. "Chapters 8–10 are still empty outlines, not drafted prose. Exporting now will
   include them as near-blank chapters in the ARC." Don't soften or bury this; a beta-reader ARC
   with blank chapters reads as broken, not "unpolished."
3. Ask for one explicit confirmation covering the whole picture — this replaces the "If WARN-only"
   confirmation below for this run, it does not stack with it. If other gates (Word count target,
   Synopsis written) are also WARN, fold their warnings into the same single confirmation prompt
   rather than asking twice.

If BLOCKED for any other reason, or if `--arc` is not set: show the issues and stop as before.
If READY but WARN-only (no blocking gate fired at all): show warnings and ask if the user wants to
proceed anyway — this is the only case where this separate prompt applies.

### Step 2: Assemble Manuscript

> **Path resolution:** Call `resolve_path(book_slug, "export", "")` (MCP) to get the resolved book root before any file I/O — this handles both standalone (`projects/{slug}/`) and series-nested (`series/<series-slug>/{slug}/`) layouts.

Create a combined markdown file at the resolved `export/output/manuscript.md`:

1. **Front matter.** ARC and non-ARC read different source data here — each has its own
   completeness gate below, because ARC mode never uses `export/front-matter.md`'s own text.

   **Non-ARC:** Read `export/front-matter.md` (via resolved path). **Stop** here per the "NEVER
   export without assembled front-matter" rule below — tell the user front matter is
   missing/incomplete and export cannot proceed until they fill it in — if any of:
   - the file does not exist or is empty
   - it still contains the scaffold placeholder text `[Author Name]` (the `*by [Author Name]*`
     title-page line written by `create_book_structure()` at scaffold time)
   - its YAML frontmatter has an empty `author: ""` field

   Never fabricate a placeholder title page or copyright line yourself. Once the gate passes, strip
   the file's own leading YAML frontmatter block (`---\n...\n---\n`) before concatenating — it's
   scaffold metadata, not manuscript content, and its `author: ""` would otherwise sit at the head
   of `manuscript.md` and silently compete with the `author` field in the `metadata.yaml` passed to
   pandoc in Step 3.

   **ARC (`--arc`):** `export/front-matter.md` is not read at all for this — it's a separate,
   independently-authored file the ARC disclaimer intentionally replaces. Instead:
   1. Take `title` from the already-loaded `get_book_full()` result, and the author display name
      already resolved in Prerequisites (never `get_book_full()`'s own `author` field — that's a
      slug, e.g. `jane-doe`, not a display name, and would print as one on the ARC's title page).
   2. **Stop** and tell the user to set the book's title before ARC export — export cannot proceed
      until they fill it in — if `title` is empty. (The author-name equivalent of this check
      already happened in Prerequisites.) This is the ARC-mode counterpart to the non-ARC
      completeness gate above; it checks the fields ARC mode actually uses instead of
      `export/front-matter.md`'s content.
   3. No manual escaping is needed here, unlike the cover-image path in Step 3: `title` and the
      author display name go into plain markdown body text in `manuscript.md`, which pandoc parses
      and re-escapes itself on the way to EPUB/LaTeX output — this is a markdown-content boundary,
      not the raw-shell/raw-`.tex`-file boundary the cover-path warnings are about. Use the values
      as-is; do not LaTeX-escape them (`\&`, `\%`-style escaping would show up as literal escaped
      text in the rendered output instead of protecting anything).
   4. Read `{plugin_root}/templates/arc-front-matter-disclaimer.md` and fill its
      `{{title}}`/`{{author_name}}`/`{{year}}` placeholders with the values from step 1 — the same,
      unescaped display name also used for `metadata.yaml` in Step 3, not a separate copy.
      `{{year}}` is the current year from the session's current date — never a guessed or
      training-cutoff year, this is a copyright field.
   5. Replace the `<!-- Replace this line with the closing paragraph ... -->` comment at the end of
      the template with the closing paragraph matching `book_category` (from `get_book_full()`).
      This comment must never survive into the rendered manuscript — treat any `book_category`
      value other than `"memoir"` (including missing/empty) as `fiction`, matching how the rest of
      this plugin defaults the same field:
      - `fiction` (default): "This is a work of fiction. Names, characters, places, and incidents
        are either the product of the author's imagination or are used fictitiously. Any
        resemblance to actual persons, living or dead, events, or locales is entirely coincidental."
      - `memoir`: "This is a work of memoir. It reflects the author's own memories, perspective, and
        experience of real events. Some names and identifying details may have been changed to
        protect the privacy of those involved."
   6. Use the rendered result as the front matter block for `manuscript.md`. (The template has no
      YAML frontmatter of its own to strip — unlike `export/front-matter.md`, it's machine-filled
      only, so there's nothing scaffold-y at its head to compete with `metadata.yaml` in Step 3.)

   `export/front-matter.md` on disk is never read, modified, or written back in ARC mode.
2. **Chapters** — Call `resolve_path(book_slug, "chapters", "")` then read all `chapters/*/draft.md` in order
   - Each `draft.md` already starts with its own `# Chapter N: Title` line (written by
     `create_chapter()` at scaffold time) — do **not** prepend another header, or every chapter
     ends up with a duplicate title line in the assembled manuscript
   - Strip any leading YAML frontmatter block (`---\n...\n---\n`) from each draft before
     concatenating — it's scaffold metadata, not manuscript content
   - Check for any un-deleted `{review_handle}:` blocks first — call `get_review_handle_config()`
     for the configured `review_handle` value — these are inline author-review comments left in
     `draft.md` by the chapter-writer review loop and must never ship in the exported manuscript.
     If any remain, **stop** and ask the user to resolve or delete them before export continues.
     This check applies **regardless of `--arc`** — ARC mode tolerates chapters that aren't marked
     `Final`, but never chapters with raw editorial comments still inline; those are for the
     author's eyes only, in a proof exactly as much as in a finished book.
   - Add page breaks between chapters (`\newpage` for PDF, `---` for EPUB)
3. **Back matter**
   - **Non-ARC:** Read `export/back-matter.md` (via resolved path).
   - **ARC (`--arc`):** Check whether `export/back-matter-arc.md` exists at the resolved path
     first — this file is not scaffolded by `create_book_structure()`, it's an opt-in the author
     creates by hand. If it does, read and use that instead of `export/back-matter.md` — the author
     has prepared ARC-specific back matter (no sales links/release-date content that isn't final
     yet). If it does **not** exist, skip this section entirely — don't fall back to
     `export/back-matter.md` and don't fabricate ARC back matter yourself, but **do** tell the user
     in the Step 4 export summary: "No `export/back-matter-arc.md` found — exported without back
     matter. Create that file (e.g. a short author bio only) to include ARC-specific back matter
     next time." An ARC without back matter is safer than one that accidentally ships stale
     pre-order links, but the option should be visible, not silent.

### Step 3: Generate Output
If the format wasn't specified in the request: read `export.default_format` from
`~/.storyforge/config.yaml` (direct file read — no MCP tool covers config; `/storyforge:configure`
uses the same pattern). If a default is set, tell the user which format you're using (e.g.
"Using default format from config: EPUB — say a different format to switch") and proceed. Only
ask the user to choose (EPUB/PDF/MOBI) when the config file is missing or has no default set.

**Cover image lookup.** Call MCP `get_cover_image(book_slug)` before building the pandoc command.
- `cover_image_path` present → use it (see EPUB/PDF commands below). If the response also has a
  `warning` key, the path is a best-effort guess (an untracked file in `cover/art/`, not one
  recorded via `import_cover_image(is_final=True)`) — surface that warning to the user alongside
  the export result, don't just silently use it. (ARC mode: still worth surfacing — a guessed cover
  could be wrong, not just non-final.)
- `cover_image_path` is `null` → export without a cover. **Non-ARC:** if a `warning` key is present
  (e.g. several untracked candidates in `cover/art/` with none marked final), mention it — the user
  likely wants `import_cover_image(is_final=True)` on one of them before exporting for real. **ARC
  (`--arc`):** a missing final cover is the normal case at this stage — don't nudge the user toward
  `cover-artist`/`import_cover_image`, just export without one silently.
- `{"error": ...}` → the recorded final file is missing from disk; tell the user and ask whether
  to proceed without a cover or fix the DB record first. (Applies in ARC mode too — this means the
  DB record is stale, not just "no final cover yet.")

Before running the pandoc command, use the Write tool to create `export/output/metadata.yaml` with the book's title, author, and language as YAML key-value pairs. This avoids shell and LaTeX injection — never interpolate `{title}` or `{author}` directly into the shell command line (they are user-controlled strings and can contain shell metacharacters or LaTeX control sequences). `author` here is the display name resolved in Prerequisites — either `get_author().name`, or the `export/front-matter.md` YAML fallback in the non-ARC no-author-profile case — **not** `get_book_full()`'s own `author` field, which is a slug (e.g. `jane-doe`) and would render as one in the EPUB's `dc:creator`/the PDF title page in *either* mode. Example file content:
```yaml
---
title: "Exact title from get_book_full()"
author: "Resolved author display name from Prerequisites (get_author().name)"
lang: "en"
---
```
Escape any double-quote characters inside the value with a backslash. Use the book slug (already
URL-safe) as the output filename — never the raw title. Every command below is shown for the
non-ARC case; **in ARC mode (`--arc`), substitute `{book_slug}-arc` for `{book_slug}` in every `-o`/
`ebook-convert` output filename** (e.g. `{book_slug}-arc.epub`, not `{book_slug}.epub`) — this keeps
the proof file from being confused with, or accidentally overwriting, the final release file. This
substitution applies uniformly to the EPUB, PDF, and MOBI commands below, including the MOBI
section's intermediate EPUB.

**EPUB:** (non-ARC filename shown — apply the `-arc` substitution above if `--arc` is set)
```bash
pandoc manuscript.md -o "{book_slug}.epub" \
  --metadata-file metadata.yaml \
  --toc --toc-depth=1 \
  --epub-chapter-level=1
```
`lang` in `metadata.yaml` is the book's `language` field from `get_book_full()` (default `"en"`) — EPUB
requires a `dc:language` element; without it pandoc warns and epubcheck flags the output.

If `get_cover_image()` returned a `cover_image_path`, append `--epub-cover-image "{cover_image_path}"`
to the command above (quote the path — it can contain spaces).

**PDF:** (non-ARC filename shown — apply the `-arc` substitution above if `--arc` is set)
```bash
pandoc manuscript.md -o "{book_slug}.pdf" \
  --pdf-engine=xelatex \
  --metadata-file metadata.yaml \
  --toc \
  -V geometry:margin=1in \
  -V fontsize=11pt \
  -V mainfont="Linux Libertine O"
```

If `get_cover_image()` returned a `cover_image_path`, render it as a dedicated title page before
the manuscript, since pandoc's LaTeX path has no `--epub-cover-image` equivalent. Never write the
raw `cover_image_path` directly into a `.tex` file or command-line flag — same reasoning as the
`metadata.yaml` rule above, but sharper: an absolute Windows path (`C:\Users\...\cover.png`)
contains backslashes that LaTeX reads as control-sequence introducers, and the filename itself
(preserved verbatim from whatever the user's image generator produced) can contain LaTeX special
characters. Use a short, fixed, relative filename instead:

1. Copy the file at `cover_image_path` to `export/output/cover.jpg` (or `.png`/whatever its
   original extension is — keep it, just drop the rest of the path) using the Read/Write tools
   (or a file copy) — never a shell command that interpolates the path.
2. Use the Write tool to create `export/output/cover-preamble.tex`:
   ```latex
   \usepackage{graphicx}
   ```
3. Use the Write tool to create `export/output/cover-page.tex`, matching the extension used in
   step 1 (`cover.jpg` here — adjust if the source was e.g. `.png`):
   ```latex
   \begin{titlepage}
   \centering
   \includegraphics[width=\textwidth,height=\textheight,keepaspectratio]{cover.jpg}
   \end{titlepage}
   ```
4. Add two flags to the pandoc command above: `--include-in-header=cover-preamble.tex` and
   `--include-before-body=cover-page.tex`.
5. Run pandoc from `export/output/` (same as Step 2's resolved export path) so the relative
   `cover.jpg`/`cover-page.tex` references resolve.

Note: pandoc's default LaTeX template places `--include-before-body` content *after* its own
generated title page (built from `metadata.yaml`'s `title`/`author`), so the cover lands as the
second page, not the first — a template default, not a bug in this wiring.

**MOBI** inherits whatever cover was embedded in the intermediate EPUB automatically — no separate
cover step needed for the `ebook-convert` command below.

**MOBI (via Calibre):**
First generate EPUB (with the metadata file approach above), then convert. Run both commands from the resolved `export/output/` directory
(the path from Step 2's `resolve_path(book_slug, "export", "")` call) — the bare filenames below
only land in `export/output/` if that's the shell's current directory:
```bash
ebook-convert "{book_slug}.epub" "{book_slug}.mobi"
```
(non-ARC filenames shown — apply the `-arc` substitution above to *both* filenames if `--arc` is
set, including the intermediate EPUB.)
Keep the intermediate EPUB alongside the final MOBI in `export/output/` — don't delete it.

### Step 4: Verify
- If the pandoc/ebook-convert command exited non-zero, or the expected output file doesn't exist:
  **stop** and report the actual error to the user (don't proceed to Step 5 as if it succeeded).
- Check file exists and has reasonable size
- Report: format, file size, page/word count
- Show file path
- **ARC (`--arc`), if `export/back-matter-arc.md` was absent in Step 2.3:** include in this report
  "No `export/back-matter-arc.md` found — exported without back matter. Create that file (e.g. a
  short author bio only) to include ARC-specific back matter next time."

### Step 5: Offer Next Steps
- "Export another format?"
- "Ready to translate? → `/storyforge:translator`"
- **Non-ARC:** "Need a cover? → `/storyforge:cover-artist`" — **skip this in ARC mode** (Step 3
  already treats a missing cover as the normal ARC state, not something to nudge about; repeating
  the nudge here would contradict that).
- **ARC (`--arc`):** "ARC exported to `{book_slug}-arc.{ext}` — for the finished-book release
  version, run `/storyforge:export-engineer {book_slug} {format}` again without `--arc`."

## Rules
- ALWAYS run pre-export gates (Step 1) before assembling the manuscript — for memoir books, only
  after the Step 0 consent gate has passed
- NEVER use `get_book_full()`'s `author` field as a display name — it's a slug. Resolve the display
  name via `get_author()` in Prerequisites and reuse it everywhere (front matter, `metadata.yaml`,
  both modes). ARC mode hard-stops if that resolution fails; non-ARC mode falls back to
  `export/front-matter.md`'s own `author:` field instead of blocking — see Prerequisites
- NEVER export without assembled front matter — **non-ARC:** a completed title page and copyright
  block, no unresolved scaffold placeholders like `[Author Name]` or an empty `author` field.
  **ARC:** a non-empty book title and the resolved author display name rendered into the
  uncorrected-proof disclaimer. See Step 2.1 for the full gate per mode.
- Output files go to `{project}/export/output/`
- Keep the assembled manuscript.md for reference
- `--arc` NEVER reads, modifies, or writes back `export/front-matter.md` or `export/back-matter.md`
  on disk (Step 2.1, 2.3) — ARC content is assembled into `manuscript.md` and the output filename
  only, for that run
- The Step 0 memoir-consent gate is never affected by `--arc` — consent requirements apply
  identically to ARCs and finished books
- The Step 2 chapter review-handle check is never relaxed by `--arc` — see Step 2.2
