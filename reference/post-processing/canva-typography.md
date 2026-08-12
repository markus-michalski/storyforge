---
tool: canva
craft_topic: cover-typography
status: stable
last_reviewed: 2026-08-12
---

# Canva: Cover Typography Reference

Reference for compositing title/author text onto a pre-generated cover image (no text baked in) in Canva. Not a tutorial — assumes basic familiarity with the editor's Text panel.

## Letter-Spacing ("Spacing")

Select a text box → toolbar → **Spacing** icon opens a small panel with two sliders: **Letter spacing** (left slider) and **Line spacing** (right slider). Drag right to open up letters, left to tighten; a numeric field next to the slider accepts direct input for precision.

Functionally this is the same concept as Photoshop's tracking — Canva's own "beginner's guide to kerning" (`canva.com/learn/kerning`) uses the terms letter spacing and tracking interchangeably. The mechanism differs in one important way: **Canva applies a single metric tracking value, with no per-pair manual kerning override.** Photoshop and GIMP both let you nudge the space between one specific letter pair; Canva does not expose that — if a specific pair (a capital "T" next to a lowercase "o," for instance) looks off, your only lever in Canva is the global letter-spacing value or physically retyping/adjusting via a different font.

### The scale-mismatch gotcha — what we could and couldn't verify

Canva's letter-spacing slider has **no publicly documented unit**. Canva's help center, its own "kerning" explainer, and every third-party tutorial we found describe the control only behaviorally ("drag right to increase spacing") — none states whether the numeric value is a percentage of em, a raw pixel value at the canvas's internal resolution, or a proprietary arbitrary scale. No official Canva documentation, Adobe Community thread, or design-blog benchmark we located publishes a verified numeric conversion between a Canva letter-spacing value and Photoshop's 1/1000-em tracking value.

**Do not treat any specific "Canva N ≈ Photoshop M" ratio you find online as verified — we searched and could not confirm one exists as a documented spec.** The two scales are not 1:1, and the practical gap is exactly the reason this reference file exists: an author copying "tracking: 40" from a Photoshop mockup into Canva's letter-spacing field will not get a visually equivalent result.

**Working method instead of a formula:**
1. Set spacing visually in whichever tool you're using, judging against the actual rendered text at the cover's final pixel size — not against a numeric value from another tool.
2. If you need the *same* title treatment reproduced in both tools (e.g. testing Canva's font-pairing suggestions against a Photoshop mockup), export a flattened reference image from the first tool and overlay/eyeball-compare in the second, adjusting the slider until they visually match — then note down "at font size X, this looked right at slider value Y" as a project-specific reference point, not a portable constant.
3. Re-check at thumbnail scale (per `cover-specs.md`'s 160×256px thumbnail test) every time you change spacing — tight tracking that looks fine at full title size can collapse into an illegible smear at thumbnail size, and this effect differs by tool since anti-aliasing/rendering differs.

## Font-Pairing Workflow

Canva is the strongest of the three tools here for pairing *guidance* specifically:

- **Font combinations panel**: in the Text tab of the editor, Canva surfaces a curated **Font combinations** section — pre-built pairs (typically a display/heading font + a complementary body font) that apply to both a heading and body text box in one click when you select a combination.
- You can type a search term in the Text tab to narrow suggested combinations (e.g. searching a mood/style keyword filters the suggested pairs).
- This is a curated/algorithmic suggestion feature, not a rule-based typographic pairing engine — treat suggestions as a fast starting point, then hand-verify the pairing against `cover-specs.md`'s genre font guidance (e.g. "Fantasy: ornate serif, medieval" / "Thriller: bold sans-serif, clean") since Canva's suggestions are aesthetic-general, not book-genre-aware.
- For book covers specifically, apply the suggested pairing to title (heading) and author name (body-ish) as separate text boxes rather than relying on Canva's combination defaulting to paragraph-style body copy — resize each independently once applied.

## Text Effects Panel (Shadow, Glow, Bevel-equivalents)

Canva groups drop-shadow/glow/outline treatments under one **Effects** panel (select text → toolbar → **Effects**), offering built-in presets rather than raw layer-style controls:

| Effect | What it does | Adjustable params |
|---|---|---|
| **Shadow** | Standard drop shadow behind the text | Offset, Direction, Blur, and (in some presets) color |
| **Lift** | Subtle soft shadow that reads as gentle depth without a hard offset | Preset-level only, minimal manual control |
| **Hollow** | Converts fill to an outline-only "hollow" letterform | Outline thickness |
| **Splice** | Offset duplicate-layer effect (a secondary colored copy of the text offset behind the original) | Offset, color |
| **Outline** | Solid stroke around the letterforms — **this is Canva's direct equivalent to Photoshop's Stroke layer style**, and the one most relevant to the grayscale/e-ink legibility rule already tracked for this project (outline beats color-only contrast on e-ink) | Thickness, color |
| **Echo** | Repeated offset copies, creating a layered/echo look | Offset, direction |
| **Glitch** | Digital-distortion offset in RGB channels | Preset-level, minor offset control |
| **Neon** | Glow treatment simulating a lit neon tube — closest Canva equivalent to Photoshop's Outer Glow | Glow intensity/color (preset-driven) |

**No native Bevel/Emboss equivalent.** Canva has no 3D bevel/emboss text effect comparable to Photoshop's Bevel & Emboss layer style or GIMP's Bevel GEGL filter — Canva's effects are all 2D (shadow, outline, offset, glow), not simulated dimensional lighting. If a cover concept needs an embossed/3D title treatment, that has to be done in Photoshop or GIMP and imported into Canva as a flattened text-image element, or skipped in favor of one of Canva's flat effects.

**For grayscale/e-ink legibility** (per this project's existing cover guidance): use **Outline** with a dark, sufficiently thick stroke rather than relying on Shadow alone — Shadow's soft blur can wash out entirely at low bit-depth grayscale rendering, while a hard Outline holds up.

## Export / Resolution Settings

- **Color mode:** Canva exports **RGB by default**. At the time this was researched, CMYK export required **Canva Pro** (paid), via **Download → File type: "PDF Print" → Colour Profile: CMYK** (with crop marks/bleed also selectable in that same dialog) — sourced from third-party design-blog coverage, not Canva's own pricing/feature page, so **verify current tier gating and the exact menu path in Canva's own help center before relying on it**; free-vs-Pro feature gates are exactly the kind of detail that shifts between plan changes. If CMYK is still Pro-gated, free-tier users needing CMYK for print submission must run the exported RGB file through a separate converter or another tool (Photoshop/GIMP+plugin), or accept the print vendor's own RGB→CMYK conversion.
- Given IngramSpark's hard CMYK requirement and KDP's ICC-profile auto-conversion on RGB print submissions (see the Photoshop reference file in this set for detail), **Canva Pro's native PDF Print CMYK export is the more reliable path for print covers** if working entirely in Canva; free-tier users should route through another tool for print, and use Canva only for the eBook (RGB) version.
- **eBook cover export:** Download → File type **PNG or JPG** at the largest available resolution; explicitly size the Canva canvas to the target platform's pixel dimensions from `cover-specs.md` before exporting (e.g. KDP's ~1600×2560px eBook target) rather than relying on Canva's default canvas presets, which are not guaranteed to match current KDP/IngramSpark/Draft2Digital pixel specs.
- **Print cover export (Pro only):** Download → **PDF Print** → enable **Crop marks and bleed** → **Colour Profile: CMYK**. This is the closest Canva gets to IngramSpark's PDF/X + bleed + CMYK requirement set, but Canva's PDF Print output has not been independently confirmed as strict PDF/X-1a/PDF/X-3 compliant — verify the exported PDF against IngramSpark's or KDP's file checker before final submission rather than assuming Canva's "print-ready" label satisfies platform-level PDF/X validation.
- Canva has no DPI setting exposed to the user directly; resolution is governed by canvas pixel dimensions at export, so hitting the platform's minimum pixel dimensions (not a DPI number) is the actionable target inside Canva.

## Sources

- [A beginner's guide to kerning like a designer — Canva](https://www.canva.com/learn/kerning/)
- [Format text — Canva Help Center](https://www.canva.com/help/format-text/)
- [Easy Tips for Perfect Letter Spacing in Canva — Artphysis](https://artphysis.com/letter-spacing-in-canva/)
- [Use Canva Text Effects: Glitch, Neon + More — Design Bundles](https://designbundles.net/design-school/how-to-use-canva-text-effects)
- [50 Amazing Canva Text Effects and Elements — Design Hub](https://designhub.co/canva-text-effects/)
- [Complete Guide to Canva Font Pairings — Motion Stamp](https://motionstamp.com/en-us/blogs/news/best-canva-font-pairings)
- [Is Canva In CMYK? — FunnelGraphic](https://funnelgraphic.com/is-canva-in-cmyk/)
- [How to Export Your Canva File in a Print-Ready Format — Jukebox](https://support.jukeboxprint.com/en/articles/9811359-how-to-export-your-canva-file-in-a-print-ready-format)
- [RGB vs. CMYK Colours: Why It Matters for Printing & How to Choose in Canva — Little Rock Printing](https://littlerockprinting.com/rgb-vs-cmyk-colours-in-canva/)
