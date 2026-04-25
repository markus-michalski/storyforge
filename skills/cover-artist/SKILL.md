---
name: cover-artist
description: |
  Generate cover art prompts for DALL-E or Midjourney based on genre and story.
  Use when: (1) User says "Cover", "Buchcover", (2) Book needs a cover.
model: claude-opus-4-7
user-invocable: true
argument-hint: "<book-slug>"
---

# Cover Artist

## Workflow

### Step 1: Context
- Load book data via MCP `get_book_full()`
- Read `{project}/synopsis.md` for story summary
- Load genre README(s) for visual conventions

### Step 2: Cover Brief
Develop with user in `{project}/cover/brief.md`:
- **Mood/atmosphere:** What should the cover FEEL like?
- **Key visual element:** One dominant image (don't overcrowd)
- **Color palette:** Genre conventions (horror=dark, romance=warm, sci-fi=cool/neon)
- **Typography style:** serif (literary/historical), sans-serif (modern/thriller), display (fantasy/horror)
- **Comparable covers:** "I want it to look like covers of [author/book]"

### Step 3: Generate Prompts
Write to `{project}/cover/prompts.md`:

**For Midjourney:**
```
/imagine [description], [style], [mood], [lighting], [composition],
book cover design, [genre] novel cover, professional book cover art,
--ar 2:3 --stylize [value] --v 6
```

**For DALL-E:**
```
A professional book cover for a [genre] novel titled "[Title]".
[Description of the key visual element].
[Mood and atmosphere]. [Color palette]. [Lighting].
Style: [photorealistic/illustrated/painted/graphic].
Composition: [centered/asymmetric/dramatic angle].
No text on the image.
```

Generate 3-5 prompt variations with different approaches:
1. **Symbolic:** Abstract representation of the theme
2. **Scene:** Key moment from the story
3. **Character:** Protagonist portrait/silhouette
4. **Object:** Iconic object from the story
5. **Atmospheric:** Mood/setting without characters

### Step 4: Platform Specs
Include size requirements:
- **Amazon KDP:** 2560 x 1600px (front cover), 300 DPI
- **EPUB:** 1600 x 2400px minimum
- **Print:** 6x9 inches at 300 DPI = 1800 x 2700px
- **Always generate WITHOUT text** — add title/author in post-processing

## Rules
- ALWAYS specify "no text" in prompts — text will be added separately
- Genre conventions matter: horror readers expect dark covers, romance expects warmth
- Less is more — one strong visual > cluttered composition
- The cover must work as a THUMBNAIL (social media, online stores)
