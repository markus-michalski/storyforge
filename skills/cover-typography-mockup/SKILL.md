---
name: cover-typography-mockup
description: |
  Generate an HTML mockup Artifact for compositing title/author typography onto an
  already-generated cover image (cover-artist deliberately generates "no text on the
  image" — this fills that post-processing gap). Branches its guidance on the
  configured post_processing.tool (canva, gimp, photoshop).
  Use when: (1) User says "Cover-Typografie", "Cover typography", "Typography mockup",
  "Titel-Schriftzug", "Titel aufs Cover", (2) A final cover image has already been
  imported via import_cover_image and the author needs to add title/author text.
model: claude-opus-5
user-invocable: true
argument-hint: "<book-slug>"
---

# Cover Typography Mockup

Produces a visual reference — not a final deliverable — for adding title/author
typography on top of a pre-generated, text-free cover image. The author recreates
the mockup manually in their own tool (Canva, GIMP, or Photoshop); this skill never
edits the actual cover image file.

## Step 1: Context

- `get_book_full(book_slug)` — title, genre(s), `book_category`, `author` slug
- `get_author(author_slug)` — author's display `name`
- `get_cover_image(book_slug)` — the final cover image. **Stop and tell the user to
  run `/storyforge:cover-artist` + `import_cover_image(is_final=True)` first** if
  `cover_image_path` is null — there's nothing to composite text onto yet. Surface any
  `warning` the tool returns (untracked/ambiguous cover) before proceeding rather than
  silently picking a guess.
- `get_post_processing_config()` — the configured `tool` (`canva` | `gimp` | `photoshop`,
  always one of the three — the tool itself falls back to `canva` for an unrecognized
  config value). Surface any `warning` it returns (a typo'd `post_processing.tool`) to
  the user instead of silently switching tools on them.
- Read `{plugin_root}/reference/export/cover-specs.md` for genre font conventions and
  platform pixel targets
- Read `{plugin_root}/reference/post-processing/{tool}-typography.md` (matching the
  configured tool exactly — never load or mix in guidance from a different tool's file).
  This file is the actual payload of the tool-specific sections below; if it fails to
  load, stop and report the path rather than falling back to generic advice while still
  claiming tool-specific guidance.

## Step 2: Typography Brief

Ask via AskUserQuestion (keep this short — defaults come from Step 1's data):

- **Title text** — default: book title
- **Author display name** — default: author profile `name`
- **Series name** (if part of a series) — shown above the title, smaller
- **Tagline** (optional) — max ~8 words, per `cover-specs.md`
- **Placement** — top third / bottom third / centered (rule of thirds guidance already
  in `cover-specs.md`)
- **Target platform** — eBook, print, or both — the export/resolution section (Step 3)
  and the canvas-size instruction (Step 3) both depend on this; don't assume
- **Effect accent** — beyond the mandatory legibility outline (see Step 3), does the
  author also want a shadow, glow, or (fiction fantasy/thriller only) bevel/emboss
  treatment? Offer only the effects the configured tool actually supports per the
  loaded reference file — e.g. never offer bevel/emboss if `tool == "canva"`, it has no
  equivalent.

Pick title/author font pairing from `cover-specs.md`'s genre table as the default,
confirm or let the user override. Write a one-paragraph rationale tying the chosen
placement/color/effect back to the book's actual cover brief (`cover/brief.md`, if the
book has one) and the genre's typography conventions — this becomes the "why" section
in Step 3, not boilerplate.

## Step 3: Build the Mockup

Structure, in this order — a two-column layout (sticky scaled preview left, spec
sections right; single column on narrow viewports):

1. **Prepare the preview image.** Downscale the cover image before encoding — a mockup
   is a hierarchy/spacing reference (Step 5 says so explicitly), not a pixel-perfect
   export, so it never needs full print resolution. Resize to a **~1200px longest
   edge**, then base64-encode with a portable method (a short Python snippet via the
   plugin venv, e.g. `Pillow` if available, or `base64.b64encode` on the resized bytes —
   not a bare `base64 -w0` shell call, its `-w` flag is GNU-coreutils-only and breaks on
   macOS/BSD/Windows). Embed as a `data:` URI background — no external image loads, the
   Artifact tool's CSP blocks them anyway. Keep the final HTML file comfortably under
   the Artifact tool's 16 MB cap; a 1200px-edge JPEG at reasonable quality is a low
   single-digit MB even base64-inflated.
2. **Framed preview column**, sticky-positioned: the cover image at its real aspect
   ratio, a subtle top/bottom scrim gradient for text legibility over busy art (not a
   substitute for the outline rule below), and the title/series/author lines
   absolutely positioned as **percentages of image height** — not fixed pixels — so the
   position numbers in the spec table (next) and the visual preview always agree with
   each other. A one-line caption under the frame states these are scale-accurate
   positions the author can transfer 1:1 into {tool}, and that the preview font is a
   system-font approximation, not the actual chosen typeface.
3. **"Text Elements" table** (Element / Text / Font in {tool} / Size as % of image
   height / Color with a visible swatch / Position as % from top or bottom) — one row
   per title/series/author/tagline line actually used. This table and the preview
   frame's inline positioning **must use the same numbers** — generate them together,
   not independently.
4. **"Why This Placement" section** — the rationale paragraph from Step 2, in prose,
   not a bullet list. Explain the placement/color/effect choices against the book's own
   cover brief and genre conventions, the way a human designer would justify a layout
   decision, not a generic "titles are usually centered" filler.
5. **"Step by Step in {Tool}" numbered list** — concrete, transcribed from the loaded
   `{tool}-typography.md`: canvas size for the *actual* target platform chosen in Step
   2 (not a generic default), exact menu paths for the font-pairing workflow and the
   chosen effect(s) in the order they need to be applied (effect order matters — e.g. a
   glow added before a shadow reads differently than the reverse; the tool reference
   file's own effect table covers this), and the export format/settings for the chosen
   platform.
6. **"Platform Specs" grid** — pixel dimensions pulled from `cover-specs.md` (and the
   book's own `cover/prompts.md` if it exists) for whichever platform(s) the book
   targets, plus the export/resolution settings (DPI, RGB vs. CMYK, file format) from
   the loaded `{tool}-typography.md` for that same platform. **This is where the
   ≥0.25" print text-safety margin lives (from `{tool}-typography.md`'s IngramSpark
   citation, not `cover-specs.md` — that file has no bleed/margin spec) if the target
   includes print** — call it out explicitly rather than folding it silently into the
   preview frame's scrim.
7. **Footer** citing the actual source files read in Step 1 (`cover/brief.md`,
   `cover/prompts.md` if present) and the real source image's resolution/aspect ratio,
   so the mockup stays traceable to what generated it.

Throughout:
- **Always include a hard outline/stroke on the text**, not shadow-only — this
  project's existing grayscale/e-ink legibility rule (outline survives low-bit-depth
  rendering, a soft shadow can wash out) applies regardless of which extra effect
  the user picked in Step 2.
- Show the letter-spacing value used in the CSS mockup (`letter-spacing: Npx` or
  `Nem`) with an explicit callout that this value **does not port 1:1** to the
  configured tool — point at the "Working method" section of the loaded reference
  file instead of implying a formula exists.
- Before writing any HTML, load the `artifact-design` skill — this is a genuine visual
  deliverable, not a throwaway diagnostic page, so it earns real design attention
  (page chrome, typography, light/dark tokens) around the preview frame.

## Step 4: Save + Publish

- Write the HTML to `{project}/cover/cover-typography-mockup.html` (Write tool)
- Publish it with the Artifact tool from that same file path — pick a stable favicon
  emoji and a concise title/description; this is a redeployable reference, not a
  one-off, so re-run Step 3–4 (same file path) rather than creating a new artifact
  if the author asks for a revision. **If the Artifact tool isn't available in the
  current session, skip publishing and just hand the author the saved file path** —
  it's a complete, self-contained HTML file either way and opens fine in any browser.
- Present the artifact link (if published) plus the saved file path to the user

## Step 5: Next Steps

Tell the author: recreate the layout manually in {tool} using the sidebar
instructions and the full reference file for exact settings — the mockup is a
hierarchy/spacing/effect reference, not a pixel-perfect export. Once they have the
final composited image, `import_cover_image(book_slug, source_path, is_final=True)`
records it as the version `export-engineer` uses — this replaces the earlier
text-free draft as "the" cover.

## Rules

- Never treat the HTML mockup as a final deliverable, and say so in the mockup itself
- Branch every tool-specific instruction strictly on the configured
  `post_processing.tool` — never blend guidance from more than one reference file
- Never claim or imply a verified numeric conversion between tools' letter-spacing
  scales exists — the loaded reference files are explicit about what is and isn't
  documented; preserve that honesty in the mockup's own copy, don't round it off into
  false precision
- Keep the mockup fully self-contained (inline CSS, embedded image as a `data:` URI) —
  no external asset loads
- The preview frame's text positions and the Text Elements table's position column
  must always describe the same layout — never let them drift apart
- Memoir books: if the brief's cover approach is Typographic (no photo), the "cover
  image" from Step 1 may itself be minimal/textured background art — the same
  workflow still applies, just with more visual weight on the typography itself
