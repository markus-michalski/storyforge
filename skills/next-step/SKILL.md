---
name: next-step
description: |
  Suggest the next step based on current book status and workflow.
  Use when: (1) User asks "was steht an?", "next step", "was als nächstes?"
  NOT for writer's block or creative resistance — use /storyforge:unblock instead.
model: claude-sonnet-4-6
user-invocable: true
---

# Next Step

## Workflow

1. **Load session** — Use MCP `get_session()` to find active book
   - If no active book: list all books via `list_books()` and ask which one

2. **Load book progress** — Use MCP `get_book_progress()` for the active book

3. **Determine next action** based on book status:

   | Current Status | Next Action | Why |
   |----------------|------------|-----|
   | Idea | `/storyforge:book-conceptualizer` | Develop the concept before plotting |
   | Concept | `/storyforge:plot-architect` | Structure the story |
   | Research | Continue research (`/storyforge:researcher`) or move to plot | Continue if the book needs historical accuracy, location/period authenticity, professional/technical knowledge, or scientific plausibility (per `researcher`'s own research categories) and that research isn't done yet; move to `/storyforge:plot-architect` once those needs are met or the genre has none (e.g. contemporary/no special factual demands) |
   | Plot Outlined | `/storyforge:character-creator` | Populate the story with people |
   | Characters Created | `/storyforge:world-builder` | Build the world (if fantasy/sci-fi/supernatural/historical — matches world-builder's own documented genre scope) or skip to Drafting |
   | World Built | `/storyforge:chapter-writer` ch.1 | Start writing! |
   | Drafting | `/storyforge:chapter-writer` next unwritten chapter | Keep writing |
   | Drafting → Revision (all chapters drafted) | `/storyforge:chapter-reviewer` on first unreviewed chapter | Start per-chapter craft review before the full-book pass |
   | Revision (chapter-reviewer done, humanizer not yet run) | `/storyforge:chapter-humanizer` on first un-humanized chapter | Targeted AI-construction scan: Section 11 elegant-abstraction shapes + flagged vocabulary, interactive fix proposals |
   | Revision (humanizer done, proofreader not yet run) | `/storyforge:chapter-proofreader` on first un-proofread chapter | Language correctness pass: spelling, grammar, punctuation — after humanizer pass |
   | Revision (all chapters proofread) | `/storyforge:manuscript-checker` | Catch cross-chapter prose issues (rules, clichés, dialogue punctuation, filter words, adverbs, repetition) |
   | Editing | `/storyforge:voice-checker` (optional) | Holistic AI-authenticity score 0–100 across 7 dimensions — use when you want a scorecard, not a required step |
   | Proofread | `/storyforge:export-engineer` | Generate the book file |
   | Export Ready | `/storyforge:translator` or publish | Translate or distribute |

   **Revision sub-phase caveat:** `get_book_progress()`/`get_book_full()` only expose a single
   per-chapter `status` (`Outline`/`Draft`/`Review`/`Final`) — there is no MCP field that separately
   records whether chapter-reviewer, chapter-humanizer, or chapter-proofreader has actually run on a
   given chapter. Do NOT assume the three Revision rows above can be derived from tool data alone.
   Determine which sub-phase applies by asking the user directly (or from what this session has
   already done earlier in the conversation) which of those three passes each chapter has already
   been through, then apply the matching row.

4. **Check for incomplete work** — if any of these conflict with step 3's status-table answer, this step wins: lead with fixing the flagged gap, don't bury it under the status-based recommendation.
   - Any chapters reviewed but not yet humanized? → Suggest `chapter-humanizer`
   - Any chapters humanized but not yet proofread? → Suggest `chapter-proofreader`
   - Any chapters in "Draft" that need review? → Suggest `chapter-reviewer`
   - Characters still in "Concept"? → Suggest `character-creator`
   - Missing plot outline? → Suggest `plot-architect`
   - All chapters proofread but `research/manuscript-report.md` missing? → Suggest `manuscript-checker` (this is the final full-manuscript pass — per `chapter-humanizer`'s and `chapter-proofreader`'s documented `chapter-writer → chapter-reviewer → chapter-humanizer → chapter-proofreader → manuscript-checker` ordering, it runs AFTER per-chapter revisions finish, never before them)

5. **Present recommendation** with clear reasoning — if the table entry carries a caveat (e.g. voice-checker's "(optional)"), state that caveat explicitly in the recommendation itself, not just internally; don't present an optional step as a mandatory gate.
