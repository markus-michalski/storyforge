# Simile Discipline: When Comparisons Work and When They Don't

Similes are among the most abused tools in fiction. Used well, a simile sharpens an image the reader couldn't otherwise picture, reveals character through the comparison itself, or lands a tonal beat that bare description misses. Used badly, it is decoration — pretty-sounding placeholder prose that tells the reader nothing, and worse, that trains their eye to skim.

This document draws a line between the two. The test is not whether a simile is present. It is whether the simile **does work** that the sentence could not do without it.

## The Core Test

Before every simile survives a scene, two questions must be answered honestly:

1. **Can the reader picture it literally?** If the vehicle (the thing being compared to) doesn't resemble the tenor (the thing being described) in any concrete, imaginable way, the simile fails. Comparisons must be *actually true*, not vaguely poetic.
2. **Does it do work that a concrete beat couldn't?** If a plain, specific sentence would convey the same meaning without loss — and the simile only adds flourish — cut the simile. Flourish is not work.

If a comparison passes both, it earns its place. If it fails either, it is decoration.

> **The Replacement Test** (from `prose-style.md`): If you can replace a simile with a simple declarative statement and lose no meaning, the simile is likely clichéd or empty. The simile must carry information the replacement cannot.

## The Failure Modes

Most bad similes fall into one of these categories. Learn to recognize them on sight.

### 1. The Illogical Comparison

The comparison doesn't make literal sense. The vehicle cannot actually resemble the tenor in any physical, sensory, or structural way. It sounds vaguely meaningful but describes nothing.

**Failing:**
> Viktor worked through a drill that moved like a conversation.

A drill does not move like a conversation. Conversations are not movements. The reader cannot picture this. It sounds thoughtful, but it is empty.

**Working:**
> Viktor worked through a drill with the rhythm of an argument — strike, pause, counter, pause, strike again, faster now.

Here the vehicle (an argument's rhythm) actually resembles the tenor (the drill's cadence) in a specific, describable way: alternation, escalation, the pressure of call-and-response. The reader can picture it.

### 2. The Empty Abstraction

The comparison reaches for an abstract concept where a concrete one would land. Abstract vehicles almost never resemble concrete tenors, because abstractions have no shape.

**Failing:**
> Her grief was like the weight of history.

History has no weight. "Weight of history" is itself already a dead metaphor. The simile is decorating an abstraction with another abstraction.

**Working:**
> Her grief was like a wet coat she had forgotten she was wearing, until she tried to move.

A wet coat is specific. It has weight, it is uncomfortable, it drags at the shoulders, it is forgotten in stillness and noticed in motion. The comparison does work.

### 3. The Decorative "The Kind Of X That Y"

The "the kind of [noun] that [verb]" construction is a frequent AI-tell and a frequent writer-tell for a simile that is trying to sound profound without doing anything.

**Failing:**
> He had the kind of voice that made silence feel like an accusation.

What does that mean? Silence made accusing by a voice? Try to picture it. You can't. It's a sentence that wants to be quoted, not read.

**Working (or cut):**
Often the right move is to delete the sentence and replace it with what the voice actually *does* in the scene — the specific pitch, pace, or word choice that would make a character in the room flinch. Showing beats comparing.

### 4. The Stacked Simile

Two or three similes in the same paragraph. Each is doing decorative work. Together they stop the prose, demand that the reader stop picturing and start admiring.

**Failing:**
> She moved like water through the crowd, her laugh like a bell, her eyes bright as coins in the low light.

Three similes in one sentence. The reader feels none of them. The character is now a composite of decorations rather than a person.

**Rule of thumb:** At most one simile per paragraph unless each one is *doing distinct, necessary work*. When in doubt, pick the strongest and cut the others.

### 5. The Over-Specific Sensation

A cousin to #1. A physical sensation is compared to something so precise and strange that the reader has to stop and work out what it means, and the payoff isn't worth the pause.

**Failing:**
> His stomach dropped like a small animal the floor shouldn't have been able to do.

Grammatically this doesn't even parse. Book-scoped rules in real projects have had to ban "things the floor shouldn't do" and "gone somewhere the face wasn't following" precisely because this failure mode recurs.

**Working:**
> His stomach dropped. Just that — the sudden unmistakable loss of altitude you feel before you realize you're falling.

The comparison is still present ("the loss of altitude before you realize you're falling") but it describes something the reader has actually felt.

### 6. The Dead Simile

A comparison so worn it no longer creates an image. These are the similes readers skip without noticing.

- *pale as a ghost*
- *quiet as a mouse*
- *quick as lightning*
- *cold as ice*
- *sharp as a knife*
- *like a deer in headlights*
- *like a kid in a candy store*

If it sounds familiar, it's probably dead. Either invent a fresh comparison or drop the simile entirely.

## Simile Markers — What to Scan For

When a scene is drafted, walk the prose and flag every instance of these markers. Each one is a simile, and each one must survive the two-question test:

- `like [noun]` — the dominant form
- `as [adj] as [noun]` — "as cold as a morgue floor"
- `as if [clause]` — "as if she'd heard that voice before"
- `the way [subject] [verb]` — "the way a diver breaks the surface"
- `moved like`, `felt like`, `sounded like`, `looked like`, `seemed like`
- `resembled`, `reminded [him/her] of` — softer similes but still comparisons
- `gave the impression of`, `had the air of` — formal simile-equivalents

A paragraph with two or more markers is a flag even before the individual check — it's either doing heavy voice work (author's deliberate style) or drowning the prose in decoration.

## Respect the Author Voice

**Some authors lean on similes deliberately. The check targets quality, not quantity.**

Character-driven voice authors often use grounded, everyday-life similes as a signature. These are *features*, not bugs:

- *"He stood there like a mall security guard who'd just been given actual authority."* — grounded, specific, reveals character.
- *"The apartment smelled like a Subway franchise had committed a crime in it."* — vivid, earns its place.

The failure mode isn't "too many similes." It's **illogical or decorative** similes. An author whose voice includes many concrete, funny, character-grounded similes is not violating discipline. An author whose voice uses "like a celestial beacon" is.

**Bias the check by profile:**
- If the author profile explicitly documents a simile-heavy style with examples, apply the two-question test with that register as context. A grounded simile in Ethan Cole's voice may pass where the same construction in a sparser author's voice would read as decoration.
- If the author profile is silent on similes or documents a sparse style, apply the test strictly. Default to cut-when-in-doubt.

Check `~/.storyforge/authors/{slug}/profile.md` and `~/.storyforge/authors/{slug}/vocabulary.md` for any simile-style notes.

## When Similes Earn Their Place

A simile is pulling its weight when it does at least one of:

- **Clarifies a sensation** the reader couldn't otherwise picture. (*"The cold hit him like stepping into a walk-in freezer — not pain, just the complete absence of warmth."*)
- **Reveals character** through the comparison's frame of reference. A soldier notices combat similes; a chef notices food similes; a nurse notices body similes. The vehicle tells the reader whose mind they're inside.
- **Lands a tonal beat** that bare description would miss. Humor, menace, grief — tone often travels in the space between tenor and vehicle.
- **Compresses what would otherwise take a paragraph.** A single strong simile can do the work of three sentences of description.

If none of those apply, the simile is decoration and should go.

## The Revision Move

When a simile fails the test, you have three options, in order of preference:

1. **Cut it entirely.** Replace with a concrete beat — what actually happens, what is actually seen, heard, smelled. This is almost always the right move.
2. **Replace the vehicle.** Keep the structure but swap the comparison for one that actually resembles the tenor.
3. **Keep it.** Only if, after honest rework, the simile still does real work.

Do not reach for option 3 because the sentence "sounds good." Sentences that sound good and do nothing are the specific problem this document exists to prevent.

## Pre-Save Checklist

Before any scene is appended to `draft.md`:

- [ ] Every `like`, `as if`, `as [adj] as`, `the way [X]` construction has been inspected.
- [ ] Each surviving simile passes both questions: *literal resemblance?* and *real work?*
- [ ] No paragraph contains stacked decorative similes.
- [ ] No dead similes (the familiar ones) survived.
- [ ] Author-voice register has been considered — the check is *quality*, not *quantity*.
- [ ] When in doubt, cut.

## Related

- `prose-style.md` — Metaphor and Simile: Fresh vs. Cliché, the Replacement Test.
- `anti-ai-patterns.md` — Purple prose on demand, hollow sophistication.
- `show-dont-tell.md` — Why concrete sensation beats decorative comparison.
