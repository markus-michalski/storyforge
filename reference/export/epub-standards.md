# EPUB Standards Reference

## EPUB 3.x Overview

EPUB (Electronic Publication) is the standard eBook format supported by all major readers except Kindle (which now also accepts EPUB).

## File Structure

An EPUB is a ZIP archive containing:
```
META-INF/container.xml    # Points to content.opf
OEBPS/
  content.opf             # Package document (metadata + manifest + spine)
  toc.ncx                 # Navigation (EPUB 2 compatibility)
  nav.xhtml               # Navigation (EPUB 3)
  style.css               # Stylesheet
  chapter01.xhtml         # Content files
  chapter02.xhtml
  images/
    cover.jpg
```

## Required Metadata

```xml
<metadata xmlns:dc="http://purl.org/dc/elements/1.1/">
  <dc:title>Book Title</dc:title>
  <dc:creator>Author Name</dc:creator>
  <dc:language>en</dc:language>
  <dc:identifier id="bookid">urn:uuid:unique-id</dc:identifier>
  <meta property="dcterms:modified">2026-04-03T00:00:00Z</meta>
</metadata>
```

## Cover Image Requirements

| Platform | Minimum Size | Aspect Ratio | Format |
|----------|-------------|--------------|--------|
| Amazon KDP | 2560 x 1600 px | 1.6:1 | JPEG/TIFF |
| Apple Books | 1400 x 1873 px | ~3:4 | JPEG/PNG |
| Kobo | 1600 x 2400 px | 2:3 | JPEG/PNG |
| Generic EPUB | 1600 x 2400 px | 2:3 | JPEG |

**Best practice:** Create at 2560 x 3840 px (2:3 ratio) and let platforms resize.

## Typography Best Practices

### Font Embedding
- Embed fonts for consistent display
- Use `@font-face` in CSS
- License: Use open-source fonts (OFL) to avoid licensing issues

### Body Text
- Font size: 1em (let reader control)
- Line height: 1.4-1.6
- Paragraph indent: 1.5em (first paragraph after heading: no indent)
- No justified text in CSS (readers control this)

### Chapter Headings
- Use semantic HTML: `<h1>` for chapter titles
- `page-break-before: always` to start chapters on new page

## Accessibility (EPUB Accessibility 1.1)

- Alt text on all images
- Semantic HTML structure
- Language declaration
- Reading order in spine
- Navigation landmarks

## Validation

Use EPUBCheck (official W3C validator):
```bash
java -jar epubcheck.jar book.epub
```

Or online: https://www.w3.org/publishing/epubcheck/

## Platform-Specific Notes

### Amazon KDP
- Now accepts EPUB (previously only MOBI/KF8)
- Kindle Previewer for testing
- Enhanced typesetting enabled by default

### Apple Books
- Supports EPUB 3 features (audio, video, JavaScript)
- Author portal: Apple Books for Authors

### Kobo
- Standard EPUB 3
- Kobo Writing Life for self-publishing

### Google Play Books
- Standard EPUB 2/3
- Google Play Books Partner Center
