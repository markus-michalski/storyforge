---
name: beta-promo-writer
description: |
  Create book-tailored recruitment content for finding beta readers and ARC
  reviewers across platforms (Reddit, Goodreads, StoryGraph, TikTok/BookTok,
  Facebook, Bluesky, Newsletter), plus StoryOrigin campaign setup guidance
  (screening questions, feedback-form questions).
  Use when: (1) User says "Beta-Leser gewinnen", "ARC-Team aufbauen", "Beta
  Promo", "Beta reader recruitment", "StoryOrigin Kampagne", (2) Book status
  is Revision or later and the author wants to recruit readers BEFORE
  distributing an ARC/beta copy, (3) NOT for processing feedback that
  already came back — that's `/storyforge:beta-feedback`.
model: claude-opus-5
user-invocable: true
argument-hint: "<book-slug> [platform]"
---

# Beta Promo Writer — Beta Reader & ARC Recruitment Content

This is the **recruitment** step: getting readers to sign up, before any file goes
out. It sits upstream of `/storyforge:export-engineer --arc` (produces the
downloadable ARC file, if needed) and `/storyforge:beta-feedback` (processes
feedback that already came back). See **StoryOrigin Modes** below for which of
those two downstream steps actually applies to a given campaign.

## Prerequisites
- Load book data via MCP `get_book_full(book_slug)` — read `book_category`, `status`, and
  `series`. Reuse this same result in Step 0 — don't call it again.
  **Why:** `book_category` gates the feedback-question set (fiction vs. memoir); `status`
  tells you whether recruitment is premature (see Step 0); `series` (the series slug, or
  empty string `""` for a standalone book — **never `null`**, the field is normalized to
  `""` server-side) gates series-specific screening/feedback questions.
  **If `book_category` is missing** or not one of `fiction`/`memoir`, stop and ask the user
  to confirm/set it before proceeding — do not guess a default.
- Call `resolve_path(book_slug)` (MCP, component omitted) to get the resolved book root —
  `{project}` throughout this skill refers to that base path and handles both standalone
  (`projects/{slug}/`) and series-nested (`series/<series-slug>/{slug}/`) layouts.
- Read `synopsis.md` (via resolved path) for pitch material.
  **Why:** Recruitment posts need a short, spoiler-free pitch — the Short Synopsis section
  is the raw material; if `{project}/export/blurb.md` already exists (from `promo-writer`),
  reuse its Hook + Conflict elements instead of re-deriving a pitch from scratch.
- Load author profile via MCP `get_author()` — recruitment voice should match author brand.
  Word/phrase-level bans live in `writing_discoveries.donts[].text`.
  **Why:** Same authenticity requirement as `promo-writer` — mismatches break trust with a
  community that will scroll past (or call out) anything that reads as generic ad copy.
- Load genre README(s) — `## Characteristics`, `## Common Tropes`, and `## Anti-Patterns`
  indicate how heavy the genre's content runs and which reader communities fit.
  **Note:** genre READMEs do not contain content-warning lists. Derive concrete warnings
  from the book's own material, or from a prior `/storyforge:sensitivity-reader` pass
  (Category 4, if one exists) — never invent a warning list from the genre label alone.
  **Why:** A dark/heavy-content genre needs explicit content-warning framing in every
  screening question and post; a light genre doesn't need the same gate.
- **Fiction:** Call `resolve_path(book_slug, "characters", "INDEX.md")` then read it if
  character-surprise feedback questions need a name check.
- **Memoir:** Call `resolve_path(book_slug, "people", "INDEX.md")` then read it — use real
  names as they appear in the memoir (or their anonymization aliases). **Never use a
  protected person's real name in public recruitment copy** — same rule as `promo-writer`.
- Read `{plugin_root}/reference/promo/beta-platforms.md` — recruitment-framed platform
  characteristics, post templates, and the screening-question / feedback-form question banks.
  **Why:** Recruitment posts are an *ask*, not a *pitch* — this file's framing differs from
  `reference/promo/platforms.md` (sales/launch promo) on purpose; do not reuse the sales
  templates here.

## StoryOrigin Modes

StoryOrigin has two distinct features for this. Step 1 asks the user which one applies (or
both), since it changes what happens downstream:

| Mode | What it is | Reader experience | Downstream file needed? |
|------|-----------|--------------------|--------------------------|
| **Beta Copies** | "Gather Beta Reader Feedback" feature | Reads in-browser, no download | Yes, but not an *ARC build* — a plain manuscript file is uploaded; the ARC disclaimer/front matter of `--arc` is not required. Exact upload format unconfirmed (see note below) — verify at upload time. |
| **ARC Team / Review Copies** | Classic ARC distribution (StoryOrigin's own feature, or NetGalley/BookFunnel) | Downloads the file | Yes — run `/storyforge:export-engineer <book-slug> [format] --arc` before distributing |

Both modes: 6–8 weeks before launch is the typical lead time to start recruiting. Set a
feedback/review deadline (4–6 weeks is a common default) and consider a mid-point check-in
so a stalled reader is caught early rather than discovered at the deadline.

The exact upload format StoryOrigin's Beta Copies feature expects (docx/txt/EPUB) was not
clearly documented as of this skill's authoring — verify at actual upload time rather than
assuming.

## Workflow

### Step 0: Readiness Check
Use the `status` already loaded in Prerequisites — don't call `get_book_full()` again. Book
statuses run `… → Drafting → Revision → Editing → Proofread → Export Ready → Published`
(`CLAUDE.md`). Recruitment can reasonably start once the manuscript is at **Revision** or
later — earlier than that, the book isn't stable enough to hand to readers.

Note that `Revision` is only auto-derived once *every* chapter reaches Revision rank — a
book mid-revision-pass still reports `Drafting`, which is a normal state for early
recruitment, not a red flag. If `status` is earlier than `Revision`, warn the user, state
which condition triggered the warning, and ask whether to proceed anyway (e.g. a very early
beta-reader/critique-partner round is a legitimate exception, not a hard block).

### Step 1: Campaign Basics
Ask the user (AskUserQuestion):
- **StoryOrigin mode:** Beta Copies / ARC Team (Review Copies) / Both / Not using StoryOrigin
- **Feedback/review deadline:** default 4–6 weeks out
- **Mid-point check-in:** yes/no

**Gate:** Present the campaign basics summary. **Wait for explicit user approval** before
proceeding to Step 2 — implicit agreement doesn't count.

### Step 2: Screening Questions
Pick 3–5 questions from the Screening-Question Bank in `beta-platforms.md`, tailored to:
- Genre (content-warning question mandatory for dark/heavy-content genres — never soften
  this to inflate signups)
- `series` (add the series-specific question only if `series` is a non-empty string)
- StoryOrigin mode (drop the "active on Goodreads/StoryGraph" question for Beta-Copies-only,
  feedback-focused campaigns — it only matters when public reviews are the goal)

**Output:** `{project}/promo/beta/screening-questions.md`

**Gate:** Present the questions. **Wait for explicit user approval** before proceeding.

### Step 3: Feedback-Form Questions
Build the post-read feedback form from the Feedback-Form Question Bank in
`beta-platforms.md`:
- Tone-shift question — only if the book has a deliberate genre/tone shift (check
  `plot/tone.md` if present, or ask the user directly)
- Character-surprise question (fiction) or the two memoir-specific questions (memoir) —
  branch on `book_category`
- Series-specific questions — only if `series` is a non-empty string

**Output:** `{project}/promo/beta/feedback-form.md`. Close the file with a collection note:
responses should be consolidated into `{project}/research/beta-feedback.md` in the format
`/storyforge:beta-feedback` parses — one `###` heading per item, body text, and an
`Affected: Ch N, Ch M` line where the reader points at specific chapters. This skill does
not collect or parse responses; it only defines the questions.

**Gate:** Present the form. **Wait for explicit user approval** before proceeding.

### Step 4: Platform-Specific Recruitment Posts
If a platform was passed as the skill's optional positional argument, pre-select it and
skip the question below. Otherwise ask the user which platforms to generate for
(AskUserQuestion, multiSelect) — suggest a default set based on genre (e.g.
LGBTQ+/dark-fantasy genres → Reddit, Goodreads, StoryGraph, TikTok as strong defaults;
adjust per the book's actual genre combination).

For each selected platform, apply the characteristics and post template from
`beta-platforms.md`. Generate native content per platform — never cross-post identical text.

**Available platforms:** `reddit.md`, `goodreads.md`, `storygraph.md`, `tiktok.md`,
`facebook.md`, `bluesky.md`, `newsletter.md`

**Output files:** `{project}/promo/beta/{platform}.md`

**Verify before finalizing:**
- Bluesky: 300 character limit
- No purchase/buy links anywhere — this is a free-copy ask, not a sales post
- Content warnings present and honest wherever the genre calls for them
- Memoir: anonymization aliases used consistently, never a protected person's real name

**Gate:** Present the generated platform files. **Wait for explicit user confirmation**
before proceeding to Step 5.

### Step 5: Community Shortlist
List concrete community *types* worth approaching, grounded in the book's actual genre
combination (e.g. "an LGBTQ+ fantasy Goodreads group," "a dark-fantasy subreddit") — **never
fabricate a specific group name, subreddit name, or URL as if it's a verified, currently-
existing community.** Point the user at the kind of community to search for and verify
themselves, not a manufactured link.

**Output:** `{project}/promo/beta/communities.md`

**Gate:** Present the shortlist alongside a closing next-steps summary — for ARC Team mode,
point at `/storyforge:export-engineer <book-slug> [format] --arc` to produce the
downloadable file; for either mode, point at `/storyforge:beta-feedback` for when responses
come back. Wait for user acknowledgement before ending the skill.

## Rules
- Every post is an *ask*, not a *pitch* — no purchase/buy links, no sales CTA. The CTA is
  always "apply / DM / comment," never "buy now."
- Content-warning honesty is non-negotiable for heavy-theme genres — never underrepresent
  dark content to inflate signup numbers. This holds even if the user asks to soften a
  warning to get more readers — decline and explain why instead of complying.
- Never fabricate a specific subreddit, Goodreads group, Facebook group, or URL as
  verified/existing. Name community *types*, and tell the user to verify the live posting
  rules of the actual community immediately before posting — these rules change without
  notice.
- Recruitment voice must match author brand (respect `writing_discoveries.donts[].text`)
  but reads as more personal/unpolished than launch-promo copy — BookTok and Reddit
  specifically punish anything that reads like an ad.
- Never promise anything beyond a free early copy plus (for ARC Team mode) an honest
  review, or (for Beta Copies mode) structured feedback — no payment, no other obligation.
- Memoir: anonymization aliases in ALL public recruitment text — same hard rule as
  `promo-writer`.
- For the downloadable-file step, point to `/storyforge:export-engineer <book-slug>
  [format] --arc` — do not attempt to build or describe export logic in this skill.
- For processing feedback that comes back, point to `/storyforge:beta-feedback` — this
  skill's job ends at recruitment.
