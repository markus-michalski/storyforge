---
name: promo-writer
description: |
  Create social media promotional content for books across all platforms.
  Use when: (1) User says "Promo", "Social Media", "Marketing", "bewerben",
  (2) Book is near completion or published, (3) User wants teasers, announcements, or campaigns.
model: claude-opus-4-7
user-invocable: true
argument-hint: "<book-slug> [platform]"
---

# Promo Writer — Social Media Content Creator

## Prerequisites
- Load book data via MCP `get_book_full()` — read `book_category`
- Read `{project}/synopsis.md` for pitch material
- Load author profile via MCP `get_author()` — promo voice should match author brand
- Load genre README(s) — genre audiences have different platform habits
- **Fiction:** Read `{project}/characters/INDEX.md` for character-driven content
- **Memoir:** Read `{project}/people/INDEX.md` (or `{project}/characters/INDEX.md` for legacy projects) — use real names as they appear in the memoir (or their anonymization aliases)
- Read `{plugin_root}/reference/promo/platforms.md` — platform characteristics and content-type templates

## Workflow

### Step 1: Write the Blurb

The book blurb is the single most important marketing text — it must exist before any platform content is written. Do this first, always.

**Load:**
- `{project}/synopsis.md` — Short Synopsis section is the raw material
- Genre README(s) — tone guidance for the blurb voice

Branch the blurb structure on `book_category`:

---

**Fiction blurb — 5-element structure:**

1. **Hook** — Opening line that captures the core premise. One sentence, written to grab a skimming reader.
2. **Character Introduction** — Protagonist name + one defining characteristic. Enough to care, nothing more.
3. **Conflict & Stakes** — What's at stake and what happens if they fail. The "or else" that creates urgency.
4. **Tone Alignment** — Verify the blurb voice matches genre expectations:
   - Thriller: tension, urgency, menace
   - Romance: warmth, anticipation, emotional pull
   - Horror: dread, wrongness, the unknown
   - Fantasy: wonder, scale, stakes
   - Literary Fiction: interiority, ambiguity, weight
5. **Comp Titles** (optional) — "_X_ meets _Y_" format. Only include if the comparison is strong and both titles are recognizable.

---

**Memoir blurb — 4-element structure:**

Memoir blurbs sell a specific kind of trust: *this person lived through something, and they're going to tell you the truth about it.* The reader doesn't buy plot — they buy the author's voice and the promise of resonance.

1. **Hook** — The most dramatic moment, the sharpest image, or the most distinctive angle of the memoir. One sentence that makes the reader think "I need to know more." Often drawn from a vivid scene rather than a thematic statement.
2. **Personal Stake** — Why did THIS author have to write THIS story? The "why me, why now" that earns the reader's trust. What the author had to lose by not telling it.
3. **Universal Theme** — The thing the reader will recognize from their own life. Not a lesson ("I learned that...") but a shared human experience ("For anyone who has ever..."). This is what moves memoir from personal to universal.
4. **Tone Signal** — A closing phrase or sentence that sets the emotional register:
   - Intimate and confessional: warm, direct, the author speaking to you personally
   - Investigative/reckoning: measured, unsettling, questions that don't resolve neatly
   - Defiant/reclaimed: energy, agency, transformation
   - Elegiac/grief memoir: weight, tenderness, acceptance
5. **Comp Titles** (optional) — Comp *memoirs*, not novels. e.g., "Readers of Tara Westover's *Educated* and Carmen Maria Machado's *In the Dream House* will recognize this voice." Only use comps you can defend.

**Memoir blurb rules:**
- Never call the book "a journey" or "a powerful story." These are death-blurb words.
- Never use "lessons learned" framing — that promises therapeutic tidiness the best memoir avoids.
- Keep the author's name in the blurb — memoir is the author, not a protagonist.
- Do NOT reveal how the story ends. But unlike fiction, the resolution is usually known (the author survived, recovered, left) — the blurb's tension is about the reader's resonance, not plot mystery.

---

**Target for both modes:** 150–200 words. Rigorously edited.

**Output:** Save to `{project}/export/blurb.md` using `templates/blurb.md` as scaffold.

**Gate (HARD):** Blurb approval is a hard gate. Step 2 (Campaign Strategy) requires explicit user sign-off on the blurb. Wait for explicit approval — implicit "looks fine" does not count. If rejected, revise and re-present until the user types approval.

---

### Step 2: Campaign Strategy
Ask the user:
- **Phase:** Pre-launch (teasers), Launch (announcement), Post-launch (sustained)
- **Platforms:** Which ones? (or all)
- **Tone:** Match author brand or separate marketing voice?
- **Content types wanted:** (use AskUserQuestion, multiSelect)

**Fiction content types:**
  - Teaser/Hook posts
  - Character introductions
  - Behind-the-scenes (writing process)
  - Quote cards (compelling lines from the book)
  - Launch announcement
  - Review/testimonial templates
  - Series announcement
  - Giveaway posts

**Memoir content types (replace/supplement):**
  - "True story" hook posts (the inciting moment, the most arresting scene)
  - Author voice posts (the author speaking directly — not "meet the protagonist")
  - Behind-the-memoir posts (why they wrote it, what it cost to write)
  - Quote cards (memoir quotes land differently — first-person, raw)
  - "You're not alone" resonance posts (universal theme framing)
  - Launch announcement
  - Review/testimonial templates (especially for readers who share similar experiences)

### Step 3: Generate Platform-Specific Content

Create `{project}/promo/` directory with per-platform files.

For each selected platform, apply the characteristics and content-type templates
from `reference/promo/platforms.md` (loaded in Prerequisites).
Generate native content — never cross-post identical text across platforms.

**Output files:** `{project}/promo/{platform}.md`
Available platforms: `facebook.md`, `instagram.md`, `twitter.md`, `tiktok.md`, `bluesky.md`, `newsletter.md`

---

### Step 4: Quote Cards
Extract 5-10 compelling quotes from the book for visual content.

**Fiction:**
- **Criteria:** Punchy, evocative, standalone (no context needed)
- **Length:** 1-3 sentences max
- **Types:** Dialog zingers, atmospheric descriptions, thematic statements
- **Format:** Quote + character attribution + book title

**Memoir:**
- **Criteria:** Raw, honest, resonant — the sentences readers will screenshot and share
- **Length:** 1-3 sentences. Fragments work well in memoir.
- **Types:** First-person observations, moments of reckoning, the precise image that captures everything
- **Format:** Quote + book title (no character attribution — the author is the narrator)
- **Avoid:** Therapeutic wisdom quotes ("I learned that..."), inspirational-poster phrasing — memoir quote cards win on specificity and honesty, not uplift.

Write to `{project}/promo/quotes.md`.

### Step 5: Hashtag Strategy
Research and compile genre-specific hashtags:
- **Broad:** #bookstagram, #booktok, #readersofinstagram, #bookish
- **Genre:** #horrorbooks, #fantasyreads, #romancebooks, etc.
- **Trope:** #enemiestoloverss, #foundFamily, #vampirefiction, etc.
- **Community:** #indieauthor, #writerscommunity, #amreading
- **Book-specific:** Create a unique hashtag for the book/series

Write to `{project}/promo/hashtags.md`.

### Step 6: Content Calendar
Suggest a posting schedule:

| Day | Platform | Content Type |
|-----|----------|-------------|
| -14 | Instagram | Cover reveal carousel |
| -10 | TikTok | BookTok pitch |
| -7 | All | Countdown begins |
| -3 | Twitter | First line thread |
| -1 | Newsletter | Pre-launch email |
| 0 | ALL | Launch day blitz |
| +1 | Instagram | Character spotlight |
| +3 | TikTok | Emotional hook |
| +7 | Facebook | Behind the scenes |
| +14 | All | Review roundup |

Write to `{project}/promo/calendar.md`.

## Rules
- Keep endings and major twists out of all promo. Spoilers kill conversion.
- Promo voice should feel AUTHENTIC, not salesy — especially on TikTok/BookTok.
- Each platform gets NATIVE content — write per-platform, not cross-post.
- Emotional hooks > plot summaries. Readers buy FEELINGS, not summaries.
- Every post needs a clear CTA (call to action) — keep it natural, not pushy.
- Quote cards must be genuinely compelling lines, not random passages.
- Hashtags: research current trending ones — guessed hashtags read as inauthentic.
- For series: emphasize "start here" — make the entry point unambiguous.
