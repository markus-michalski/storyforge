---
name: configure
description: |
  Interactive configuration editor for ~/.storyforge/config.yaml.
  Use when: (1) User says "configure", "konfigurieren", "Einstellungen".
model: claude-sonnet-4-6
user-invocable: true
---

# Configure StoryForge

## Workflow

1. **Read current config** from `~/.storyforge/config.yaml`
2. **Show current settings** in a clear table:
   (this example is illustrative — always include every row from the Configurable Settings table
   below, not just the fields shown here)
   ```
   Current Configuration:
   =====================
   Content Root:    ~/projekte/book-projects
   Authors Root:    ~/.storyforge/authors
   Language:        en
   Book Type:       novel
   Book Category:   fiction
   Review Handle:   Markus
   Export Format:   epub
   PDF Engine:      xelatex
   Pandoc Path:     pandoc          (informational — not in Configurable Settings below)
   Calibre Path:    ebook-convert   (informational — not in Configurable Settings below)
   Cover Platform:  midjourney
   ```
3. **Ask what to change** via AskUserQuestion
4. **Update config.yaml** — Edit the YAML file directly
   Before writing: if the field's Options column names a closed list of values (not "Any valid
   path" / free text), check the requested value against it. If it isn't one of the listed values,
   tell the user so explicitly and confirm before writing it anyway — don't silently write an
   unlisted or mismatched value (this also covers a value that's valid for a *different* field,
   e.g. a `book_type` value requested for `book_category`).
5. **Verify** — Re-read and confirm changes
   The Edit tool's own success response is not sufficient — actually call `Read` on
   `~/.storyforge/config.yaml` again after editing, confirm the new value is present in the
   re-read content, then report it to the user.

## Configurable Settings

| Setting | Key | Options |
|---------|-----|---------|
| Content directory | `paths.content_root` | Any valid path |
| Authors directory | `paths.authors_root` | Any valid path |
| Default language | `defaults.language` | en, de, es, fr, etc. |
| Default book type | `defaults.book_type` | short-story, novelette, novella, novel, epic |
| Default book category | `defaults.book_category` | fiction, memoir |
| Review comment handle | `defaults.review_handle` | Your name/identifier for inline draft.md annotations |
| Export format | `export.default_format` | epub, pdf, mobi |
| PDF engine | `export.pdf_engine` | xelatex, pdflatex, wkhtmltopdf |
| Cover platform | `cover.platform` | midjourney, dall-e |

## Author Profile Settings

These settings live in the author's `profile.md` frontmatter, not in `config.yaml`.
Use MCP `update_author(slug, field, value)` to apply changes.

| Setting | Field | Options |
|---------|-------|---------|
| Writing process mode | `author_writing_mode` | `outliner` \| `plantser` \| `discovery` |

**To change an author's writing mode:**
1. Ask which author profile to edit via MCP `list_authors()`
2. Show current value via MCP `get_author(slug)`
3. Ask for new value with AskUserQuestion (Outliner / Plantser / Discovery)
   Even if the user already stated a value in their message, still check it against these three
   options before applying it — don't skip validation just because an explicit re-ask feels
   redundant.
4. Apply via MCP `update_author(slug, "author_writing_mode", value)`
5. Confirm the change
