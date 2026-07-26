---
name: reset-testdata
description: |
  Resets the zz-sandbox- test fixtures back to their documented baseline state, without
  deleting them (author is deleted and immediately recreated for a clean profile reset),
  undoing whatever mutations a live-tier rollout run left behind. Enforces a zz-sandbox-
  prefix gate before touching anything. Uses git checkout against the sandbox-baseline
  tag for isolated book files (chapters, plot, characters, people), deletes per-book
  SQLite DBs so they are recreated fresh, and delete+recreates the author for a clean
  profile and zero discoveries. Use when: (1) skill-rollout's rollout pipeline needs a
  clean fixture state between runs, (2) explicit "/storyforge:reset-testdata". Never
  triggers from ordinary conversation — this is machine-invoked test infrastructure, not
  a user-facing feature.
model: claude-sonnet-5
user-invocable: true
disable-model-invocation: true
---

# Reset Test Data

Resets the `zz-sandbox-` fixtures back to a verified baseline state, **without destroying
the fixture set** — the end result is identical to a fresh `create-testdata` run, but
faster and without re-tagging. Companion skills: `create-testdata`, `delete-testdata`.
Full convention: skill-rollout's `reference/self-improving-skills.md`, section
"create-testdata / reset-testdata / delete-testdata Convention" (skill-rollout#35).

## Reset strategy by storage type

| Storage | Entities | Strategy |
|---------|----------|----------|
| Isolated files per book (book project dirs) | `zz-sandbox-book/`, `zz-sandbox-book-memoir/` | `git checkout sandbox-baseline -- <paths>` + `git clean -fdx -- <paths>` |
| Per-book SQLite DBs | `~/.storyforge/db/zz-sandbox-book.db`, `zz-sandbox-book-memoir.db` | Delete; MCP server creates them fresh on next access |
| Isolated author profile file + all author dirs | `~/.storyforge/authors/zz-sandbox-author/` | Delete author entirely + recreate via `create_author()` |
| Shared `authors.db` (author_discoveries) | All rows for `zz-sandbox-author` | Automatically wiped when `delete_author()` runs, so recreated clean |

**Why delete+recreate the author instead of field-by-field update:**
`update_author()` can only set listed fields, not remove them. Skills like `study-author`
can add new fields (`dialog_ratio_target`, `subject_position`, `off_limits`, etc.) that
`update_author()` cannot later clear. Delete+recreate guarantees the profile is byte-for-byte
identical to what `create_author()` produces — no accumulated drift, no zombie fields, no
orphaned discovery rows.

Book project directories are isolated per-book in the git repo — a path-scoped `git
checkout` only touches files under those two directories and cannot affect any real book.
`git clean -fdx` removes any files (including git-ignored ones like export output and
generated PDFs) added by live tests that are not in the tag.

**Full-book blast radius** (Issues #434, #450): the `git checkout sandbox-baseline + git clean -fdx`
reset is a **whole-directory restore** — it wipes every chapter dir (including `chapters/`
dirs added by prior skill-rollout live-tier runs) and resets the author profile and all
writing-discovery rows. Any `sandbox.md` file that documents a chapter fixture or author
field as "persistent baseline going forward" is only valid until the next `reset-testdata`
or `create-testdata` run; those conventions predate this full-reset strategy. Before trusting
a prior skill's documented baseline: re-verify the files actually exist on disk and in git
(`git ls-files <path>`), and call `get_author("zz-sandbox-author")` for the authoritative
current author state, rather than assuming anything survived the last reset.

## Workflow

### 1. Prefix gate — mandatory, first, unconditional

Before calling any MCP tool: confirm the targets are exactly `zz-sandbox-author`,
`zz-sandbox-book`, and `zz-sandbox-book-memoir` — all carry the `zz-sandbox-` prefix. If
ever asked to reset anything else, refuse and stop.

### 2. Confirm the fixtures exist

Call `get_author("zz-sandbox-author")`. If not found, refuse and stop: report there is
nothing to reset and instruct the caller to run `create-testdata` first.

### 3. Delete and recreate the author

Delete first — this wipes the profile directory, all writing discoveries, and all entries
in `authors.db` for this author in one call:

```
delete_author(slug="zz-sandbox-author", force=True)
```

`force=True` is required because the sandbox books still reference this author slug. Check
the return value — if it contains `error`, stop and report.

Recreate immediately with the same parameters as `create-testdata` used:

```
create_author(
  name="ZZ Sandbox Author",
  genres="thriller",
  voice="third-limited",
  tense="past",
)
```

Check the return value for `error` and stop if present.

### 4. Delete the per-book SQLite DBs

These files store `canon_facts`, `character_snapshots`, and `book_rules` for each book.
Deleting them lets the MCP server create them fresh (empty) on next access — this is safe
because the per-book DB path is derived from the book slug and is recreated automatically.

```bash
rm -f ~/.storyforge/db/zz-sandbox-book.db
rm -f ~/.storyforge/db/zz-sandbox-book-memoir.db
```

### 5. Git-restore the book files

Get the book directory path via `resolve_path("zz-sandbox-book", "")`. Derive the git
repo root:

```bash
git -C "<returned_path>" rev-parse --show-toplevel
```

Verify the tag exists: `git -C "<git_root>" tag -l sandbox-baseline` — if the output is
empty, stop and report that the baseline tag is missing; the operator must run
`create-testdata` first to re-establish it.

Then restore:

```bash
git -C "<git_root>" checkout sandbox-baseline -- projects/zz-sandbox-book projects/zz-sandbox-book-memoir
git -C "<git_root>" clean -fdx -- projects/zz-sandbox-book projects/zz-sandbox-book-memoir
```

The `checkout` restores tracked files to their tag-time content. The `clean -fdx` removes
all untracked and git-ignored files added by live tests (extra chapter dirs, generated
export files, PDFs, etc.).

### 6. Rebuild state cache

Call `rebuild_state()` after the git restore and DB deletion so the MCP server reflects
the now-restored state.

### 7. Confirm and report

Independently re-read all three entities after rebuild:
- `get_author("zz-sandbox-author")` — must succeed, `primary_genres` must contain `thriller`, zero discoveries in `writing_discoveries`
- `get_book_full("zz-sandbox-book")` — must succeed, `book_category` must be `fiction`
- `get_book_full("zz-sandbox-book-memoir")` — must succeed, `book_category` must be `memoir`
- `check_memoir_consent("zz-sandbox-book-memoir")` — must list all three persons

All three fixture entities must still exist after reset — `reset-testdata` restores, it
does not destroy. The author recreation in step 3 satisfies this: the author is back with
a clean profile.

```
## Test-Fixtures zurückgesetzt

**Author:** zz-sandbox-author — gelöscht und sauber neu angelegt (Profile + Discoveries auf Baseline)
**Fiction book:** zz-sandbox-book — git checkout sandbox-baseline + git clean -fdx
**Memoir book:** zz-sandbox-book-memoir — git checkout sandbox-baseline + git clean -fdx
**Per-book DBs:** zz-sandbox-book.db + zz-sandbox-book-memoir.db — gelöscht (werden leer neu angelegt)
```
