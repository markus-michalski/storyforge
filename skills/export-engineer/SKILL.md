---
name: export-engineer
description: |
  Generate EPUB, PDF, or MOBI from a book project via Pandoc.
  Use when: (1) User says "Export", "EPUB", "PDF", "MOBI",
  (2) Book is in "Export Ready" status or user wants a draft export.
model: claude-sonnet-4-6
user-invocable: true
argument-hint: "<book-slug> [format]"
---

# Export Engineer

## Prerequisites
- Load book data via MCP `get_book_full()` — needed first to read `book_category`, since Step 0
  gates memoir books before pre-export gates ever run. Reuse this same result in Step 0 — don't
  call it again.
- Verify Pandoc is installed: `pandoc --version`
- For MOBI: verify Calibre's ebook-convert is installed

Pre-export gates (`run_pre_export_gates()`) are run in Step 1, not here — for memoir books, only
*after* Step 0's consent gate has passed.

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
Run MCP `run_pre_export_gates()`. If BLOCKED, show the issues and stop.
If WARN-only, show warnings and ask if user wants to proceed anyway.

### Step 2: Assemble Manuscript

> **Path resolution:** Call `resolve_path(book_slug, "export", "")` (MCP) to get the resolved book root before any file I/O — this handles both standalone (`projects/{slug}/`) and series-nested (`series/<series-slug>/{slug}/`) layouts.

Create a combined markdown file at the resolved `export/output/manuscript.md`:

1. **Front matter** — Read `export/front-matter.md` (via resolved path). **Stop** here per the
   "NEVER export without assembled front-matter" rule below — tell the user front matter is
   missing/incomplete and export cannot proceed until they fill it in — if any of:
   - the file does not exist or is empty
   - it still contains the scaffold placeholder text `[Author Name]` (the `*by [Author Name]*`
     title-page line written by `create_book_structure()` at scaffold time)
   - its YAML frontmatter has an empty `author: ""` field

   Never fabricate a placeholder title page or copyright line yourself. Once the gate passes,
   strip the file's own leading YAML frontmatter block (`---\n...\n---\n`) before concatenating —
   it's scaffold metadata, not manuscript content, and its `author: ""` would otherwise sit at the
   head of `manuscript.md` and silently compete with the `author` field in the `metadata.yaml`
   passed to pandoc in Step 3.
2. **Chapters** — Call `resolve_path(book_slug, "chapters", "")` then read all `chapters/*/draft.md` in order
   - Each `draft.md` already starts with its own `# Chapter N: Title` line (written by
     `create_chapter()` at scaffold time) — do **not** prepend another header, or every chapter
     ends up with a duplicate title line in the assembled manuscript
   - Strip any leading YAML frontmatter block (`---\n...\n---\n`) from each draft before
     concatenating — it's scaffold metadata, not manuscript content
   - Check for any un-deleted `{review_handle}:` blocks first — call `get_review_handle_config()`
     for the configured `review_handle` value — these are inline author-review comments left in
     `draft.md` by the chapter-writer review loop and must never ship in the exported manuscript.
     If any remain, **stop** and ask the user to resolve or delete them before export continues
   - Add page breaks between chapters (`\newpage` for PDF, `---` for EPUB)
3. **Back matter** — Read `export/back-matter.md` (via resolved path)

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
  the export result, don't just silently use it.
- `cover_image_path` is `null` → export without a cover. If a `warning` key is present (e.g.
  several untracked candidates in `cover/art/` with none marked final), mention it — the user
  likely wants `import_cover_image(is_final=True)` on one of them before exporting for real.
- `{"error": ...}` → the recorded final file is missing from disk; tell the user and ask whether
  to proceed without a cover or fix the DB record first.

Before running the pandoc command, use the Write tool to create `export/output/metadata.yaml` with the book's title, author, and language as YAML key-value pairs. This avoids shell and LaTeX injection — never interpolate `{title}` or `{author}` directly into the shell command line (they are user-controlled strings and can contain shell metacharacters or LaTeX control sequences). Example file content:
```yaml
---
title: "Exact Title from get_book_full()"
author: "Exact Author from get_book_full()"
lang: "en"
---
```
Escape any double-quote characters inside the value with a backslash. Use the book slug (already URL-safe) as the output filename — never the raw title.

**EPUB:**
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

**PDF:**
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
Keep the intermediate EPUB alongside the final MOBI in `export/output/` — don't delete it.

### Step 4: Verify
- If the pandoc/ebook-convert command exited non-zero, or the expected output file doesn't exist:
  **stop** and report the actual error to the user (don't proceed to Step 5 as if it succeeded).
- Check file exists and has reasonable size
- Report: format, file size, page/word count
- Show file path

### Step 5: Offer Next Steps
- "Export another format?"
- "Ready to translate? → `/storyforge:translator`"
- "Need a cover? → `/storyforge:cover-artist`"

## Rules
- ALWAYS run pre-export gates (Step 1) before assembling the manuscript — for memoir books, only
  after the Step 0 consent gate has passed
- NEVER export without assembled front-matter (title page, copyright, no unresolved scaffold
  placeholders like `[Author Name]` or an empty `author` field)
- Output files go to `{project}/export/output/`
- Keep the assembled manuscript.md for reference
