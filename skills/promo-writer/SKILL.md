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
- Load book data via MCP `get_book_full()`
- Read `{project}/synopsis.md` for pitch material
- Load author profile via MCP `get_author()` — promo voice should match author brand
- Load genre README(s) — genre audiences have different platform habits
- Read `{project}/characters/INDEX.md` for character-driven content
- Read `{plugin_root}/reference/promo/platforms.md` — platform characteristics and content-type templates

## Workflow

### Step 1: Write the Blurb

The book blurb is the single most important marketing text — it must exist before any platform content is written. Do this first, always.

**Load:**
- `{project}/synopsis.md` — Short Synopsis section is the raw material
- Genre README(s) — tone guidance for the blurb voice

**Walk through the 5-element structure:**

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

**Target:** 150–200 words. Rigorously edited. No spoilers. No ending revealed.

**Output:** Save to `{project}/export/blurb.md` using `templates/blurb.md` as scaffold.

**Gate:** Ask the user to approve the blurb before proceeding. If rejected, revise until approved.

---

### Step 2: Campaign Strategy
Ask the user:
- **Phase:** Pre-launch (teasers), Launch (announcement), Post-launch (sustained)
- **Platforms:** Which ones? (or all)
- **Tone:** Match author brand or separate marketing voice?
- **Content types wanted:** (use AskUserQuestion, multiSelect)
  - Teaser/Hook posts
  - Character introductions
  - Behind-the-scenes (writing process)
  - Quote cards (compelling lines from the book)
  - Launch announcement
  - Review/testimonial templates
  - Series announcement
  - Giveaway posts

### Step 3: Generate Platform-Specific Content

Create `{project}/promo/` directory with per-platform files.

For each selected platform, apply the characteristics and content-type templates
from `reference/promo/platforms.md` (loaded in Prerequisites).
Generate native content — never cross-post identical text across platforms.

**Output files:** `{project}/promo/{platform}.md`
Available platforms: `facebook.md`, `instagram.md`, `twitter.md`, `tiktok.md`, `bluesky.md`, `newsletter.md`

---

### Step 4: Quote Cards
Extract 5-10 compelling quotes from the book for visual content:
- **Criteria:** Punchy, evocative, standalone (no context needed)
- **Length:** 1-3 sentences max
- **Types:** Dialog zingers, atmospheric descriptions, thematic statements
- **Format:** Quote + character attribution + book title

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
- NEVER spoil the ending or major twists
- Promo voice should feel AUTHENTIC, not salesy — especially on TikTok/BookTok
- Each platform gets NATIVE content — don't cross-post identical text
- Emotional hooks > plot summaries. Readers buy FEELINGS, not summaries.
- Every post needs a clear CTA (call to action) — but make it natural
- Quote cards must be genuinely compelling lines, not random passages
- Hashtags: research current trending ones, don't guess
- For series: emphasize "start here" — make entry point clear
