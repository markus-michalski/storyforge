---
tool: gimp
craft_topic: cover-typography
status: stable
last_reviewed: 2026-08-12
---

# GIMP: Cover Typography Reference

Reference for compositing title/author text onto a pre-generated cover image (no text baked in) in GIMP (2.10 and 3.0 filter names both noted where they differ). Not a tutorial — assumes basic familiarity with the Text tool and Layers dialog.

## Letter-Spacing and Kerning

GIMP's Text tool options panel exposes distinct **Kerning** and **Letter Spacing** fields, and — unlike Photoshop and Canva — GIMP's own documentation is explicit that these are two mechanically different operations, not just UI labels for the same thing (`docs.gimp.org` Text Management chapter):

- **Letter Spacing**: applies to the *entire* text layer (not a selection). The numeric value is **pixels added to or subtracted from the space between letters** — a raw pixel offset, not an em-relative or percentage value. Negative values tighten, positive values open up.
- **Kerning**: adjusts spacing for a *specific selected range* or a single character pair (click between two letters with nothing else selected). GIMP's docs describe kerning as inserting blank space "2 pixels wide" between selected characters as the base unit, with letter widths preserved — again, a pixel-based mechanism, not em-based.
- There is also a **Tracking** field described in GIMP's typography controls (grouped with font size, leading/line-spacing, and kerning) — in GIMP's terminology tracking and letter-spacing map to the same underlying control described above.

### Why this doesn't convert cleanly to Photoshop or Canva

Photoshop's tracking is em-relative (1/1000 em, scales with point size — see the Photoshop reference file in this set). GIMP's letter spacing is a **flat pixel value independent of point size**: 5px of letter-spacing on 40pt text and 5px on 200pt text add the identical amount of physical space, whereas Photoshop's 5/1000 em tracking scales up proportionally with the larger size. This means even if a numeric Canva↔Photoshop conversion existed (it doesn't, per the Canva reference file), a third GIMP-pixel conversion couldn't be a fixed ratio either — it would have to be recalculated per font size, per canvas resolution.

**Practical implication:** treat GIMP's letter-spacing value as tied to *this specific composite's pixel dimensions and point size*. If you resize the canvas (e.g. moving from a working-resolution draft to the final 300 DPI export size), re-check spacing visually rather than assuming the pixel value still looks right — a value that read correctly at a smaller working canvas will look proportionally tighter once the canvas (and font point size with it) scales up, since the pixel offset stays fixed while everything else grows. Cross-checking against a Photoshop or Canva mockup should be done visually at matched final pixel dimensions, not by porting the numeric value.

## Font-Pairing Workflow

GIMP has **no built-in font-pairing suggestion feature** — no equivalent to Canva's Font Combinations panel or Adobe Fonts' curated pairing UI. Font selection workflow:

1. **Text tool options → font field**: type-ahead search across installed system fonts, with a live thumbnail preview of each font name rendered in that font next to its name in the dropdown list — useful for fast visual scanning, but not classification-filterable (no "show only serif" toggle the way Photoshop's Character panel offers).
2. Because there's no pairing intelligence, decide the title/author font pairing **before** opening GIMP — using `cover-specs.md`'s genre guidance directly, or a pairing chosen in Canva/a font-pairing reference site — then just apply the two fonts to separate text layers in GIMP.
3. Fonts must be installed at the OS level (or in GIMP's user fonts folder) to appear in the Text tool's font list; GIMP has no cloud font sync comparable to Adobe Fonts.
4. Keep title and author text as **separate text layers**, same rationale as the Photoshop reference: independent letter-spacing, independent filter effects, independent positioning.

## Layer/Filter Effects for Cover Text

GIMP has no unified non-destructive "layer style" panel like Photoshop's — effects are applied as **filters**, which in GIMP 2.10+ are largely GEGL-based (destructive by default unless applied via a duplicated layer or, in recent versions, GIMP's limited non-destructive filter re-editing before the layer is flattened). Relevant filters, all under **Filters** menu:

| Effect | Menu path | Notes |
|---|---|---|
| **Drop Shadow** | Filters → Light and Shadow → Drop Shadow | GEGL filter (GIMP 2.10+, replacing the older Script-Fu "Drop Shadow (legacy)" under Filters → Light and Shadow → Drop Shadow (legacy)). Controls: X/Y offset in pixels, blur radius, color, opacity/grow. Applies directly to the layer's alpha — works cleanly on a text layer since text layers already have transparent backgrounds. |
| **Bevel** | Filters → Light and Shadow → Bevel | GEGL filter. Two types: **Chamfer** (default — simulates a sloped/chamfered 3D edge) and **Bump**. This is GIMP's closest equivalent to Photoshop's Bevel & Emboss, though with fewer sub-controls (no separate Contour/Texture sub-effects the way Photoshop nests them). |
| **Outer Glow** | *No dedicated filter* | GIMP has no single-click Outer Glow filter. Standard workaround: duplicate the text layer, apply Gaussian Blur (Filters → Blur → Gaussian Blur) to the duplicate, set its blend mode to Screen or Addition, place it beneath the original text layer, and optionally recolor the blurred copy via Colors → Curves or a Color Balance adjustment. This is a manual multi-step reconstruction of what Photoshop and Canva expose as one preset. |
| **Stroke/Outline** | **Select → From alpha channel** on the text layer, then **Select → Grow** by N px, then fill the grown selection on a new layer beneath the text — or **Edit → Stroke Path/Selection** directly on the alpha-channel selection | No single "Outline" toggle like Canva's; requires the alpha-to-selection-to-stroke sequence. This is the technique to use for the grayscale/e-ink legibility rule already tracked for this project — a hard-edged pixel outline survives grayscale/e-ink rendering better than a soft shadow or glow. |

Because GIMP filters are more manual-assembly than the one-click presets in Photoshop/Canva, consider building the shadow/glow/outline stack once, then **Script-Fu**-recording or saving the layered .xcf as a reusable template if the same title treatment needs to repeat across a series (per this project's series-cover consistency guidance).

## Export / Resolution Settings

- **Native colorspace is RGB.** GIMP has **no native CMYK editing mode** — GIMP opens/imports CMYK source images by converting them to RGB, and has no built-in way to author or export true CMYK. This is a hard limitation, not a preference: GIMP's own project history shows CMYK export was only prototyped in a 2022 Google Summer of Code project and is not standard in mainline releases as of this writing.
- **Practical consequence for print covers:** IngramSpark requires CMYK in the delivered PDF (all images CMYK, ≤240% total ink coverage). GIMP cannot natively produce that. Workaround: install the third-party **Separate+** plugin (`blackfiveservices.co.uk/separate.shtml`), which fakes CMYK conversion using layer-based channel separation and an ICC profile (conversion performed via littlecms), then export through that plugin's CMYK TIFF/JPEG path — or, more reliably, do the final RGB→CMYK conversion in a tool with native CMYK support (Photoshop, or a dedicated prepress tool) after finishing all text/effects work in GIMP. Community reports flag that Separate+ conversions can shift color noticeably from ICC-profile-based conversions done in Photoshop — proof the final CMYK file against IngramSpark's own file checker before submission rather than trusting the plugin's output blind.
- **eBook cover export:** GIMP handles this natively without complication — File → Export As → JPEG (or PNG, though KDP does not accept PNG for its cover upload) at the platform's target pixel dimensions from `cover-specs.md`. Set **Image → Print Size** or check **Image → Image Properties** to confirm the pixel dimensions match the platform target before export; GIMP's DPI metadata field is cosmetic for on-screen eBook covers (only pixel dimensions matter for e-reader/retail thumbnail pipelines) but should still be set to 300 if you're using the same working file to also produce a print asset.
- **Print cover export (with the above CMYK caveat):** target 300 DPI at the platform's trim size, add 0.125" bleed by working on an oversized canvas (trim size + 0.25" total, 0.125" per outer edge) and using GIMP's guides (Image → Guides → New Guide) to mark the trim and safe-text lines before placing text, matching IngramSpark's ≥0.25" text-safety margin from trim.
- **File format for GIMP's export:** JPEG for eBook delivery (Export As, quality ~90–95 to avoid visible compression artifacts around fine text edges — text edges show JPEG ringing more visibly than photographic content, so don't use GIMP's lower quality presets on cover text composites). For print, export as flattened TIFF or, via a CMYK plugin/second tool, PDF — GIMP's native PDF export does not itself perform RGB→CMYK conversion.

## Sources

- [Chapter 9. Text Management — GIMP 3.0 docs](https://docs.gimp.org/3.0/en/gimp-image-text-management.html)
- [Text-Handling in GIMP — GIMP GUI Redesign wiki](https://gui.gimp.org/index.php?title=Text-Handling_in_GIMP)
- [6.8. Drop Shadow — GIMP 3.0 docs](https://docs.gimp.org/3.0/en/gimp-filter-drop-shadow.html)
- [6.7. Drop Shadow — GIMP 2.10 docs](https://docs.gimp.org/2.10/en/gimp-filter-drop-shadow.html)
- [6.14. Bevel — GIMP 3.2 docs](https://docs.gimp.org/3.2/en/gegl-bevel.html)
- [CMYK Separation Plugin for The GIMP — Black Five Services](https://www.blackfiveservices.co.uk/separate.shtml)
- [GSoC 2022 project announced: CMYK features — GIMP.org](https://www.gimp.org/news/2022/06/03/cmyk-in-gsoc-2022/)
- [GIMP/CMYK support — ArchWiki](https://wiki.archlinux.org/title/GIMP/CMYK_support)
- [IngramSpark File Creation Guide (official PDF)](https://myaccount.ingramspark.com/documents/IngramSpark%20File%20Creation%20Guide.pdf)
