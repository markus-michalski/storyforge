---
book_categories: [memoir]
craft_topic: ethics-and-legal
status: stable
last_reviewed: 2026-04-27
---

# Real People in Memoir — Ethics and Legal

Memoir puts real people on the page. Some consent. Some can't. Some won't
like it. A few may sue. This doc covers the practical ethics and the
working legal categories. **It is not legal advice.** When the stakes are
high — a named living person, a damaging claim, a powerful subject —
consult an actual publishing lawyer before you publish.

This doc is the working framework that StoryForge skills (especially the
forthcoming `memoir-ethics-checker`, #65) use to flag risk and prompt
consent decisions.

## The four-category model

Every named real person in a memoir falls into one of these:

| Category | Defines | Typical risk | Consent posture |
|----------|---------|--------------|-----------------|
| **Public figure** | Politician, celebrity, named author of a public work | Lower — public conduct is fair game; private life is not | Not required for public conduct; required for private claims |
| **Private living person** | Anyone not a public figure | Highest — defamation + privacy claims live here | Strongly recommended; sometimes mandatory |
| **Deceased person** | Person no longer living | Lower — defamation typically does not survive death | Not required, but consider survivors' feelings |
| **Anonymized / composite** | Person whose identity you have actively obscured or merged | Lower if anonymization holds | Disclose convention in author's note |

Tag each person in `characters/` (or `people/`, post-#59) with their
category and a `consent_status` field:

- `confirmed-consent` — you have asked, they have said yes (ideally in
  writing for a high-stakes portrayal)
- `pending` — you intend to ask before publication; not yet asked
- `not-required` — public figure on public matters, deceased, or fully
  anonymized
- `refused` — you asked, they said no — see "When consent is refused"
- `not-asking` — deliberate choice not to ask (estranged relationship,
  abuser, etc.) — see "When you're not asking"

## Defamation, in two paragraphs

A defamation claim in most common-law jurisdictions requires: (1) a false
statement of fact (2) about an identifiable person (3) communicated to a
third party (4) causing harm. Opinion is generally protected; truth is
generally a complete defense; substantial truth (the gist is true even if
details differ) is usually enough.

The traps for memoirists:

- **Compressed time** can convert a defensible characterization into an
  indefensible one. "He drank too much, that year" is different from "He
  was an alcoholic". Be precise about scope.
- **Reconstructed dialogue** that puts a defamatory statement in someone's
  mouth they did not actually make is invention dressed as fact. Don't.
- **Mind-reading**: "He hated me" is opinion if framed as your perception;
  it can read as fact. Frame perceptions as perceptions.
- **Imputation of crime, professional incompetence, or sexual misconduct**
  raises the legal bar. These are *per se* defamatory in many
  jurisdictions if false. Verify, document, or strongly consider
  anonymization.

## Anonymization patterns that work

Light anonymization (changed name only) **often does not protect you** if
the person is identifiable from context — relationship, location,
occupation, distinctive events. Real anonymization changes enough that the
person could not be identified by anyone who knew them well.

Effective patterns:

- **Change the name plus 2–3 identifying facts** (occupation, city, hair
  color, age range, distinguishing physical detail). Pick ones that don't
  change the meaning of the story.
- **Conflate timing**. Move events by months or compress two encounters
  into one if it doesn't distort the felt sense.
- **Use "a friend" or "a colleague"** in summary if the person doesn't
  need to be on the page as a character. The reader doesn't need every
  name.
- **Disclose in an author's note** that "some names and identifying details
  have been changed" — this is standard memoir convention and does not
  weaken the work.

What does **not** count as anonymization:

- Changing only the first name when the person is your sister and you've
  said you have one sister.
- Calling someone "my boss" when you've named the small company in
  Chapter 2.
- Using initials.
- Vaguely distorting age or gender while keeping every other identifier.

## Composite characters

Merging two or more real people into one fictional character is **a
fabrication if undisclosed** in many readers' eyes (and increasingly in
publishers' contracts). The convention is:

- Use composites only when **necessary for narrative economy** (the story
  has six minor characters who collectively played one role; merge them
  into one).
- Never composite when the merged character carries **moral weight** the
  individuals did not. Don't merge a difficult-but-decent ex with an
  abusive ex into one character readers will read as the abuser.
- **Always disclose** in an author's note. "Some characters are composites
  of two or more people I knew" is standard.

If you are tempted to composite to obscure identity rather than for
narrative economy, you are anonymizing badly. Do real anonymization
instead.

## Consent in practice

When asking consent for a high-stakes portrayal of a private living
person:

1. **Show them the relevant passages**, not just describe them.
2. **Tell them what you cannot change** — the events as you remember
   them, the felt sense, the meaning. Tell them what you can — name,
   identifying details, dialogue specifics.
3. **Get it in writing if the portrayal is sensitive**. A simple "I have
   read the attached pages and consent to publication as written" email
   is enough for most cases.
4. **Don't promise approval rights over the whole book**. You retain
   editorial control; they are consenting to their portrayal.

When asking consent feels like it would damage the relationship:

- **Ask anyway** if you would not be okay publishing without consent.
- **Anonymize** if you would publish without consent but can render the
  story without identifying them.
- **Reconsider whether the story needs them on the page** if neither.

## When consent is refused

You have three ethical paths:

- **Honor the refusal**: cut or anonymize the portrayal.
- **Publish anyway because the story requires it and you accept the
  consequences**: relationship damage, possible legal exposure, possible
  reputational damage to you. Be clear-eyed about this; don't pretend
  you're being heroic.
- **Re-frame**: render the story from a different angle, summary instead
  of scene, perception instead of fact, in a way that no longer requires
  the disputed material.

Whichever path: **document the request and refusal**. If you publish
against refusal, you should be able to demonstrate that you considered
the harm.

## When you're not asking

There are situations — abuse, estrangement, ongoing harm — where asking
consent is itself unsafe or absurd. You don't owe consent to every
real person on every page. You do owe yourself clarity about why you
are not asking.

Working test: would a reasonable reader who learned why you didn't ask
agree it was a defensible choice? If yes, document the reasoning in your
project notes (not the book) and proceed. If no, ask anyway, even if
they refuse.

## Special cases

### Children
Particularly your own children. They cannot meaningfully consent to a
portrayal that will outlive their childhood. Anonymize aggressively, or
wait until they're old enough to consent.

### Therapists, doctors, lawyers
Their interactions with you are legally privileged from their side. From
your side, you can write what you want — but be precise. Quoting a
therapist saying something they did not say is the same defamation
problem as anyone else, with extra reputational weight.

### Public figures on private matters
Public figures' private lives are not "fair game" simply because they're
public. The First-Amendment protections that loosen defamation standards
on their public conduct don't extend to their private conduct.

### Group portraits — religion, family, ethnicity
You can write critically about the group you came from. You will hear
about it. This is not a legal matter; it is an emotional one. Decide in
advance whether you can sustain the response.

## The author's note

A memoir author's note typically covers:

- **Anonymization disclosure**: "Some names and identifying details have
  been changed."
- **Composite disclosure**: "X is a composite of two friends from that
  period" — or, more general, "Some characters are composites."
- **Time-compression disclosure**: "I have compressed events that took
  place over several months into a single chapter for narrative clarity."
- **Reconstructed dialogue**: "Dialogue is reconstructed from memory; it
  is the substance of conversations as I remember them, not a verbatim
  record."

These are not cop-outs. They are the conventions that make memoir
trustworthy. Skipping them does not make the work more honest; it makes
it less.

## What StoryForge skills enforce

Phase 1 (#54–#56, #67) does not yet branch on category. From Phase 3 on:

- `memoir-ethics-checker` (#65) flags named living people without
  `consent_status`, scans for *per se* defamation triggers, and warns on
  thin anonymization.
- `chapter-writer` in memoir mode (Phase 2 #57) prompts for consent
  status before drafting any scene with a named living person.
- The author's-note generation in `export-engineer` (Phase 4 #64)
  assembles the disclosure paragraphs from per-person `consent_status`
  values.

Until those land, this doc is your manual checklist.

## See also

- `book_categories/memoir/craft/emotional-truth.md` — dialogue convention, composites in context
- `book_categories/memoir/status-model.md` — consent gates between status transitions
- `book_categories/memoir/README.md` — overview
