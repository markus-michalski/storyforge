---
name: cover-artist
description: |
  Generate cover art prompts for DALL-E or Midjourney based on genre and story.
  Use when: (1) User says "Cover", "Buchcover", (2) Book needs a cover.
  Works for both fiction and memoir books.
model: claude-opus-4-7
user-invocable: true
argument-hint: "<book-slug>"
---

# Cover Artist

## Workflow

### Step 1: Context
- Load book data via MCP `get_book_full()`
- Read `book_category` — branch Step 2 and Step 3 on `fiction` vs `memoir`
- Read `{project}/synopsis.md` for story summary
- Load genre README(s) for visual conventions

### Step 2: Cover Brief

Develop with user in `{project}/cover/brief.md`. Branch by `book_category`:

**Fiction brief questions:**
- **Mood/atmosphere:** What should the cover FEEL like?
- **Key visual element:** One dominant image (don't overcrowd)
- **Color palette:** Genre conventions (horror=dark, romance=warm, sci-fi=cool/neon)
- **Typography style:** serif (literary/historical), sans-serif (modern/thriller), display (fantasy/horror)
- **Comparable covers:** "I want it to look like covers of [author/book]"

**Memoir brief questions:**
- **Cover approach:** Photographic (personal/period photo), Typographic (bold text, minimal image), or Portrait (author-as-subject)?
- **Photo availability:** Is there a meaningful real photo — author at the relevant age, a significant place, a family object?
- **Time period feel:** Should the cover signal the era the memoir covers (vintage tones, period aesthetic) or feel contemporary?
- **Author presence:** Should the author's face/image appear on the cover, or stay anonymous (place, object, silhouette)?
- **Tone:** Intimate and personal? Weighty and serious? Warm and reflective?
- **Comparable covers:** Memoir covers to reference (e.g., *The Glass Castle*, *Educated*, *Between the World and Me*, *When Breath Becomes Air*)

### Step 3: Generate Prompts

Write to `{project}/cover/prompts.md`. Branch by `book_category`:

---

**Fiction prompts:**

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

Fiction prompt variations (generate 3-5):
1. **Symbolic:** Abstract representation of the theme
2. **Scene:** Key moment from the story
3. **Character:** Protagonist portrait/silhouette
4. **Object:** Iconic object from the story
5. **Atmospheric:** Mood/setting without characters

---

**Memoir prompts:**

Memoir covers lean toward restraint — authenticity over drama. The cover should feel like the book: personal, honest, unguarded.

**For Midjourney:**
```
/imagine [description], [period/mood], [color palette], [lighting],
memoir book cover design, literary memoir cover, typographic emphasis,
professional book cover, --ar 2:3 --stylize [value] --v 6
```

**For DALL-E:**
```
A professional book cover for a memoir titled "[Title]".
[Description of the central visual element — photo, place, or portrait].
[Time period and atmosphere]. [Color palette — muted/warm/high-contrast].
[Lighting — soft and natural / dramatic / nostalgic].
Style: [photorealistic / documentary photography aesthetic / vintage].
Composition: [centered portrait / full-bleed place / object against plain background].
No text on the image.
```

Memoir prompt variations (generate 3-4 — not all will apply):
1. **Portrait approach:** Close or medium shot of a person at the relevant age/time period — evokes the human at the center of the story. If using AI: do not use a real person's likeness; generate an anonymous portrait in period-appropriate style.
2. **Place approach:** A meaningful location from the memoir — a childhood home, a road, a landscape — rendered with emotional weight. Often the strongest memoir cover.
3. **Object approach:** A significant personal object — a photograph, a letter, a worn item — on a plain or textured background. Works best for intimate, small-scope memoirs.
4. **Typographic approach:** Minimal or no image — strong typography does the work. Bold author name + title, atmospheric paper/texture background. Common for literary and political memoirs.

**Color palette guidance for memoir:**
- Period memoir (pre-1980): desaturated, warm-sepia, faded tones, aged paper
- Contemporary memoir: cleaner tones, high contrast, or muted naturalistic
- Trauma/difficult subject memoir: high contrast, stark, monochrome + accent color
- Warm/family memoir: soft warm tones, golden light, lived-in textures

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
- **Memoir:** never generate a real person's likeness in AI prompts — use anonymous period portraits or places/objects instead. If the author wants their own photo on the cover, that's a separate production task (photographer or existing photo), not an AI-generation task.
