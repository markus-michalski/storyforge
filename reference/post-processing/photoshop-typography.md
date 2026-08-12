---
tool: photoshop
craft_topic: cover-typography
status: stable
last_reviewed: 2026-08-12
---

# Photoshop: Cover Typography Reference

Reference for compositing title/author text onto a pre-generated cover image (no text baked in) in Adobe Photoshop. Not a tutorial — assumes you can open the Character panel and Layers panel.

## Letter-Spacing (Tracking) and Kerning

Photoshop measures **tracking** and **kerning** in **1/1000 em**, relative to the current point size (Adobe help docs, `helpx.adobe.com/photoshop/using/line-character-spacing.html`). This is the baseline unit every other tool in this reference set gets compared against.

- 1 em = the current font size. At 100pt type, 1000/1000 em = 100pt of extra space; 20/1000 em ≈ 2pt.
- Positive values open up the text; negative values tighten it. 0 is font-default spacing.
- Default UI increment when clicking the up/down arrows in the Character panel is 20/1000 em (community-reported; Adobe hasn't documented an official override for this default in current versions).
- Set tracking via Character panel → **VA▸** field, or Type menu. Selecting a text range applies tracking to that range only; clicking between two letters with nothing selected sets **kerning** for that single pair instead.

**Kerning modes** (Character panel dropdown):
- **Metrics** — uses the font's built-in kerning pairs (default, usually correct for display faces).
- **Optical** — Photoshop calculates spacing based on glyph shapes; use for typefaces with weak/no kern pairs or mixed scripts.
- **Manual** — a numeric override entered with the cursor between two specific characters.

### Cross-tool conversion — what's actually verifiable

Photoshop's 1/1000-em tracking scale is the one hard, documented number in this whole comparison. GIMP's letter-spacing is in raw pixels added between glyphs (tool-dependent on point size and canvas resolution — no fixed ratio to em). Canva's "Letter Spacing" slider is a proprietary 0–100(ish) UI value with **no published unit or conversion formula** — Canva's own help center and marketing blogs describe it only as "drag right to increase, left to decrease," and no forum thread, Adobe Community post, or design-blog benchmark we could find publishes a verified Canva-value → Photoshop-1/1000-em ratio. Treat any specific multiplier you see quoted online (e.g. "Canva's slider is roughly Photoshop tracking ÷ 20") as unverified folklore, not a spec.

**Practical implication:** don't try to numerically port a tracking value between Photoshop and Canva. Set the value in Photoshop, export a flattened reference PNG at final size, and eyeball-match the Canva version against it side by side — especially at the thumbnail size from `cover-specs.md` (title must read at ~160×256px). GIMP's px-based spacing needs the same visual re-match, not a formula.

## Font-Pairing Workflow

Photoshop has no built-in font-pairing suggestion engine (unlike Adobe Express or Canva). Workflow:

1. **Font preview in the Character panel / Options bar dropdown**: hover a font name to live-preview it applied to the selected text layer. Filter by classification (Serif, Sans Serif, Slab, Script, etc.) using the panel's category filter icons — useful for narrowing to genre-appropriate faces per `cover-specs.md`'s per-genre font guidance (e.g. filter to Serif for Fantasy, Sans for Thriller).
2. **Adobe Fonts** (bundled with a Creative Cloud subscription) activates directly from the font dropdown — search, filter by classification/weight/width, and Photoshop syncs the font locally without leaving the app.
3. No pairing suggestions ship in-app. Authors doing genre-appropriate title/author pairing manually should decide the pairing *before* opening Photoshop (e.g. using a font-pairing reference site or Canva's suggestion panel) and just apply the two chosen fonts to the title and author text layers here.
4. Keep title and author on **separate text layers** (not separate lines in one layer) — this is required for independent tracking, layer styles, and blend-mode control per element.

## Layer Styles for Cover Text

Access via **Layer → Layer Style**, or double-click the text layer in the Layers panel. All effects here are non-destructive and stay live-editable as long as the layer remains a text layer.

| Effect | Purpose on a cover | Key controls |
|---|---|---|
| **Drop Shadow** | Separates title text from a busy/similarly-toned background image | Blend mode (usually Multiply), Opacity, Angle (match the art's implied light source), Distance, Spread, Size |
| **Outer Glow** | Rim-light effect; also doubles as a poor-man's "halo" for light text on light backgrounds | Blend mode (Screen for a glow look), Opacity, Noise, color/gradient, Spread, Size |
| **Stroke** | Hard outline — the single most reliable fix for text sitting on a variable-tone background, and the technique this repo's cover guidance already flags for e-ink/grayscale legibility (`feedback_ebook_cover_bw_legibility` in project memory: use an outline, not just color contrast) | Size, Position (Outside recommended so the stroke doesn't eat into thin letterforms), Blend Mode, Color |
| **Bevel & Emboss** | 3D/embossed title treatment (common on fantasy/thriller covers) | Style (Inner Bevel / Outer Bevel / Emboss), Depth, Direction (Up/Down), Size, Soften, plus nested **Contour** and **Texture** sub-effects |
| **Gradient Overlay / Color Overlay** | Metallic or two-tone title fills | Blend mode, gradient stops, angle/scale |

**Layer Style workflow for legibility on grayscale devices** (ties directly to the e-ink gotcha already tracked in this project): stack **Stroke** (outside, dark, 2–4px at full-res proportions) underneath a **Drop Shadow** at low opacity. Verify by temporarily desaturating a flattened copy (Image → Adjustments → Desaturate) and checking the title still reads — this simulates Kindle/Kobo e-ink rendering before you export.

Save a configured style as a **Style preset** (Styles panel → New Style) once dialed in, so title and author layers — or an entire series' worth of covers — reuse identical settings.

## Export / Resolution Settings

Two very different targets, do not conflate them:

### Print cover (KDP paperback/hardcover, IngramSpark)
- **Resolution:** 300 DPI minimum, non-negotiable for both platforms.
- **Color mode:** IngramSpark requires **CMYK** in the delivered file, PDF/X-1a:2001 or PDF/X-3:2002 compliant, all images CMYK, ≤240% total ink, rich black at 60/40/40/100 C/M/Y/K if used (IngramSpark File Creation Guide). KDP nominally accepts RGB **or** CMYK for print, but converts RGB to CMYK at print time using a generic ICC profile — bright, saturated RGB colors can shift. Safer to design/flatten to CMYK yourself if targeting print, matching IngramSpark's requirement and avoiding surprise KDP conversion shifts.
- Convert in Photoshop: **Image → Mode → CMYK Color**, ideally *after* finishing text/effects work (some layer-style blend modes render differently in CMYK — flatten and proof after conversion, don't design blind in CMYK from the start unless the source cover art was already delivered CMYK).
- **Bleed:** 0.125" (3.2mm) on all outer edges for both platforms; keep live text ≥0.25" from trim edge.
- **File format:** PDF (flattened, layers merged) is preferred by both platforms; PSD/JPEG/PNG accepted by KDP as fallback but PDF minimizes rasterization surprises.

### eBook cover (KDP, Apple Books, Kobo, Draft2Digital, Smashwords)
- **Resolution:** no DPI requirement in the technical sense — these are screen-viewed pixel dimensions, not print. Use the platform's pixel target from `cover-specs.md` (e.g. KDP 1600×2560px minimum per that file) — check current platform docs before finalizing regardless, dimension guidance drifts over time.
- **Color mode:** **RGB (sRGB)** — do not deliver CMYK for eBook covers; e-readers and retail thumbnail pipelines expect RGB and will render CMYK incorrectly or reject it.
- **File format:** platform requirements drift as fast as dimensions do — as of this writing, secondary sources (not KDP's own help center) report KDP requiring JPEG for eBook covers and rejecting PNG, with TIFF also accepted for the cover upload specifically; Draft2Digital's knowledge base documents JPEG (recommended) or PNG. **Verify current accepted formats against each platform's own upload page before export** rather than trusting this list blind.
- Export via **File → Export → Export As** (JPEG, quality 90+) or **Save As** for TIFF — not "Save for Web," which applies extra compression/color profile stripping unsuited to full-resolution cover delivery.

### Practical two-file workflow
Composite text once on the pre-generated art in RGB at the largest target size (the "universal safe size" 2560×3840px @300DPI referenced in `cover-specs.md`), verify legibility at thumbnail size, then branch: export an RGB JPEG for eBook platforms, and separately convert-and-flatten a CMYK PDF/X for print — don't try to make one exported file serve both pipelines.

## Sources

- [Line and character spacing in Adobe Photoshop (official docs)](https://helpx.adobe.com/photoshop/using/line-character-spacing.html)
- [Tracking in Photoshop — Adobe Community discussion](https://community.adobe.com/t5/photoshop/tracking-in-photoshop/td-p/10790983)
- [Bevel and Emboss in Photoshop: A Complete Guide](https://design.tutsplus.com/articles/the-comprehensive-guide-to-bevel-and-emboss--psd-17308)
- [How to Master Layer Styles in Photoshop – PHLEARN](https://phlearn.com/tutorial/layer-styles-photoshop/)
- [10 Useful Layer Style Text Effects — Envato Tuts+](https://design.tutsplus.com/tutorials/10-useful-layer-style-text-effects--cms-29372)
- [Amazon KDP Book Cover Requirements 2026 — BookClad](https://bookclad.com/blog/amazon-kdp-cover-requirements-2026)
- [RGB or CMYK for KDP Covers? — Veritas Canvas](https://www.veritascanvas.com/kdp-cover-rgb-or-cmyk.html)
- [IngramSpark File Creation Guide (official PDF)](https://myaccount.ingramspark.com/documents/IngramSpark%20File%20Creation%20Guide.pdf)
- [IngramSpark Requirements — File Specs & Submission Guide](https://cambric.pub/guides/ingramspark-requirements/)
- [Draft2Digital Knowledge Base](https://draft2digital.com/knowledge-base/)
