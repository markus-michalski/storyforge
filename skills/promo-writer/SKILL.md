---
name: promo-writer
description: |
  Create social media promotional content for books across all platforms.
  Use when: (1) User says "Promo", "Social Media", "Marketing", "bewerben",
  (2) Book is near completion or published, (3) User wants teasers, announcements, or campaigns.
model: claude-opus-4-6
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

---

#### Facebook (`{project}/promo/facebook.md`)

**Characteristics:**
- Longer text OK (up to 500 words performs well)
- Storytelling format works best
- Questions drive engagement
- Link posts get lower reach — use text + image instead
- Groups are gold for book promotion

**Content types:**
```markdown
## Launch Announcement
[Longer, personal story about the book + purchase link]

## Teaser Post (Pre-Launch)
[Hook from Chapter 1 + "Coming [date]"]

## Character Spotlight
[Character intro as if they were a real person — fun, intriguing]

## Behind the Scenes
[Writing process insight — relatable, human]

## Reader Question
[Engaging question related to book's theme — drives comments]

## Quote Card Caption
[Compelling quote from book + brief context]
```

---

#### Instagram (`{project}/promo/instagram.md`)

**Characteristics:**
- Visual-first platform — every post needs an image concept
- Carousel posts (multiple slides) get highest engagement
- Reels for short video content
- Hashtags: 5-15 relevant ones, mix of broad + niche
- Stories for behind-the-scenes, polls, countdowns
- Bio link is the ONLY clickable link

**Content types:**
```markdown
## Feed Post — Launch
Caption: [150-200 words, personal, with CTA]
Image concept: [Cover reveal, aesthetic flat lay, mood board]
Hashtags: #bookstagram #newrelease #[genre]books #[genre]fiction
  #booklover #readersofinstagram #bookish #authorsofinstagram
  #[specific-hashtags]

## Carousel — Character Profiles
Slide 1: [Character name + striking visual description]
Slide 2-5: [One fact per slide — quirk, flaw, secret, quote]
Slide 6: [Book title + "Meet them in [Title]"]

## Reel Concept — Book Teaser
[15-30 second concept: text overlay on atmospheric video/images]
Hook: [First 3 seconds must grab — opening line or question]
Audio: [Trending sound suggestion or atmospheric music]

## Story Series — Countdown
Day 7: [Theme/mood reveal]
Day 5: [Character tease]
Day 3: [First chapter hook]
Day 1: [IT'S HERE + link]
```

---

#### X / Twitter (`{project}/promo/twitter.md`)

**Characteristics:**
- 280 characters max (threads for longer content)
- Threads perform well for storytelling
- Wit and voice matter more than anywhere else
- Quote tweets for engagement
- Timing matters: post when audience is active

**Content types:**
```markdown
## Launch Tweet
[Under 280 chars. Punchy. Link. Done.]

## Thread — The Story Behind the Story
Tweet 1: [Hook — why you wrote this book]
Tweet 2-5: [Key moments in the writing journey]
Tweet 6: [The book pitch + link]

## Teaser Thread — Opening Lines
Tweet 1: "The first line of my new book:"
Tweet 2: [Actual first line — must be a BANGER]
Tweet 3: [Reaction bait — "Would you keep reading?"]

## Character in 280 Chars
[Describe your protagonist in one tweet — voice, flaw, hook]

## Quote Tweet Template
"[Compelling quote from the book]"
— [Character Name], [Book Title]
```

---

#### TikTok (`{project}/promo/tiktok.md`)

**Characteristics:**
- #BookTok is MASSIVE — 200B+ views
- Authentic > polished (don't look like an ad)
- Emotion sells (cry, laugh, rage, shock)
- Trending sounds + formats boost reach
- 15-60 seconds sweet spot
- Hook in first 2 seconds or they scroll

**Content types:**
```markdown
## BookTok Pitch
Format: Face-to-camera or text overlay on aesthetic background
Hook: "If you like [comp title], you NEED this book"
Script: [15-second pitch — genre, vibe, emotional hook, NOT a summary]
CTA: "Link in bio" or "Comment [emoji] if you want to read this"

## Trope Check
Format: Text overlay with book cover
"Books with [trope] that will DESTROY you"
[List 2-3 popular books + yours]

## POV Video
"POV: You're [character] and [dramatic situation from book]"
[Atmospheric, moody, short — let viewers imagine]

## Emotional Hook
"The book that made me [cry/scream/throw my phone]"
[React to your own most emotional scene — genuine reaction]

## First Chapter Read
[Read the opening paragraph — compelling voice, atmospheric setting]
[Text overlay: "Should I post more?"]
```

---

#### Bluesky (`{project}/promo/bluesky.md`)

**Characteristics:**
- Growing literary community
- 300 character limit
- Thread-friendly
- Less algorithm-driven — chronological feeds
- Author community is active and supportive

**Content types:**
```markdown
## Launch Post
[Concise announcement + cover image + link]

## Writing Process Thread
[Authentic insights about the creative process]

## Character Introduction
[Brief, intriguing intro — like a dating profile for your character]
```

---

#### Newsletter / Email (`{project}/promo/newsletter.md`)

**Characteristics:**
- Highest conversion rate of any channel
- Personal, intimate tone
- Longer content OK (500-1000 words)
- Include exclusive content (deleted scene, character backstory)
- Clear CTA (one per email)

**Content types:**
```markdown
## Pre-Launch Email
Subject: [Curiosity-driven subject line]
Body: [Personal story + cover reveal + pre-order link]

## Launch Day Email
Subject: [IT'S HERE / Publication day subject]
Body: [Excitement + what the book is about + buy links + ask for review]

## Post-Launch Follow-Up
Subject: [Thank you + bonus content]
Body: [Deleted scene or character backstory + review request]
```

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
