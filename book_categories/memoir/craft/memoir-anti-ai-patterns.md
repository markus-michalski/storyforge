---
book_categories: [memoir]
craft_topic: voice-and-truth
status: stable
last_reviewed: 2026-04-27
---

# Memoir Anti-AI Patterns

This is the memoir-specific companion to `reference/craft/anti-ai-patterns.md`.
That doc catalogs universal AI tells — generic vocabulary, smooth-but-flat
rhythm, plausible-sounding-nothing. This doc covers the **memoir-specific
failure modes** that LLM-assisted prose drifts toward and that fiction
prompts do not catch.

The forthcoming `voice-checker` in memoir mode (Phase 3 #62) and the
chapter-writer in memoir mode (Phase 2 #57) load this file. Until those
land, treat it as a manual revision pass.

## The five memoir AI tells

Each pattern below: what it is, why LLMs produce it, an example, and how
to fix it.

---

### 1. Reflective platitude

The narrator pauses to deliver a generic life-lesson in elegant cadence.
The lesson is true the way fortune cookies are true — broad enough to
apply to anyone, specific enough to apply to nobody.

> *Bad*: I have come to understand that grief is not a destination but a
> companion that walks beside us, sometimes quietly, sometimes loudly,
> always present.

The reflection sounds wise. It says nothing. It could close any grief
memoir; therefore it closes none of them.

**Why LLMs do this**: training data is full of grief-essay closings shaped
exactly like this. The model interpolates toward consensus.

**Fix**: replace the platitude with **a specific, slightly-wrong, slightly-
embarrassing thing only this narrator would say**.

> *Better*: Grief is not what people warn you about. Nobody warned me I
> would still be writing the wrong year on checks four months later
> because some part of me had not agreed to live in a year my mother had
> not lived in.

Specificity (checks, four months, a year not yet conceded) defeats the
platitude. The reader believes it because no other narrator could have
said it.

---

### 2. "Looking back, I now realize"

The construction itself, with its cousins:

- *Looking back, I now realize…*
- *In hindsight, I see that…*
- *Now, with the benefit of years, I understand…*
- *Only later did I come to know…*
- *What I did not yet know was…*

These are the AI's go-to retrospective hinges. Each does the same thing:
**announces** that the present-narrator is about to deliver wisdom about
the past. The announcement is the problem — it tells the reader what is
about to happen instead of just doing it.

**Why LLMs do this**: retrospective wisdom is a memoir convention; LLMs
default to the most-rehearsed phrasing of any convention.

**Fix options**:

- **Cut the hinge entirely**. Move directly into the realization;
  trust the tense shift to do the work.
- **Move the realization into a scene** so the past-self comes to it
  rather than the present-narrator delivering it.
- **Replace with a more idiosyncratic move**: "It took me a decade to
  understand…" / "I was wrong about him for years. I am still occasionally
  wrong." The voice betrays a specific narrator, not a generic one.

> *Bad*: Looking back, I now realize that my mother had been afraid for
> years.
>
> *Better*: It took her death for the fear to make sense. She had been
> rehearsing it for years.

---

### 3. Tidy lessons / earned wisdom

The chapter ends with a clean takeaway. The narrator has Learned Something.
The reader nods. The book has done its job.

> *Bad*: I left the apartment that day understanding, finally, that love
> was not the same as obligation. It was a lesson I would carry with me.

The lesson is too clean. Real change is not legible at the moment of
change; it is partial, contradicted by next week's behavior, slowly
reversed and re-reversed. A lesson that announces itself as final almost
certainly wasn't.

**Why LLMs do this**: chapter-ending wisdom is a strong training pattern;
the model converges on it.

**Fix**: end the chapter on **the moment, not the meaning**. The reader
will extract the lesson if it's there. If you have to deliver it, deliver
it slant — partial, self-undermining, contradicted by the next chapter.

> *Better*: I left the apartment that day. Six weeks later I went back to
> get a sweater I had not actually forgotten. He was not home. I sat on
> the steps for an hour pretending I was waiting for him.

The non-tidy ending tells the reader the lesson was not learned. That is
emotional truth.

---

### 4. Hedging as humility

The narrator softens every claim with qualifiers — *perhaps*, *I think*,
*maybe*, *some part of me*, *in a sense*, *in some way*, *to a certain
extent* — until the prose is upholstered in cotton.

> *Bad*: I think perhaps in some way I had always known, on some level,
> that the marriage was, in a sense, over.

The narrator is doing **performative humility**. The reader does not
believe the narrator's uncertainty; they correctly read it as the writer's
fear of commitment to the claim.

**Why LLMs do this**: AI safety training rewards hedging. Memoir prose
suffers under it.

**Fix**: remove every qualifier on the first pass. Add back the one or
two that mark genuine uncertainty. The rest were upholstery.

> *Better*: I had always known the marriage was over. Knowing was the
> easy part.

If the second sentence ("knowing was the easy part") is false, the
narrator can replace it with a more accurate hard-edged claim. But the
hedging version concedes nothing real.

---

### 5. The therapeutic reframe

The narrator interprets a past experience through a present-day vocabulary
of therapy, trauma, attachment styles, somatics, parts work, nervous-system
language. The reframe is intelligent. It is also **anachronistic** —
imposing a current frame on a past that did not have it.

> *Bad*: I see now that my body was holding the trauma of those years in
> my fascia, my breath patterns, my dysregulated nervous system, manifesting
> as the chronic tension that twenty-year-old me did not yet have the
> language to name.

The vocabulary is twenty-five years more advanced than the past-self's
experience. The retrospective frame is plausible — and may even be true —
but it occupies the page where the **felt sense at the time** should live.

**Why LLMs do this**: therapeutic language has saturated memoir-adjacent
training data; the model defaults to the contemporary lexicon.

**Fix options**:

- **Render the past-self's experience in the past-self's vocabulary**.
  "My back hurt all the time and I couldn't sleep" is more honest and
  more dramatic than "my dysregulated nervous system was holding…"
- **If the contemporary frame matters, mark it as retrospective**, in a
  short summary beat, not a scene-disrupting interruption: "What I
  would now call dissociation, I then called 'spacing out.' I spaced out
  through most of that year."
- **Trust the reader to bring their own contemporary frame** to the
  rendered experience. They will name it. You don't have to.

---

## The reflexive AI-tell pattern: explanation-after-image

A subtler tell, common when LLMs assist with sentence-by-sentence
composition: every concrete image is **immediately followed by an
explanation of its meaning**.

> *Bad*: He set down the coffee mug very carefully on the saucer, the
> small ceremony of a man trying to control what he could because so much
> else had slipped through his hands.

The image (careful coffee mug) does work. The explanation (because so
much else had slipped through his hands) **eats the work**. The reader
no longer has to feel anything; they have been told what the image meant.

**Fix**: **strip the explanation**. Trust the image. If you cannot trust
the image, the image is not strong enough — make it stronger, don't
gloss it.

> *Better*: He set down the coffee mug very carefully on the saucer.

The reader does the work. Memoir respects the reader.

---

## A revision pass for AI-tells

When revising any memoir chapter — whether AI-assisted or not — run this
pass:

- [ ] Search for *looking back*, *in hindsight*, *now I see*, *now I realize*, *what I did not yet know* — kill or rewrite
- [ ] Search for *perhaps*, *in some way*, *to a certain extent*, *some part of me*, *in a sense* — strip on first pass, restore only if genuine uncertainty
- [ ] Search for therapy-vocabulary anachronisms (*nervous system*, *dysregulated*, *attachment*, *somatic*, *trauma response*, *parts work*) — verify each was contemporaneous or marked retrospective
- [ ] Read each chapter ending — does it deliver a tidy lesson? Cut the lesson; end on the moment
- [ ] Read each scene — is every concrete image followed by an explanation of its meaning? Strip the explanation; trust the image
- [ ] Read aloud to a person who knew you then — do they recognize you, or do they recognize "memoir voice"?

## What this means for AI-assisted drafting

LLMs are useful for drafting in memoir mode under two conditions:

1. **The author profile carries strong voice constraints** that are loaded
   before any prose generation (the standard StoryForge pattern).
2. **Output passes through this anti-pattern check** before being treated
   as drafted — manually in Phase 1, automatically once
   `voice-checker` learns memoir mode (Phase 3).

Without those guards, AI-drafted memoir reads as memoir-shaped consensus.
The reader can feel it. They will close the book.

## See also

- `reference/craft/anti-ai-patterns.md` — universal AI tells (apply here too)
- `book_categories/memoir/craft/emotional-truth.md` — what the page should be doing instead
- `book_categories/memoir/craft/scene-vs-summary.md` — the scene/summary discipline that prevents many of these
