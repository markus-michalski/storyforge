---
name: create-testdata
description: |
  Creates disposable zz-sandbox- prefixed test fixtures (one author, one fiction book,
  one memoir book, three memoir persons) via storyforge's own real MCP tools, for
  skill-rollout's live-tier sandbox testing. Enforces a zz-sandbox- prefix gate before
  touching anything. After creating all fixtures, commits them to the book-projects git
  repo and updates the sandbox-baseline tag so reset-testdata can restore to this state.
  Use when: (1) skill-rollout's onboarding or rollout pipeline needs sandbox fixtures for
  this plugin, (2) explicit "/storyforge:create-testdata". Never triggers from ordinary
  conversation — this is machine-invoked test infrastructure, not a user-facing feature.
model: claude-sonnet-5
user-invocable: true
disable-model-invocation: true
---

# Create Test Data

Creates the `zz-sandbox-` disposable fixture set via storyforge's real creation tools —
never hand-written files, so there is no schema-drift risk between the fixture and what the
plugin's own tools actually produce. After creation, commits the book-project files to the
`book-projects` git repo and updates the `sandbox-baseline` tag so that `reset-testdata`
can restore to this exact state. Companion skills: `reset-testdata`, `delete-testdata`.
Full convention: skill-rollout's `reference/self-improving-skills.md`, section
"create-testdata / reset-testdata / delete-testdata Convention" (skill-rollout#35).

## Fixed fixture identifiers

- Author: slug `zz-sandbox-author` (name "ZZ Sandbox Author")
- Fiction book: slug `zz-sandbox-book` (title "ZZ Sandbox Book")
- Memoir book: slug `zz-sandbox-book-memoir` (title "ZZ Sandbox Book Memoir")
- Memoir person — consented: slug `zz-sandbox-person-consented`
- Memoir person — pending: slug `zz-sandbox-person-pending`
- Memoir person — refused: slug `zz-sandbox-person-refused`

These exact slugs are the whole contract — `reset-testdata` and `delete-testdata` operate
on exactly these names. Do not vary them.

## Workflow

### 1. Prefix gate — mandatory, first, unconditional

Before calling any MCP tool: confirm every identifier this skill is about to create starts
with the literal `zz-sandbox-` prefix (all six fixed names above do, by construction). If
ever asked to create a fixture under any other name, refuse and stop — never create test
data outside the `zz-sandbox-` namespace.

### 2. Refuse to duplicate — check existence first

Call `get_author("zz-sandbox-author")`. If the author already exists, refuse and stop:
report that the sandbox is already provisioned and instruct the caller to run
`delete-testdata` first.

Also call `get_book_full("zz-sandbox-book")` and `get_book_full("zz-sandbox-book-memoir")`.
If either book already exists (no `error` key in the response), refuse and stop with the
same message — never attempt to create over an existing fixture.

### 3. Create the author

```
create_author(
  name="ZZ Sandbox Author",
  genres="thriller",
  voice="third-limited",
  tense="past",
)
```

Check the return value. If it contains an `error` key, stop and report the error.

### 4. Create the fiction book

```
create_book_structure(
  title="ZZ Sandbox Book",
  author="zz-sandbox-author",
  genres="thriller",
  book_type="short-story",
  book_category="fiction",
  language="en",
  target_word_count=5000,
)
```

Check the return value for `error` and stop if present.

### 5. Create the memoir book

```
create_book_structure(
  title="ZZ Sandbox Book Memoir",
  author="zz-sandbox-author",
  genres="drama",
  book_type="short-story",
  book_category="memoir",
  language="en",
  target_word_count=5000,
)
```

Check the return value for `error` and stop if present.

### 6. Create the three memoir persons

These three persons cover the `consent_status` values that memoir-ethics-checker and related
skills need to test. Check each return value for `error` and stop on first failure.

```
create_person(
  book_slug="zz-sandbox-book-memoir",
  name="ZZ Sandbox Person Consented",
  relationship="sister",
  person_category="private-living-person",
  consent_status="confirmed-consent",
)

create_person(
  book_slug="zz-sandbox-book-memoir",
  name="ZZ Sandbox Person Pending",
  relationship="former colleague",
  person_category="private-living-person",
  consent_status="pending",
)

create_person(
  book_slug="zz-sandbox-book-memoir",
  name="ZZ Sandbox Person Refused",
  relationship="childhood neighbor",
  person_category="private-living-person",
  consent_status="refused",
)
```

### 7. Commit and update sandbox-baseline tag

Get the book directory path via `resolve_path("zz-sandbox-book", "")` — the returned
`path` is the full book project directory (e.g. `.../book-projects/projects/zz-sandbox-book`).
From that path, derive the git repo root by running:

```bash
git -C "<returned_path>" rev-parse --show-toplevel
```

This avoids fragile path-arithmetic and correctly finds the repo root regardless of the
directory structure. Confirm the command succeeds (exit 0) before proceeding.

Stage, commit, and re-tag — using `--allow-empty` to survive a "nothing to commit" case
(which can happen if the fixtures were just deleted and recreated with identical content):

```bash
git -C "<git_root>" add -- projects/zz-sandbox-book projects/zz-sandbox-book-memoir
git -C "<git_root>" commit --allow-empty -m "testdata: provision zz-sandbox fixtures for skill-rollout (storyforge#431)"
git -C "<git_root>" tag -f sandbox-baseline
```

The `-f` force-updates the tag if it already exists. This is intentional: the tag always
points at the current, just-created state so that `reset-testdata` restores to exactly what
this skill produced, not to a stale prior run.

### 8. Confirm and report

Independently re-read what was just created:
- `get_author("zz-sandbox-author")` — must succeed (no `error` key)
- `get_book_full("zz-sandbox-book")` — must succeed, `book_category` must be `fiction`
- `get_book_full("zz-sandbox-book-memoir")` — must succeed, `book_category` must be `memoir`
- `check_memoir_consent("zz-sandbox-book-memoir")` — must list all three persons with their consent statuses

Never trust the create calls' own return values as the only evidence the entities persisted.

```
## Test-Fixtures angelegt

**Author:** zz-sandbox-author
**Fiction book:** zz-sandbox-book
**Memoir book:** zz-sandbox-book-memoir
**Memoir persons:** zz-sandbox-person-consented, zz-sandbox-person-pending, zz-sandbox-person-refused
**sandbox-baseline tag:** updated to HEAD
```

Return these slugs as the skill's result — skill-rollout's onboarding and rollout pipeline
record them.
