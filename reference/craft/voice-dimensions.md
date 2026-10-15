---
book_categories: [fiction, memoir]
craft_topic: author-voice
status: draft
last_reviewed: 2026-10-15
---

# Voice Dimensions: A Closed Vocabulary for Review Feedback

Review feedback arrives in whatever words the author happens to use: "zu verschwurbelt", "cut the fluff", "das braucht kein Mensch", "make it plainer". These are the same signal. This document defines the closed set of **dimensions** and **directions** that every logged piece of feedback is mapped to, so that recurrence is counted on a stable key and never on wording.

Used by `chapter-voice-harvest` (classification and proposal walk), `log_review_feedback` / `set_feedback_classification` (validation) and the candidate engine (counting, conflicts, target section).

## Key and Meaning

A classification is a pair `(dimension, direction)`:

- **dimension** — what part of the voice the feedback is about (`sentence_rhythm`, `simile_density`, ...).
- **direction** — which way the author pushes it (`shorter`, `fewer`, ...). Each direction has a `kind`:
  - `prefer` — the author wants more of this quality. Becomes a `style_principles` candidate.
  - `avoid` — the author wants less or none of it. Becomes a `donts` candidate.
- **opposite** — the direction that contradicts it inside the same dimension. Two entries with opposite directions in the same scope are reported as a conflict by the candidate engine, never promoted.

`normalized_rule` is the one free-text field: a single plain-language sentence stating the rule. For memoir books it must not contain names, places or facts about real people.

## Classification Procedure

1. **Classify once.** Each feedback entry is classified a single time and the result is stored. Never re-derive it on later runs; model variance must not change the counts.
2. **The diff is primary evidence.** If the entry has a `before → after` pair, read the direction from what changed (sentence got shorter, simile removed, tag swapped for `said`). The comment text is secondary and only disambiguates.
3. **Rejected proposals are evidence too.** A declined suggestion points in the opposite direction of the proposal. Classify what the author kept or asked for instead, not what was proposed.
4. **Pick the narrowest dimension that fits.** Use `other` only when nothing fits, and then set the generic direction `prefer` or `avoid` and put the specifics in `normalized_rule`.
5. **One key per signal.** Every wish has exactly one valid `(dimension, direction)` key; the vocabulary contains no synonyms. If two dimensions seem to fit, apply the precedence rules below.
6. **One entry, one classification.** If a comment mixes several wishes, split it into several entries before classifying.
7. **Ignore non-voice feedback.** Typos, continuity fixes, fact corrections and book-specific rules are not voice evidence; leave them unclassified and discard them at harvest.
8. **Memoir: abstract before storing.** Classify at logging time and write `normalized_rule` without names or facts.

## Precedence

When feedback fits several dimensions, the more specific dimension wins:

| Feedback is about | Use | Not |
|---|---|---|
| a scene or chapter ending on a tidy takeaway | `tidy_lesson_ending` | `scene_ending`, `emotional_restraint` |
| an image followed by its interpretation | `explanation_after_image` | `show_vs_tell`, `exposition_density` |
| an announced realization ("looking back") | `looking_back_hinge` (memoir) | `pov_distance`, `exposition_density` |
| the same word, opening or structure recurring | `repetition` | `pacing`, `word_register` |
| flagged AI vocabulary ("delve", "tapestry") | `ai_vocabulary` | `word_register` |
| universal wisdom delivered in a narrator pause | `reflective_platitude` | `exposition_density` |
| qualifiers that soften claims | `hedging` | `word_register` |

## Overlap with Existing Checks

| Dimension group | Related check |
|---|---|
| `sentence_rhythm`, `paragraph_shape` | `voice-checker` dimensions 2 and 3, `author-check` quantitative targets |
| `dialog_tags`, `dialog_realism` | `voice-checker` dimension 4, `dialog-craft.md` |
| `show_vs_tell`, `emotional_restraint` | `voice-checker` dimension 5, `show-dont-tell.md` |
| `specificity`, `word_register` | `voice-checker` dimensions 1 and 6, `prose-style.md` |
| `simile_density` | `simile-discipline.md` |
| `ai_vocabulary`, `repetition` | `voice-checker` dimension 1, `anti-ai-patterns.md`, `repetition-category-rules.md` |
| `reflective_platitude`, `hedging`, `tidy_lesson_ending`, `explanation_after_image` | `anti-ai-patterns.md` sections 3, 5 and 11 (fiction), `voice-checker` dimension 8 and `memoir-anti-ai-patterns.md` (memoir) |
| `looking_back_hinge`, `therapeutic_reframe` (memoir only) | `voice-checker` dimension 8, `memoir-anti-ai-patterns.md` |

## Vocabulary

The block below is the machine-readable source of truth. Slugs are lowercase with underscores. Do not rename a slug without a migration for stored rows.

```yaml
sentence_rhythm:
  definition: Length and variation of sentences, including fragments.
  categories: [fiction, memoir]
  directions:
    shorter: {kind: prefer, opposite: longer}
    longer: {kind: prefer, opposite: shorter}
    more_variance: {kind: prefer, opposite: more_uniform}
    more_uniform: {kind: prefer, opposite: more_variance}
    more_fragments: {kind: prefer, opposite: fewer_fragments}
    fewer_fragments: {kind: avoid, opposite: more_fragments}
  examples:
    - "Zu lang, brich das auf."
    - "Cut this down, three clauses is too many."

paragraph_shape:
  definition: Paragraph length, single-line paragraphs, blocks of text.
  categories: [fiction, memoir]
  directions:
    shorter: {kind: prefer, opposite: longer}
    longer: {kind: prefer, opposite: shorter}
    more_single_line: {kind: prefer, opposite: fewer_single_line}
    fewer_single_line: {kind: avoid, opposite: more_single_line}
  examples:
    - "Der Absatz ist ein Block, teil ihn."
    - "Too many one-liners in a row, merge them."

dialog_tags:
  definition: Speech tags and action beats around dialogue.
  categories: [fiction, memoir]
  directions:
    more_said: {kind: prefer}
    fewer_creative_tags: {kind: avoid}
    more_action_beats: {kind: prefer, opposite: fewer_action_beats}
    fewer_action_beats: {kind: avoid, opposite: more_action_beats}
    more_tagless: {kind: prefer}
  examples:
    - "Kein 'murmelte', einfach 'sagte'."
    - "Stop inventing tags, said is fine."

dialog_realism:
  definition: How spoken dialogue sounds - interruptions, fragments, subtext, distinct voices.
  categories: [fiction, memoir]
  directions:
    more_broken_speech: {kind: prefer, opposite: more_polished_speech}
    more_polished_speech: {kind: prefer, opposite: more_broken_speech}
    more_subtext: {kind: prefer}
    more_distinct_voices: {kind: prefer}
  examples:
    - "Niemand redet so sauber."
    - "She would never say that out loud, make it less direct."

simile_density:
  definition: How often comparisons and metaphors appear and how load-bearing they are.
  categories: [fiction, memoir]
  directions:
    fewer: {kind: avoid, opposite: more}
    more: {kind: prefer, opposite: fewer}
    more_concrete: {kind: prefer}
  examples:
    - "Der Vergleich trägt nichts, raus."
    - "One simile per page is plenty."

show_vs_tell:
  definition: Whether the prose names states and meanings or renders them through action and image.
  categories: [fiction, memoir]
  directions:
    more_showing: {kind: prefer, opposite: more_telling}
    more_telling: {kind: prefer, opposite: more_showing}
  examples:
    - "Sag nicht, dass sie traurig ist, zeig es."
    - "Why name the feeling, the gesture already does it."

emotional_restraint:
  definition: How openly and how intensely emotion is rendered.
  categories: [fiction, memoir]
  directions:
    more_restrained: {kind: prefer, opposite: more_open}
    more_open: {kind: prefer, opposite: more_restrained}
    less_melodrama: {kind: avoid}
  examples:
    - "Das ist zu dick aufgetragen."
    - "Let the moment stay unresolved."

humor_register:
  definition: Presence and kind of humour, sarcasm and irony.
  categories: [fiction, memoir]
  directions:
    more_humor: {kind: prefer, opposite: less_humor}
    less_humor: {kind: avoid, opposite: more_humor}
    drier: {kind: prefer}
    less_snark: {kind: avoid}
  examples:
    - "Hier darf es trockener sein."
    - "The joke undercuts the scene, drop it."

word_register:
  definition: Vocabulary level and formality - plain versus ornate, colloquial versus formal.
  categories: [fiction, memoir]
  directions:
    plainer: {kind: prefer, opposite: more_ornate}
    more_ornate: {kind: prefer, opposite: plainer}
    more_colloquial: {kind: prefer, opposite: more_formal}
    more_formal: {kind: prefer, opposite: more_colloquial}
    fewer_abstract_nouns: {kind: avoid}
  examples:
    - "Das Wort kennt keiner, nimm ein einfacheres."
    - "Too fancy, say it the way you would say it."

specificity:
  definition: Concrete, particular detail versus generic description.
  categories: [fiction, memoir]
  directions:
    more_specific: {kind: prefer}
    fewer_generic_adjectives: {kind: avoid}
    fewer_filler_details: {kind: avoid}
  examples:
    - "Welcher Baum? Sag es genau."
    - "A beautiful sunset tells me nothing."

scene_opening:
  definition: How scenes and chapters begin.
  categories: [fiction, memoir]
  directions:
    more_in_medias_res: {kind: prefer}
    fewer_weather_openings: {kind: avoid}
  examples:
    - "Fang mittendrin an."
    - "Skip the establishing paragraph."

scene_ending:
  definition: How scenes and chapters close.
  categories: [fiction, memoir]
  directions:
    end_on_the_moment: {kind: prefer}
    fewer_summary_endings: {kind: avoid}
    more_hook: {kind: prefer}
  examples:
    - "Der letzte Absatz erklärt zu viel."
    - "Stop one beat earlier."

punctuation_dashes:
  definition: Em dashes, dash-heavy rhythm and other punctuation habits.
  categories: [fiction, memoir]
  directions:
    fewer_dashes: {kind: avoid}
    more_commas: {kind: prefer}
    fewer_ellipses: {kind: avoid}
    fewer_exclamations: {kind: avoid}
  examples:
    - "Zu viele Gedankenstriche."
    - "Use a period, not another dash."

pov_distance:
  definition: How close the narration sits to the point-of-view character.
  categories: [fiction, memoir]
  directions:
    closer: {kind: prefer, opposite: more_distant}
    more_distant: {kind: prefer, opposite: closer}
    fewer_filter_words: {kind: avoid}
  examples:
    - "Wir sind zu weit weg von ihr."
    - "Drop 'she saw' and just give me what she saw."

pacing:
  definition: Speed of the scene - how quickly events and beats move.
  categories: [fiction, memoir]
  directions:
    faster: {kind: prefer, opposite: slower}
    slower: {kind: prefer, opposite: faster}
    more_variation: {kind: prefer}
  examples:
    - "Das zieht sich."
    - "Linger here, this is the moment."

exposition_density:
  definition: Amount of explanation, backstory and information delivered in the prose.
  categories: [fiction, memoir]
  directions:
    less_exposition: {kind: avoid, opposite: more_exposition}
    more_exposition: {kind: prefer, opposite: less_exposition}
  examples:
    - "Das weiß der Leser schon."
    - "Trust the reader, cut the explanation."

reflective_platitude:
  definition: Narrator pauses that deliver universal life wisdom in elegant cadence.
  categories: [fiction, memoir]
  directions:
    less: {kind: avoid}
  examples:
    - "Das klingt wie ein Kalenderspruch."
    - "Fortune-cookie line, make it specific or cut it."

looking_back_hinge:
  definition: Retrospective announcements such as "looking back, I realize".
  categories: [memoir]
  directions:
    less: {kind: avoid}
  examples:
    - "Streich das 'rückblickend'."
    - "Don't announce the realization, just have it."

tidy_lesson_ending:
  definition: Chapters or scenes that end on a clean takeaway or learned lesson.
  categories: [fiction, memoir]
  directions:
    less: {kind: avoid}
    more_unresolved: {kind: prefer}
  examples:
    - "Das Ende ist zu aufgeräumt."
    - "It all wraps up too neatly, leave it open."

hedging:
  definition: Qualifiers that soften claims - perhaps, I think, in a sense.
  categories: [fiction, memoir]
  directions:
    less: {kind: avoid}
  examples:
    - "Zu viele 'vielleicht'."
    - "Commit to the sentence."

therapeutic_reframe:
  definition: Therapy vocabulary imposed on a past self who did not have it.
  categories: [memoir]
  directions:
    less: {kind: avoid}
  examples:
    - "So hat sie damals nicht gedacht."
    - "That is today's vocabulary, not hers back then."

explanation_after_image:
  definition: A concrete image immediately followed by its interpretation.
  categories: [fiction, memoir]
  directions:
    less: {kind: avoid}
  examples:
    - "Das Bild reicht, die Erklärung muss weg."
    - "The image already did the work."

ai_vocabulary:
  definition: Flagged AI-sounding words and phrases ("delve", "tapestry", "it's worth noting").
  categories: [fiction, memoir]
  directions:
    fewer_flagged_words: {kind: avoid}
    plainer_wording: {kind: prefer}
  examples:
    - "Dieses Wort benutzt kein Mensch."
    - "Nobody says 'testament to'."

repetition:
  definition: The same word, sentence opening or sentence structure recurring close together.
  categories: [fiction, memoir]
  directions:
    fewer_word_echoes: {kind: avoid}
    fewer_repeated_openings: {kind: avoid}
    fewer_repeated_structures: {kind: avoid}
  examples:
    - "Das Wort steht dreimal auf einer Seite."
    - "Every sentence starts with 'She'."

other:
  definition: Voice feedback that fits no dimension above; the specifics go into normalized_rule.
  categories: [fiction, memoir]
  directions:
    prefer: {kind: prefer}
    avoid: {kind: avoid}
  examples:
    - "Das klingt nicht nach mir."
    - "This is not how I would put it."
```
