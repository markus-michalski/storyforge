---
name: chapter-humanizer
description: |
  Targeted AI-construction scan on an existing chapter draft. Identifies Section 11 elegant-abstraction
  shapes and flagged vocabulary hits, proposes human alternatives per occurrence, applies approved
  changes interactively to draft.md. Run after chapter-reviewer, before chapter-proofreader.
  Use when: (1) User says "humanize chapter", "AI-Tells entfernen", "chapter humanizer",
  (2) After chapter-reviewer craft fixes are applied and the prose still feels AI-generated,
  (3) As a mandatory step in the standard writing workflow between review and proofread.
model: claude-opus-4-7
user-invocable: true
argument-hint: "<book-slug> <chapter-slug>"
---

# Chapter Humanizer

The chapter-humanizer is a surgical pass — not a rewrite. Its job is to find AI-construction patterns in already-reviewed prose and replace them with alternatives written in the author's voice. It does not touch craft, structure, story logic, or anything the chapter-reviewer already addressed.

**Position in workflow:** `chapter-writer → chapter-reviewer → chapter-humanizer → chapter-proofreader → manuscript-checker`

## Prerequisites — MANDATORY LOADS

Before scanning a single line:

1. **Draft** — Read `{project}/chapters/{chapter}/draft.md` in full. If missing, stop and tell the user: "Kein draft.md für dieses Kapitel gefunden — chapter-writer muss zuerst laufen."
2. **Anti-AI patterns** — MCP `get_craft_reference("anti-ai-patterns")`. **Why:** Section 11 contains the shape catalog with banned-shape descriptions and examples. Section 1 contains the flagged-vocabulary list. Both are the scan targets.
3. **Author profile** — MCP `get_author()`. **Why:** Alternatives must be written in the author's documented voice (tone, rhythm, vocabulary). A proposed fix that doesn't match the author's profile is not a fix — it's a different kind of AI output.
4. **Book CLAUDE.md** — MCP `get_book_claudemd(book_slug)`. **Why:** Book-level rules may contain additional banned shapes or construction constraints specific to this book.

## Scan — Two Passes

### Pass 1: Section 11 Elegant Abstraction Shapes

Scan every sentence for the following constructions. For each hit, record: line number (approximate), the offending text verbatim, the shape name.

| Shape | What to search for |
|---|---|
| **11.1 Word-count commentary** | `One word.` / `Two words.` / `Three words.` followed by narrator editorial about the rarity of those words |
| **11.2 Sentence-as-projectile** | `the words landed`, `the line landed`, `the sentence landed`, `settled into the room`, `sat in the room` |
| **11.3 Room-as-receiver** | `the room received`, `the silence held`, `the hall absorbed`, `the air carried`, `the quiet kept` |
| **11.4 Economic metaphor** | `most expensive [word/sentence/motion/gesture]`, `the word cost him`, `paid in silence`, `[action] cost her` (non-literal) |
| **11.5 Near-miss body language** | `did not quite become`, `almost became a`, `never quite [verb]` — flag count per scene |
| **11.6 Body-part agency** | `[hand\|breath\|stomach\|shoulders\|face\|mouth\|eyes\|chest\|throat\|jaw\|spine\|fingers\|knee\|feet\|legs] + [had been\|was\|were\|kept\|started\|began] + [deciding\|having\|choosing\|wanting\|refusing\|trying\|failing\|knowing]` — see Section 11.6 for full regex |
| **11.6 Trust-split** | `trust his/her/my face`, `trust his/her voice`, `trust his/her hands` + `distrust`/`not trust` variants |
| **11.7 Backward-negation loop** | `what [pronoun] had been refusing/unable/failing to [verb]` where the verb echoes the sentence's opening action |
| **11.8 Expository repeat** | Same noun-phrase or logical constraint appearing in two consecutive sentences — second sentence restates first to justify a narrative gap |
| **11.9 Negation-as-assertion loop** | `It wasn't [X]. It was [Y].` or `Not [X]. [Y].` — flag on 2nd+ occurrence per scene |
| **11.10 Hedge-word density** | `seemed`, `appeared to`, `as if` (non-simile use), `might have` — flag when 3+ combined instances per scene |

**11.5 scoring:** One near-miss per scene is acceptable. Two or more in the same scene → flag all instances.

**11.9 / 11.10 density rules:** Count instances per scene. 11.9: flag from the second negation-assertion per scene onward. 11.10: flag when *seemed* / *appeared to* / *as if* (non-simile) / *might have* reaches 3+ combined per scene — report the count and all instances.

### Pass 2: Flagged Vocabulary (Section 1)

Scan for the 60 flagged words and phrases from Section 1 of anti-ai-patterns.md. Entries 1–55 include core AI-vocabulary (`delve`, `tapestry`, `nuanced`, `vibrant`, `landscape` (metaphorical), `embark`, `resonate`, `pivotal`, `realm`, `testament`, `intricate`, `myriad`, `unprecedented`, `foster`, `navigate` (metaphorical), etc.). Entries 56–60 are formal transition tells: `Furthermore`, `Moreover`, `In addition`, `Conversely`, `On the other hand`.

For each hit: record word, sentence, context. Do not flag words that are clearly literal or in-character dialect.

Also check author profile's `writing_discoveries.donts` and `vocabulary.md` banned list — these are book/author-specific additions.

## Output: Scan Report

After both passes, present the findings as a numbered list. Do NOT apply any changes yet.

```
## Humanizer Scan — {book-slug} / {chapter-slug}

**Section 11 shapes found: N**
**Flagged vocabulary hits: M**
**Near-miss count per scene: [Sc1: X, Sc2: Y, ...]**

---

### Hits

[1] **11.6 Body-part agency** — Sc 2, ~line 47
> *"His throat had been refusing to close on what he'd been holding since yesterday."*
Proposed fix: *"His throat tightened. Yesterday he hadn't been able to cry. He still couldn't, not entirely."*

[2] **11.6 Trust-split** — Sc 2, ~line 52
> *"stayed there until he could trust his face again."*
Proposed fix: *"He held still. When he was sure his expression had settled, he moved."*

[3] **11.8 Expository repeat** — Sc 3, ~line 89
> *"They had silver on her and weren't careful about the rest. They did not look under the shirt of a vampire they had silver on."*
Proposed fix: *"Silver was enough. They didn't check further."*

[4] **Flagged vocabulary** — Sc 1, ~line 12
> *"...the nuanced tension between them..."*
Proposed fix: *"...the tension between them, which neither named..."*

---

**Instructions:** Reply with the hit numbers you want to apply as-is, numbers you want a different alternative for (e.g. "3: shorter"), and numbers you want to skip. Example: "apply 1, 2, 4 / rework 3: make it one sentence / skip none"
```

**Do not present more than 20 hits at once.** If the chapter has more, present the first 20, apply those, then continue with the next batch.

## Interaction Loop

### User Response Formats

The user responds with one of:

- `apply all` — Apply every proposed fix as-is.
- `apply N, M, ...` — Apply specific hit numbers as-is.
- `skip N, M, ...` — Leave those hits unchanged.
- `N: [instruction]` — Rework hit N with the given instruction before applying.
- `apply N, M / skip P / Q: shorter` — Mixed response.

### Rework

When the user requests a rework (`N: [instruction]`), generate a revised alternative that:
- Addresses the specific instruction
- Stays in the author's documented voice
- Does not introduce new Section 11 shapes or flagged vocabulary

Present the rework for confirmation before applying: *"Rework for [N]: '[revised text]' — ok?"*

### Applying Changes

After the user approves (or applies with reworks confirmed):

1. Read the full `draft.md` again before writing (GH#27 — file may have changed if the session has been long).
2. Apply ALL approved changes in a single write pass — do not write the file multiple times.
3. Report: *"Applied N changes. Skipped M. Draft updated."*
4. If flagged vocabulary was accepted to stay, note it: *"[word] kept at your request."*

### Iteration

After applying, offer: *"Möchtest du noch eine Runde? Oder weiter zu `/storyforge:chapter-proofreader`?"*

If the user wants another pass: re-scan the updated draft (the fixes may have introduced new issues — rare but possible). Cap at 2 iterations per session.

## Rules

- **Surgical only.** Change only the flagged construction. Do not improve surrounding prose, fix style, or add content. The chapter-reviewer already handled craft.
- **Author voice is mandatory.** Every proposed alternative must match the author's documented tone, rhythm, and vocabulary. An alternative that sounds like a different author is a regression, not a fix.
- **No wholesale rewrites.** If a passage has so many Section 11 shapes that individual fixes would require reconstructing the scene, stop and tell the user: *"Szene [N] hat [X] overlapping shapes — eine gezielte Überarbeitung der ganzen Szene wäre effizienter als Einzelfixes. Soll ich Vorschläge für die ganze Szene machen?"* Then wait for explicit confirmation before proceeding.
- **Do not create new AI-tells.** Before proposing any fix, run a quick mental check: does the proposed alternative introduce a new Section 11 shape, flagged vocabulary word, or other known tell?
- **Read the full file before writing.** GH#27 applies here. Always re-read `draft.md` before the write pass.
- **voice-checker is optional after humanizing.** If the user wants a holistic score after this pass, suggest `/storyforge:voice-checker`. But the humanizer's targeted pass is more actionable for the patterns it covers.
