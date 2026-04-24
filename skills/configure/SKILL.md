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
   ```
   Current Configuration:
   =====================
   Content Root:    ~/projekte/book-projects
   Authors Root:    ~/.storyforge/authors
   Language:        en
   Book Type:       novel
   Export Format:   epub
   PDF Engine:      xelatex
   Pandoc Path:     pandoc
   Calibre Path:    ebook-convert
   Cover Platform:  midjourney
   ```
3. **Ask what to change** via AskUserQuestion
4. **Update config.yaml** — Edit the YAML file directly
5. **Verify** — Re-read and confirm changes

## Configurable Settings

| Setting | Key | Options |
|---------|-----|---------|
| Content directory | `paths.content_root` | Any valid path |
| Authors directory | `paths.authors_root` | Any valid path |
| Default language | `defaults.language` | en, de, es, fr, etc. |
| Default book type | `defaults.book_type` | short-story, novelette, novella, novel, epic |
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
4. Apply via MCP `update_author(slug, "author_writing_mode", value)`
5. Confirm the change
