# Pandoc Export Guide for StoryForge

## Overview

StoryForge uses Pandoc to convert Markdown manuscripts into EPUB, PDF, and MOBI formats. This guide covers configuration, templates, and troubleshooting.

## Installation

```bash
# Ubuntu/Debian
sudo apt install pandoc texlive-xetex texlive-fonts-recommended

# macOS
brew install pandoc basictex

# For MOBI: install Calibre
sudo apt install calibre    # or download from calibre-ebook.com
```

## EPUB Generation

```bash
pandoc manuscript.md -o book.epub \
  --metadata title="Book Title" \
  --metadata author="Author Name" \
  --metadata lang="en" \
  --toc --toc-depth=1 \
  --epub-chapter-level=1 \
  --css=style.css
```

### Key Options
- `--toc`: Generate table of contents
- `--toc-depth=1`: Only top-level chapters in TOC
- `--epub-chapter-level=1`: Split at H1 headers (one file per chapter)
- `--css`: Custom stylesheet for typography
- `--epub-cover-image`: Cover image path
- `--epub-metadata`: Additional EPUB metadata XML

### EPUB CSS Template
```css
body {
  font-family: Georgia, "Times New Roman", serif;
  font-size: 1em;
  line-height: 1.6;
  margin: 1em;
}

h1 {
  font-size: 1.8em;
  margin-top: 3em;
  page-break-before: always;
}

p {
  text-indent: 1.5em;
  margin: 0;
}

p.first, h1 + p, h2 + p, h3 + p, hr + p {
  text-indent: 0;
}

blockquote {
  font-style: italic;
  margin: 1em 2em;
}
```

## PDF Generation

```bash
pandoc manuscript.md -o book.pdf \
  --pdf-engine=xelatex \
  --metadata title="Book Title" \
  --metadata author="Author Name" \
  --toc \
  -V geometry:margin=1in \
  -V fontsize=11pt \
  -V mainfont="Linux Libertine O" \
  -V documentclass=book \
  -V classoption=openright
```

### Key Options
- `--pdf-engine=xelatex`: Full Unicode support, system fonts
- `-V geometry:margin=1in`: Page margins
- `-V mainfont`: System font (must be installed)
- `-V documentclass=book`: Book layout with chapters
- `-V classoption=openright`: Chapters start on right page

### Recommended Fonts
- **Serif (body):** Linux Libertine O, EB Garamond, Crimson Pro
- **Sans (headers):** Linux Biolinum O, Lato, Source Sans Pro
- **Mono (if needed):** Fira Mono, Inconsolata

## MOBI Generation

Pandoc doesn't generate MOBI directly. Use Calibre's `ebook-convert`:

```bash
# First generate EPUB, then convert
pandoc manuscript.md -o book.epub [options]
ebook-convert book.epub book.mobi
```

Note: Amazon now prefers EPUB over MOBI for KDP submissions.

## Manuscript Assembly

The `export-engineer` skill assembles chapters in order:

```markdown
---
title: "Book Title"
author: "Author Name"
lang: en
---

[Front matter: title page, copyright, dedication]

# Chapter 1: The Beginning

[Chapter 1 content]

# Chapter 2: Into the Dark

[Chapter 2 content]

[...]

[Back matter: about author, other books]
```

### Chapter Breaks
- EPUB: Use `# Chapter Title` (H1 headers)
- PDF: Add `\newpage` before each chapter header

## Troubleshooting

### "Font not found"
Install the font system-wide or use a different font with `-V mainfont`.

### Unicode characters missing
Use `--pdf-engine=xelatex` (not pdflatex). XeLaTeX handles Unicode natively.

### EPUB validation errors
Run `epubcheck book.epub` to find issues. Common fix: ensure all images are referenced correctly.

### Large file size
- Compress images before embedding
- Use `--epub-chapter-level=1` to split into smaller files
- Remove unnecessary metadata
