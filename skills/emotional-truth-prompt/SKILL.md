---
name: emotional-truth-prompt
description: |
  Interactive felt-sense pass for memoir scenes. Interrogates a chapter draft
  for emotional truth gaps — implicit feelings the narrator doesn't name,
  retrospective-vantage drift, memory contradiction, avoidance hedges, and
  "I was wrong" rendering failures. Outputs targeted questions + revision
  directions, not rewrites.
  Use when: (1) User says "emotional truth", "deepen scene", "memoir scene check",
  "felt sense", "emotionale Wahrheit", "Szene vertiefen", "Erinnerung prüfen",
  (2) After a memoir chapter draft is complete, before chapter-reviewer,
  (3) When a scene feels "smooth" but not alive.
  Only runs on memoir books (book_category: memoir).
model: claude-opus-4-7
user-invocable: true
argument-hint: "<book-slug> [chapter-slug]"
---

# Emotional Truth Prompt

Interactive interrogation pass for memoir chapter drafts. The market gap this
fills: AI writes smoothness. Memoir needs memory contradiction, emotional
specificity, and the not-quite-shareable. This skill finds where the draft
has drifted toward plausible-feeling abstraction and asks the writer the
questions that can only be answered from lived experience.

Outputs **questions and revision directions**, never prose rewrites. The
writer has to do the work — the skill creates the conditions for it.

## When to run

- After a chapter draft exists, before `chapter-reviewer`.
- When the writer says a scene "feels flat" or "too polished" or "like
  everyone else's memoir".
- During revision, as a felt-sense gate before `voice-checker`.
- Does not replace `voice-checker` (AI-tells) or `chapter-reviewer`
  (line-level craft). Different problem: those catch what is wrong with the
  prose; this catches what is missing from the *experience*.

## Prerequisites — MANDATORY LOADS

- **`emotional-truth.md`** via MCP `get_book_category_dir("memoir")` +
  `/craft/emotional-truth.md`. **Why:** The full taxonomy of emotional-truth
  failure modes — thoroughness, avoidance, retrospective vantage, dialogue
  convention, "I was wrong" — is the interrogation framework.
- **`memoir-anti-ai-patterns.md`** via MCP. **Why:** Several emotional-truth
  failures are also memoir AI-tells (tidy lessons, reflective platitudes,
  explanation-after-image). Cross-reference so findings aren't duplicated
  with the voice-checker pass.
- **`scene-vs-summary.md`** via MCP. **Why:** Some emotional-truth gaps are
  actually scene/summary mode errors — a moment that should be dramatized is
  being summarized instead. The fix is a mode switch, not a deeper feeling.
- **Author profile** via MCP `get_author()`. **Why:** Emotional register is
  voice-dependent. A sparse narrator and a maximalist narrator have different
  failure modes. The interrogation questions need to be calibrated to the
  author's documented style.

## Workflow

### 1. Resolve target

Use the user-supplied slugs if provided. Otherwise call MCP `get_session()`
for the active book + chapter. If no active chapter, show the chapter list
via `get_book_full()` and ask which scene to interrogate.

### 2. Verify memoir mode

Call MCP `get_book_full(book_slug)` and read `book_category`.

If `book_category` is not `memoir`: stop. Explain this skill is memoir-only.
Offer `/storyforge:chapter-reviewer` as the fiction analogue.

### 3. Read the chapter draft

Read `{chapter-path}/draft.md` in full. Do not summarize it — you need to
work from the actual text.

Also read the chapter README for context (POV, timeline anchor, what the
chapter is supposed to accomplish in the narrative arc).

### 4. Run the 7-dimension interrogation

For each dimension: scan the full draft, flag what you find, generate
targeted questions. Only flag genuine hits — a clean dimension should say
so clearly.

---

#### ET1 — Implicit Feeling (what the narrator feels but doesn't say)

**What to look for:**
- Emotional states that are named abstractly: "She felt sad." "I was afraid."
  "He seemed angry."
- Body-language reports with no interiority: "My hands were shaking." — but
  what was happening inside?
- Scenes where something significant happens and the narrator gives no
  felt-sense access at all. Emotional blank spots.

**Questions to generate for flagged passages:**
- "What were you actually feeling in this moment — the specific texture of it,
  not the category?"
- "What did you feel that you didn't want to feel? What were you protecting
  yourself from noticing?"
- "Was there something else underneath the named emotion — a contradiction,
  a small comedy, an embarrassment?"

---

#### ET2 — Retrospective Vantage Drift

**What to look for:**
- Past-self given knowledge she did not have: foreshadowing that belongs to
  the present-narrator slipping into scene-level narration.
- Condescension toward past-self: "I was so naive." "I didn't yet understand."
  "If only I'd known." These are performance; they do the reader's emotional
  work for them.
- Contempt toward past-self: angry retrospective judgement ("I was an idiot
  to think that") that functions as therapy on the page.
- Present-narrator intrusion in scene — marked if it clearly serves the
  narrative; flagged if it is reflex.

**Questions to generate for flagged passages:**
- "What did the in-scene-you actually believe at this moment — not what you
  know now?"
- "You wrote [quoted condescension]. What was the in-scene feeling that
  actually belongs here?"
- "Is this retrospective voice doing work, or is it protecting you from
  staying with the scene?"

---

#### ET3 — Memory Contradiction

**What to look for:**
- Suspiciously clean memory: every detail fits together, the narrative has
  no gaps, the past-self's experience reads as complete and coherent.
  Real memory doesn't work like this.
- Missing contradiction: scenes where only one feeling is present. Memory
  of charged events is almost always mixed — dread and relief, grief and
  strange humor, love and rage at the same moment.
- Absent gaps: the writer reconstructs without acknowledging the limits of
  reconstruction. ("I remember every word of that conversation" — do you?)

**Questions to generate for flagged passages:**
- "What do you actually remember about this moment versus what are you
  reconstructing? Where does memory end and imagination begin?"
- "Were there contradictory feelings in this moment — something that you
  felt alongside the dominant emotion that complicates it?"
- "Is there something about this event you genuinely don't remember, or
  remember wrongly? What does that gap feel like — and should it be on the
  page?"

---

#### ET4 — Avoidance Hedge

**What to look for:**
- Vague event references: "what happened", "the incident", "after all that",
  "what he did". Signal phrases for undramatized charged content.
- Euphemism sequences: polite language standing in for what actually occurred.
- Transition elisions: jumping from before to after a significant moment
  without entering it.

**Distinguish avoidance from legitimate summary:** If the writer has named
the refusal ("I have never been able to write this down"), that is honest.
If the vagueness is unnamed, it is avoidance.

**Questions to generate for flagged passages:**
- "You wrote [quoted hedge]. What is actually being avoided here — what is
  the specific thing you can't or won't name?"
- "If you can't dramatize this, can you name what you're not doing and why?
  A named refusal is emotionally true; an unnamed one is mush."
- "What would you lose if you dramatized this? What would the reader gain?"

---

#### ET5 — Thoroughness Trap (detail that doesn't carry feeling)

**What to look for:**
- Inventory sequences: lists of objects, rooms, meals, people present that
  do not serve a felt-sense function.
- Logistical narration: who drove where, who said what first, the sequence
  of procedural events, without the feeling inside them.
- Detail density that flattens rather than deepens: when everything is
  described at the same level of resolution, nothing stands out.

**Questions to generate for flagged passages:**
- "Why does [named detail] survive the cut? What was it carrying when you
  were living through it?"
- "In this passage you describe [inventory]. What detail from this moment do
  you remember most vividly, and why that one?"
- "What could you cut from this passage without losing the felt sense?"

---

#### ET6 — Scene/Summary Mode Error

**What to look for** (cross-reference `scene-vs-summary.md`):
- Hinge moments (first time, last time, the conversation that changed
  everything) rendered in summary instead of scene. These must be dramatized.
- Scene mode used for transitional content that should compress — weeks of
  hospital visits rendered at minute-by-minute resolution.
- Mixed mode confusion: the draft switches between scene and summary without
  a clear intention, creating tonal blur.

**Questions to generate for flagged passages:**
- "This moment [described moment] reads as summary. Is this actually where
  the meaning lives? If yes, it needs to be a scene."
- "You are giving this [transition/procedural sequence] scene-level attention.
  What is it doing that earns that? If nothing, compress it."

---

#### ET7 — "I Was Wrong" Rendering

**What to look for:**
- **Penance porn:** the narrator repeatedly, explicitly flagging their past
  errors with emotional intensity that reads as performance. "I cringe to
  think of it." "I am ashamed even now." "How could I have been so blind."
  When the self-flagellation becomes the point, it's performing regret for
  the reader's absolution.
- **Tidy redemption:** the wrongness resolves into a clean lesson. "I
  learned then that…" "Looking back, I see that I needed to…" The
  memoir-anti-ai-patterns doc covers this; cross-reference.
- **Under-rendering the wrongness:** the narrator gestures at having been
  wrong without ever rendering it from inside the past-self's frame. The
  wrongness is told; the reader is not shown the conditions that produced it.

**Questions to generate for flagged passages:**
- "You wrote [penance marker]. Is this the feeling, or is this performing
  the feeling for the reader?"
- "Can you render this wrongness from inside the past-self's frame — what
  did that version of you actually believe, and why did it make sense to
  her?"
- "What happens if you cut the explicit self-judgement and trust the reader
  to see what the past-self couldn't?"

---

### 5. Present the findings

**Chat target: max ~350 words per dimension.** Surface only real hits; a
clean dimension gets one sentence.

For each flagged dimension:
1. Quote the specific passage (or passages).
2. Name the pattern (ET1–ET7).
3. Give the targeted question(s) for the writer — phrased as genuine
   interrogation, not editorial suggestion.
4. Give one concrete revision direction (not a rewrite) — a structural
   instruction the writer can execute from their own material.

```
## Emotional Truth Report — {chapter-slug}

### ET1 — Implicit Feeling
[CLEAN — no abstract emotion-naming found.]

### ET2 — Retrospective Vantage Drift
[Flag + quote + question(s) + revision direction]

[...per dimension...]

### Summary: Questions for the Writer
[Numbered list of the most important questions across all dimensions —
max 7. These are the questions only the writer can answer. Prioritize the
ones that, if answered, would most change the scene.]

### Verdict
[PASS — proceed to chapter-reviewer |
DEEPEN — address flagged dimensions before review |
REWRITE — scene mode errors or extensive avoidance; structural rework needed]
```

### 6. Interactive deepening _(optional)_

If the user answers any of the targeted questions, respond to each answer by:

1. Noticing what the answer contains that is not on the page yet.
2. Giving a single revision direction based on the answer.
3. NOT rewriting the prose — "You said X. That belongs in the scene. Here
   is where it could enter: [paragraph reference + how to introduce it]."

If the user asks for a rewrite, decline:

> The felt-sense work has to come from you — I can't feel what you felt. What
> I can do is show you where the gap is and give you a frame for entering it.

### 7. Mark the chapter

If the overall verdict is PASS, tell the user the scene is ready for
`chapter-reviewer`. Suggest `/storyforge:chapter-reviewer {chapter-slug}`.

If DEEPEN or REWRITE, do not advance. Ask the user to work the questions and
return for a second pass.

## Rules

- This skill asks questions. It does not answer them. The writer is the only
  person with access to the source material.
- Never generate replacement prose. The temptation is strong; resist it. A
  proposed rewrite forecloses the writer's discovery process.
- ET3 (Memory Contradiction) requires care: do not push the writer to invent
  contradictions that weren't there. The question is "were there?" not
  "there must have been."
- The thoroughness trap (ET5) is common in first drafts. Do not flag every
  detail — only inventory that has no felt-sense function. When in doubt,
  ask: "What is this carrying?"
- Retrospective vantage (ET2) is not always a problem. A memoir's present-
  narrator voice is a legitimate structural layer. Flag **intrusion** (when
  it overwrites the scene's in-the-moment texture), not **presence**.
- Cross-reference with `memoir-anti-ai-patterns.md` before flagging ET7.
  Tidy lessons and reflective platitudes are memoir AI-tells; if they are
  already on the voice-checker pass list, flag them here but note the
  overlap rather than running a full duplicate analysis.
- Honor the author profile. A spare, elliptical voice legitimately leaves
  feeling implicit; that is a style choice, not an ET1 failure. Only flag
  when the implicit feeling creates a blank spot the reader cannot enter.
- This skill runs before `chapter-reviewer`. Chapter-reviewer handles
  line-level craft (dialog punctuation, filter words, show-don't-tell).
  Emotional truth is the structural layer underneath line craft. Don't mix
  the two passes — finish this one first.
