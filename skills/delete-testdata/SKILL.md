---
name: delete-testdata
description: |
  Fully tears down the zz-sandbox- test fixtures (author, all zz-sandbox- book dirs,
  per-book SQLite DBs), for a clean decommission or full reset. Idempotent: a call against
  an already-empty sandbox is a clean no-op, never an error. Enforces an unconditional
  zz-sandbox- prefix gate before any tool call or lookup — the highest-blast-radius of
  the three testdata skills and the one skill-rollout's onboarding live-verifies first.
  Use when: (1) skill-rollout's rollout pipeline or onboarding live-verification needs to
  tear down or verify this guard, (2) explicit "/storyforge:delete-testdata". Never
  triggers from ordinary conversation.
model: claude-sonnet-5
user-invocable: true
disable-model-invocation: true
---

# Delete Test Data

Fully removes the `zz-sandbox-` fixture set. This is the **highest blast radius** of the
three testdata skills — it is the one skill-rollout's onboarding calls with a synthetic,
provably-nonexistent, non-prefixed slug to live-verify the prefix guard actually works
before trusting any of the three skills for automated use. Companion skills:
`create-testdata`, `reset-testdata`. Full convention: skill-rollout's
`reference/self-improving-skills.md`, section "create-testdata / reset-testdata /
delete-testdata Convention" (skill-rollout#35).

## Argument

`target` (optional, defaults to `zz-sandbox-author`) — used exclusively as the prefix
gate's test subject. The actual teardown always operates on the fixed fixture set
(`zz-sandbox-author`, `zz-sandbox-book`, `zz-sandbox-book-memoir`, and any other
`zz-sandbox-book-*` dirs present). Pass any non-`zz-sandbox-`-prefixed slug to
live-verify the gate fires before any tool call — that is exactly how skill-rollout's
onboarding checks this skill.

## Workflow

### 1. Prefix gate — mandatory, first, unconditional, before ANY tool call

Confirm `target` starts with the literal `zz-sandbox-` prefix. **If it does not, refuse
and stop immediately — do not call `get_author`, do not resolve any path, do not call
anything else.** This is the exact check skill-rollout's onboarding live-verifies: it
calls this skill once with a synthetic, provably-nonexistent, non-`zz-sandbox-` slug and
expects this refusal to fire before any lookup happens. Never weaken this to "check after
looking it up" — the whole safety property depends on refusing before any tool call can
touch real data.

### 2. Look up the author — detect empty-sandbox no-op

Call `get_author("zz-sandbox-author")`. If not found, skip steps 4 (author delete) and
proceed directly to step 3 — book dirs and DBs may still exist even when the author
profile is absent, and cleanup must run regardless. Report at the end that the author
was not found but cleanup of remaining artifacts ran.

### 3. Remove book project directories and per-book SQLite DBs

Get the path to `zz-sandbox-book` via `resolve_path("zz-sandbox-book", "")`. If the
returned `path` does not exist (`exists: false`), skip the `rm -rf` calls for book dirs
— do not error.

For each known `zz-sandbox-book-*` directory, verify its final path component starts with
`zz-sandbox-` before deleting. `resolve_path` already validates containment within
`content_root` (Issue #116), providing defense-in-depth.

```bash
# Resolve paths:
resolve_path("zz-sandbox-book", "")          # → {"path": ".../projects/zz-sandbox-book", ...}
resolve_path("zz-sandbox-book-memoir", "")   # → {"path": ".../projects/zz-sandbox-book-memoir", ...}

# Delete book dirs (only if exists and final component starts with "zz-sandbox-"):
rm -rf ".../projects/zz-sandbox-book"
rm -rf ".../projects/zz-sandbox-book-memoir"

# Also clean up legacy per-skill sandbox books if present (left over from pre-#431 rollouts):
# Check each with resolve_path first before deleting
resolve_path("zz-sandbox-book-chars", "")    # skip if {"exists": false}
resolve_path("zz-sandbox-book-plot", "")     # skip if {"exists": false}
rm -rf ".../projects/zz-sandbox-book-chars"  # only if exists and has zz-sandbox- prefix
rm -rf ".../projects/zz-sandbox-book-plot"   # only if exists and has zz-sandbox- prefix
```

Delete per-book SQLite DBs (these live in `~/.storyforge/db/` outside content_root):

```bash
rm -f ~/.storyforge/db/zz-sandbox-book.db
rm -f ~/.storyforge/db/zz-sandbox-book-memoir.db
rm -f ~/.storyforge/db/zz-sandbox-book-chars.db
rm -f ~/.storyforge/db/zz-sandbox-book-plot.db
```

### 4. Delete the author

Only run this step if step 2 found the author. If step 2 found nothing, skip to step 5.

```
delete_author(slug="zz-sandbox-author", force=True)
```

`force=True` prevents the "books still reference this author" guard from blocking the
delete — book dirs were already removed in step 3.

Check the return value. If it contains `error`, stop and report.

### 5. Rebuild state cache

Call `rebuild_state()` so the MCP server reflects the now-empty sandbox.

### 6. Confirm via independent reads

Call `get_author("zz-sandbox-author")` and confirm it returns `{"error": ...}` (not
found). Never trust step 4's return value as the only evidence of deletion.

```
## Test-Fixtures entfernt

**Author:** zz-sandbox-author — gelöscht
**Book dirs:** projects/zz-sandbox-book + zz-sandbox-book-memoir — entfernt
**Legacy book dirs:** zz-sandbox-book-chars + zz-sandbox-book-plot — entfernt (falls vorhanden)
**Per-book DBs:** ~/.storyforge/db/zz-sandbox-book*.db — entfernt
```

If step 2 found no author AND step 3 found no book dirs AND no DBs existed, report:

```
## Keine Test-Fixtures vorhanden

Nichts zu löschen — sandbox war bereits leer.
```
