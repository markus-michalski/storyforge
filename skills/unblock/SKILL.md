---
name: unblock
description: |
  Diagnose and resolve writer's block with targeted, book-context-aware interventions.
  Use when: User says "I'm stuck", "Ich komme nicht weiter", "blocked", "can't write",
  "keine Motivation", "keine Lust", "Schreibblockade", or similar signals of creative resistance.
model: claude-opus-4-7
user-invocable: true
---

# Unblock

Writer's block is not one thing. It has 4 distinct root causes, each requiring a different fix.
Diagnose first. Intervene precisely. Never give generic "just write!" advice.

## Workflow

### Step 1: Diagnose the Block

Use AskUserQuestion to identify the root cause. Ask warmly, without judgment:

**"Was passiert, wenn du versuchst zu schreiben?"**

Options:
- **Fear** — "Ich weiß nicht, ob das gut genug ist" / "I'm afraid it's not good enough"
- **Perfectionism** — "Ich schreibe den gleichen Absatz immer wieder" / "I keep rewriting the same paragraph"
- **Procrastination** — "Ich habe die Datei seit Tagen nicht geöffnet" / "I haven't opened the file in days"
- **Distraction** — "Ich fange an, aber ich kann mich nicht konzentrieren" / "I start but can't focus"
- **Something else** — Let the user describe in their own words

If "Something else": Listen carefully. Map to the nearest root cause before continuing. If genuinely unclear, ask one follow-up question: "Ist es eher ein inneres oder ein äußeres Problem?" (inner = Fear/Perfectionism, outer = Procrastination/Distraction)

### Step 2: Load Book Context

Use MCP `get_session()` to find the active book slug.

If no active session: Use AskUserQuestion to ask which book they're working on (`list_books()` for options). Then `get_book_full(book_slug)`.

Load from `get_book_full(book_slug)`:
- Current chapter (most recently active)
- Last written scene or last chapter excerpt
- Protagonist's name and current situation
- Genre(s) and tone

This context drives the warmup exercise in Step 4 — without it, the exercise is generic and useless.

### Step 3: Deliver Targeted Intervention

Each cause gets a specific, actionable response. No overlap, no hedging.

---

#### Fear — "I don't know if this is good enough"

**Reframe:** Fear is not the enemy — it's data. Fear of bad writing means you care enough to do it right. That's called craftsmanship. Every writer you admire felt this on every book.

**The truth about fear in writing:**
- Fear means you're working at the edge of your ability — that's exactly where growth happens.
- "Good enough" is the wrong question during a draft. The only question is: does this scene advance the story?
- Nobody reads your first draft. Nobody. Not even you — you'll revise it.

**Intervention:**
1. Name the specific fear. Ask: "Was genau hast du Angst, dass nicht gut genug ist?" (the prose? the plot? the voice? the whole concept?) — then address that specific thing, not a vague fear.
2. Suggest a **throwaway warmup scene** (Step 4) — something that will never appear in the book. No stakes. Pure practice.
3. Remind them: your only job right now is to finish the draft. Editing is a different job, done by a different version of you.

---

#### Perfectionism — "I keep rewriting the same paragraph"

**Reframe:** Perfectionism is drafting mode and editing mode running simultaneously. They are incompatible. You cannot drive forward while constantly braking.

**The two-mode rule:**
- **Draft mode:** Write forward. No deleting. No rereading. Ugly sentences are allowed. Ugly sentences are expected. A bad sentence that exists is infinitely better than a perfect sentence that doesn't.
- **Edit mode:** Separate session. Cold read. After the full draft is done.

**Intervention:**
1. **Hard stop the loop.** If they're stuck on the same paragraph: copy it, move it to a "parking lot" document, and skip past it. Mark it `[FIX LATER]` in the draft.
2. **Vomit draft** — Ask them to write just the next 3 sentences. Not good sentences. Just 3 sentences that happen. The bar is: do they exist?
3. **Permission statement:** Read this aloud if it helps: "I give myself permission to write badly. This draft is for me alone."

---

#### Procrastination — "I haven't opened the file in days"

**Reframe:** Procrastination is not laziness — it's avoidance. Something about this project feels overwhelming, threatening, or unclear. Find the real obstacle.

**Diagnostic questions** (pick the most relevant):
- Is the next step unclear? (→ use `next-step` to clarify what to write next)
- Is the daily target too high? (→ lower it dramatically: 100 words per day is better than 1000 words never)
- Does the project feel too big? (→ shrink the horizon to just today's scene)
- Is there life stuff competing for mental energy? (→ acknowledge it; don't fight it)

**Intervention:**
1. **Micro-goal:** Set a target so small it's impossible to fail. "Open the file and write one sentence." Not a good sentence. Just one sentence that wasn't there before.
2. **Schedule procrastination intentionally:** Instead of fighting the urge to avoid, assign it a time slot. "I will procrastinate from 14:00 to 15:00. From 15:00 to 15:30 I write." This removes the guilt spiral that makes procrastination worse.
3. **Anchor the session:** Pick a physical ritual that signals "writing time": same chair, same drink, same playlist, lights a certain way. The ritual becomes the trigger.

---

#### Distraction — "I start but can't focus"

**Reframe:** Distraction is an environment problem disguised as a willpower problem. The brain seeks novelty. If the environment offers novelty (phone, browser, noise), the brain will take it every time. Fix the environment, not yourself.

**Environment audit checklist:**
- [ ] Phone in another room (not face-down, not silenced — other room)
- [ ] Browser closed or site-blocked during writing session
- [ ] Notifications off at OS level (not just app level)
- [ ] Physical space: desk clear of non-writing items?
- [ ] Noise: is it music with lyrics? (lyrics compete with the language center — switch to instrumental or silence)
- [ ] Time of day: are you writing when you're cognitively sharpest, or when you're depleted?

**Intervention:**
1. **Environment audit:** Walk through the checklist above. Identify the biggest distraction. Fix one thing right now.
2. **Timed writing sprint:** Offer to start a focused sprint together. "25 minutes. Nothing but the manuscript. I'll give you a prompt to start." (→ leads into the warmup in Step 4, then immediately hands off to chapter-writer)
3. **Change of location:** Sometimes the desk itself is the problem. A café, a library, a park bench — novelty of location can suppress the need for other novelty.

---

### Step 4: Warmup Exercise

For all block types, generate a short, low-pressure warmup prompt based on the actual book.

**Use the loaded book context** (protagonist, current situation, world details).

The warmup must:
- **Not appear in the book** — this is throwaway writing, zero stakes
- **Use the actual characters and world** — but in a side moment or parallel scene
- **Be completable in 5-10 minutes** — 150-300 words max
- **Be playful or low-stakes** — the protagonist doing something mundane, a background character's moment, a "deleted scene" scenario

**Examples (adapt to the actual book):**
- Fear/Perfectionism: "Write the scene where [protagonist] makes breakfast. Nothing happens. Nobody talks. Just the morning routine. 200 words. Ugly is fine."
- Procrastination: "Write the first sentence only. Then the second. Then stop. That's the whole exercise."
- Distraction: "Set a timer for 15 minutes. Write [protagonist] walking from A to B. Describe only what they notice. No plot. No pressure."

Present the warmup as an invitation, not an assignment. "Hier ist eine Idee — kein Druck:"

### Step 5: Handoff

After the intervention + warmup, offer immediate continuation:

Use AskUserQuestion:

**"Bereit weiterzumachen?"**

- **Ja, Kapitel schreiben** — Launch `/storyforge:chapter-writer`
- **Nein, ich brauche mehr Zeit** — Acknowledge, no pressure. "Das ist okay. Komm wieder wenn du bereit bist."
- **Ich möchte erst den Plan sehen** — Launch `/storyforge:next-step` to clarify what comes next

## Notes

- Never lecture. Keep interventions direct, specific, and warm.
- Never suggest "just push through it" without a concrete technique.
- Always use real book context for the warmup — generic prompts break trust.
- If the user's block is ongoing (they mention it's been weeks), suggest `/storyforge:next-step` first — sometimes the block is caused by an unclear path, not psychology.
