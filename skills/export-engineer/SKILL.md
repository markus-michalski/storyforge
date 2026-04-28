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
- Run MCP `run_pre_export_gates()` — check if book is ready
- Load book data via MCP `get_book_full()`
- Verify Pandoc is installed: `pandoc --version`
- For MOBI: verify Calibre's ebook-convert is installed

## Workflow

### Step 0: Memoir consent gate _(memoir books only)_

Call MCP `get_book_full(book_slug)` and read `book_category`.

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
Create a combined markdown file at `{project}/export/output/manuscript.md`:

1. **Front matter** — Read `{project}/export/front-matter.md`
2. **Chapters** — Read all `{project}/chapters/*/draft.md` in order
   - Add `# Chapter N: Title` headers
   - Add page breaks between chapters (`\newpage` for PDF, `---` for EPUB)
3. **Back matter** — Read `{project}/export/back-matter.md`

### Step 3: Generate Output
Ask user for format if not specified (default from config):

**EPUB:**
```bash
pandoc manuscript.md -o "{title}.epub" \
  --metadata title="{title}" \
  --metadata author="{author}" \
  --toc --toc-depth=1 \
  --epub-chapter-level=1
```

**PDF:**
```bash
pandoc manuscript.md -o "{title}.pdf" \
  --pdf-engine=xelatex \
  --metadata title="{title}" \
  --metadata author="{author}" \
  --toc \
  -V geometry:margin=1in \
  -V fontsize=11pt \
  -V mainfont="Linux Libertine O"
```

**MOBI (via Calibre):**
First generate EPUB, then convert:
```bash
ebook-convert "{title}.epub" "{title}.mobi"
```

### Step 4: Verify
- Check file exists and has reasonable size
- Report: format, file size, page/word count
- Show file path

### Step 5: Offer Next Steps
- "Export another format?"
- "Ready to translate? → `/storyforge:translator`"
- "Need a cover? → `/storyforge:cover-artist`"

## Rules
- ALWAYS run pre-export gates first
- NEVER export without assembled front-matter (title page, copyright)
- Output files go to `{project}/export/output/`
- Keep the assembled manuscript.md for reference
