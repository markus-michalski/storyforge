---
name: chapter-humanizer
description: |
  Targeted AI-construction scan on an existing chapter draft. Identifies Section 11 elegant-abstraction
  shapes and flagged vocabulary hits, proposes human alternatives per occurrence, applies approved
  changes interactively to draft.md. Run after chapter-reviewer, before chapter-proofreader.
  Use when: (1) User says "humanize chapter", "AI-Tells entfernen", "chapter humanizer",
  (2) After chapter-reviewer craft fixes are applied and the prose still feels AI-generated,
  (3) As a mandatory step in the standard writing workflow between review and proofread.
model: claude-opus-5
user-invocable: true
argument-hint: "<book-slug> <chapter-slug>"
---

# Chapter Humanizer

The chapter-humanizer is a surgical pass — not a rewrite. Its job is to find AI-construction patterns in already-reviewed prose and replace them with alternatives written in the author's voice. It does not touch craft, structure, story logic, or anything the chapter-reviewer already addressed.

**Position in workflow:** `chapter-writer → chapter-reviewer → chapter-humanizer → chapter-proofreader → manuscript-checker`

## Prerequisites — MANDATORY LOADS

Before scanning a single line:

0. **Resolve book context** — Call MCP `get_book_full(book_slug)`. If it returns an `error` key,
   stop and tell the user the book wasn't found at the expected path. Otherwise extract `author`
   (→ `author_slug`, needed for step 3 and Pass 2's writing-discoveries lookup).
1. **Draft** — Call `resolve_path(book_slug, "chapters", "{chapter}/draft.md")` (MCP) to get the correct path (handles series-nested vs. standalone layout), then read `draft.md` at the returned path. If missing (`exists: false`), stop and tell the user: "Kein draft.md für dieses Kapitel gefunden — chapter-writer muss zuerst laufen."
2. **Anti-AI patterns** — MCP `get_craft_reference("anti-ai-patterns")`. **Why:** Section 11 contains the shape catalog with banned-shape descriptions and examples. Section 1 contains the flagged-vocabulary list. Both are the scan targets.
3. **Author profile** — MCP `get_author(author_slug)`. **Why:** Alternatives must be written in the author's documented voice (tone, rhythm, vocabulary). A proposed fix that doesn't match the author's profile is not a fix — it's a different kind of AI output.
4. **Book CLAUDE.md** — MCP `get_book_claudemd(book_slug)`. **Why:** Book-level rules may contain
   additional banned shapes or construction constraints specific to this book. A book with no
   CLAUDE.md file yet returns whatever DB-rendered Rules/Callbacks/Workflows exist, or empty
   content, instead of an error (storyforge#573) — treat genuinely empty content (`content` is
   `""`, or has no Rules/Callbacks/Workflows entries) as "no additional book-level rules" and
   continue; do not stop or block on it. An `error` key still happens for two distinct causes, and
   neither means "no rules": the book project itself doesn't exist (already handled by
   Prerequisite 0), or the book's `series:` frontmatter names a series it isn't registered in
   (`BookNotLinkedToSeriesError` — a real, reachable state for a book that DOES exist; see the
   `book_rules_unreadable` report category, storyforge#579/#584). On an `error` key here: stop and
   surface it to the user — "book rules could not be read, cannot verify banned-shape or
   construction constraints for this book" — rather than silently treating the check as passed.
   The user decides whether to fix the series link first or proceed anyway.

All five loads are mandatory on every run — including load 4, even for a book you suspect has no extra rules. The only way to know is to actually call the tool; skipping it because it "probably" has nothing is not a valid shortcut.

## Scan — Two Passes

### Pass 1: Section 11 Elegant Abstraction Shapes

Scan every sentence for the following constructions. For each hit, record: line number (approximate), the offending text verbatim, the shape name. A single sentence can match more than one shape (e.g. "the words landed, and the silence held" hits both 11.2 and 11.3) — count and name every matching shape (this feeds the **Section 11 shapes found: N** header count). But when two or more matched shapes fall in the *same sentence*, do NOT report them as separate, independently-appliable hits with their own full-sentence fixes — two overlapping replacements against one sentence cannot both go out in the single write pass (see Applying Changes). Instead, present them as ONE hit numbered entry that names all matched shapes (e.g. "11.2 + 11.3") and carries a single combined "Proposed fix" that resolves every matched shape in that sentence together.

| Shape | What to search for |
|---|---|
| **11.1 Count-and-editorialise fragment** | `One word.` / `Two sentences.` / `Twelve texts.` / `Six syllables.` — a sentence-opening count of a unit of speech or writing (word/sentence/syllable/line/phrase/name/letter/text/message) followed by narrator editorial about the rarity or weight of that count. Only flag when the fragment opens a sentence/dialogue beat; plain time/distance/duration counts ("He had been gone three days.", a countdown like "Twelve seconds.") are NOT the tell — those are measurements, not editorialised utterances |
| **11.2 Sentence-as-projectile** | `the words landed`, `the line landed`, `the sentence landed`, `settled into the room`, `sat in the room` |
| **11.3 Room-as-receiver** | `the room received`, `the silence held`, `the hall absorbed`, `the air carried`, `the quiet kept` |
| **11.4 Economic metaphor** | `most expensive [word/sentence/motion/gesture]`, `the word cost him`, `paid in silence`, `[action] cost her` (non-literal) |
| **11.5 Near-miss body language** | `did not quite become`, `almost became a`, `never quite [verb]` — one per scene is acceptable, do NOT flag it; 2+ in the same scene → flag ALL instances |
| **11.6 Body-part agency** | `[hand\|breath\|stomach\|shoulders\|face\|mouth\|eyes\|chest\|throat\|jaw\|spine\|fingers\|knee\|feet\|legs] + [had been\|was\|were\|kept\|started\|began] + [deciding\|having\|choosing\|wanting\|refusing\|trying\|failing\|knowing]` — see Section 11.6 for full regex |
| **11.6 Trust-split** | `trust his/her/my face`, `trust his/her voice`, `trust his/her hands` + `distrust`/`not trust` variants |
| **11.7 Backward-negation loop** | `what [pronoun] had been refusing/unable/failing to [verb]` where the verb echoes the sentence's opening action |
| **11.8 Expository repeat** | Same noun-phrase or logical constraint appearing in two consecutive sentences — second sentence restates first to justify a narrative gap |
| **11.9 Negation-as-assertion loop** | `It wasn't [X]. It was [Y].` or `Not [X]. [Y].` — flag on 2nd+ occurrence per scene |
| **11.10 Hedge-word density** | `seemed`, `appeared to`, `as if` (non-simile use), `might have` — flag when 3+ combined instances per scene |

**11.9 / 11.10 density rules:** Count instances per scene. 11.9: flag from the second negation-assertion per scene onward. 11.10: flag when *seemed* / *appeared to* / *as if* (non-simile) / *might have* reaches 3+ combined per scene — report the count and all instances.

### Pass 2: Flagged Vocabulary (Section 1)

Scan for the 60 flagged words and phrases from Section 1 of anti-ai-patterns.md. Entries 1–55 include core AI-vocabulary (`delve`, `tapestry`, `nuanced`, `vibrant`, `landscape` (metaphorical), `embark`, `resonate`, `pivotal`, `realm`, `testament`, `intricate`, `myriad`, `unprecedented`, `foster`, `navigate` (metaphorical), etc.). Entries 56–60 are formal transition tells: `Furthermore`, `Moreover`, `In addition`, `Conversely`, `On the other hand`.

For each hit: record word, sentence, context. Flag only non-literal uses — words that are clearly literal or in-character dialect are excluded from the scan (e.g. flag "the tapestry of lies wove tighter" — metaphorical; do NOT flag "she folded the tapestry on the loom" — literal physical object).

Also check the author profile's `writing_discoveries.donts` — these are book/author-specific additions. *(The SQLite-backed `donts` entries are authoritative; `vocabulary.md` is superseded — Issue #281.)*

## Output: Scan Report

After both passes, present the findings as a numbered list. No change is written to `draft.md`
until the user gives an explicit apply/skip decision on this exact batch — see the GATE below
the report template. **Hard cap: ≤ 20 hits per batch.** Before writing the report, count total hits — if there are more than 20, present only the first 20 now, apply those per the user's response, then present the next batch (do not dump all hits in one report).

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

> **--- APPROVAL GATE ---**
> Stop here. Do NOT proceed to Applying Changes or touch `draft.md` this turn.
> Unlocks only on an explicit apply/skip decision on THIS batch. A reply containing ANY rework
> holds the ENTIRE batch — plain-apply hits included — until that rework's replacement is
> confirmed (see Rework below).
> Silence or generic enthusiasm is not approval — no "keep moving instead of asking"
> instruction overrides this gate.
> **--- END GATE ---**

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

If the user's response mixes a rework with plain apply/skip instructions (e.g. `apply 1, 4 / skip 2 / 3: shorter`), do NOT write any of the batch yet — even the plain-apply hits. Resolve the rework's confirmation first, THEN apply the full batch (plain-applies + confirmed reworks, minus skips) together in the single write pass described below.

### Applying Changes

**Entry check.** Confirm the current message replies to the batch just presented (GATE above),
and that every pending rework has been confirmed. Doubt which batch a stray "apply all" targets
→ ask, don't guess.

After the user approves (or applies with reworks confirmed):

1. Read the full `draft.md` again before writing (GH#27 — file may have changed if the session has been long). Do this even though you already have its content from the Prerequisites load or the scan pass — that copy may be stale, and reusing it instead of issuing a fresh Read is exactly the GH#27 failure mode.
2. Apply ALL approved changes in a single write pass — one write, all changes together.
3. Report: *"Applied N changes. Skipped M. Draft updated."*
4. If flagged vocabulary was accepted to stay, note it: *"[word] kept at your request."*

### Iteration

After applying, offer: *"Möchtest du noch eine Runde? Oder weiter zu `/storyforge:chapter-proofreader`?"*

If the user wants another pass: re-scan the updated draft (the fixes may have introduced new issues — rare but possible). Track how many **scans** (not batches) have run in this session — this initial scan is pass 1, the first re-scan is pass 2. A single scan that needs multiple ≤20-hit batches (Output: Scan Report) is still ONE pass: batches within one scan never increment the counter, only a re-scan of the already-updated draft does. **Hard cap: 2 passes (scans) per session.** If the user asks for a 3rd scan after pass 2 has completed, decline and redirect instead of re-scanning again: *"Zwei Humanizer-Runden sind für diese Session das Limit. Für weitere Änderungen: neue Session starten oder direkt manuell anpassen."*

## Record Pass Completion (Issue #479)

Once the user moves on (accepts the "weiter zu `/storyforge:chapter-proofreader`" offer, or
explicitly ends the humanizer session), record that chapter-humanizer has run on this chapter, so
`next-step` can derive revision sub-phase progress instead of asking the user:

1. Call `resolve_path(book_slug, "chapters", chapter_slug)` (MCP) to resolve `chapter_dir` (its `path` field).
2. Call `update_field(f"{chapter_dir}/chapter.yaml", "humanizer_pass_done", "true")` (MCP).

`chapter.yaml` is guaranteed to exist here — chapters only reach chapter-humanizer after
`start_chapter_draft` already created it (Issue #16), and after chapter-reviewer has already run.

## Surgical Mode — Core Constraints

All fixes in this skill operate under the following four rules:

1. **Touch only the flagged construction.** The replacement covers the hit and nothing else — surrounding prose, style, and content remain as the chapter-reviewer left them.
2. **Verify alternatives before proposing.** Confirm that the proposed replacement is free of Section 11 shapes, flagged vocabulary, and other known AI-tells before presenting it.
3. **Author voice is mandatory.** Every proposed alternative must match the author's documented tone, rhythm, and vocabulary. An alternative that sounds like a different author is a regression, not a fix.
4. **Read the full file before writing.** GH#27 applies here — see Applying Changes, step 1, for the exact re-read requirement.

## Rules

- **Never blind-apply — hard block, not a default.** Every hit needs an explicit apply/skip
  decision before it's written; batch approval via the User Response Formats above counts. Not
  met by proceeding without a reply or any "keep moving instead of asking" instruction — see the
  Scan Report GATE.
- **Surgical only.** Apply Surgical Mode above. The chapter-reviewer already handled craft.
- **No wholesale rewrites.** If a passage has so many Section 11 shapes that individual fixes would require reconstructing the scene, stop and tell the user: *"Szene [N] hat [X] overlapping shapes — eine gezielte Überarbeitung der ganzen Szene wäre effizienter als Einzelfixes. Soll ich Vorschläge für die ganze Szene machen?"* Then wait for explicit confirmation before proceeding.
- **voice-checker is optional after humanizing.** If the user wants a holistic score after this pass, suggest `/storyforge:voice-checker`. But the humanizer's targeted pass is more actionable for the patterns it covers.
