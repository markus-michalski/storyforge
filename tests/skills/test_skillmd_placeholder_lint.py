"""Repo-wide placeholder-consistency lint for SKILL.md files.

Issue #381 was an undefined `{title}` template placeholder in
`backfill-style-principles/SKILL.md`: Step 5.1 referenced `{title}` when the
only variable that step's own flow ever derives is `{book_slug}` (from
Step 4). No test would have caught that class of bug before it shipped.

This lint scans every `skills/*/SKILL.md` for `{snake_case}` placeholders
inside backtick-wrapped text (code spans/blocks — the shape the #381 bug
had: `` `[{title}]` ``, `` `analysis-{title}.md` ``) and flags any token that
never appears as a bare word (no surrounding braces) anywhere else in the
same file. A bare-word appearance means the skill's own prose establishes
that identifier somewhere (a step deriving it, an MCP call using it as a
parameter, etc.) — exactly what `{title}` was missing in #381 (only
`book_slug` was ever established).

Manually triaged against all 51 skills at introduction time (2026-07):
64 tokens across 31 skills were flagged by the raw heuristic. Every single
one turned out to be a false positive, falling into one of two legitimate
categories — the ALLOWLISTs below encode that triage so this lint starts
green and only fires on genuinely new occurrences of the #381 bug shape:

1. Plugin-wide path conventions documented in the plugin root's CLAUDE.md
   (`{project}`, `{plugin_root}`, `{content_root}`) — established by
   repo-wide convention, not by any single skill's local prose.
2. Report-template / per-item loop placeholders (e.g. `{total_new}`,
   `{n_accepted}`, `{book_title}`, `{count}`, `{date}`) — these represent
   "insert a computed value or an MCP-returned field here" in a display
   template (e.g. "For each idea, show: **{title}**" where `title` is a
   field on the MCP tool's return object, not a locally-derived variable).
   Their meaning is self-evident from the immediately surrounding label
   text, unlike #381's `{title}`, which silently pointed at nothing.

Adding a new placeholder to a skill that this lint flags is NOT
automatically wrong — it usually means it belongs in one of the two
categories above. Verify it actually resolves to something (an MCP field,
a locally-derived variable, or a documented plugin-wide convention) before
adding it to the per-skill allowlist with a short reason. If it doesn't
resolve to anything, that's a live instance of the #381 bug class — fix
the skill instead of allowlisting it.

**Coverage limit — read before trusting a clean run on a new skill.**
Definedness is a bare-word text search, not real variable-binding analysis.
A token that also happens to be an ordinary English word appearing
elsewhere in the same skill's code spans (e.g. "title", "type", "context")
will be treated as "established" even if that occurrence has nothing to do
with the placeholder — this lint would NOT have caught #381 in a skill that
happened to also use the bare word "title" for something else. Coverage is
strongest for distinctive, unambiguous identifiers (`book_slug`,
`tracker_slug`) and weakest for common words. Treat a clean run as "no
*obviously* undefined placeholder," not a full definedness proof.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

PLUGIN_ROOT = Path(__file__).resolve().parent.parent.parent
SKILLS_DIR = PLUGIN_ROOT / "skills"

FRONTMATTER_RE = re.compile(r"^---\s*\n(.*?)\n---\s*\n", re.DOTALL)
# Includes hyphens: slugs across this plugin are hyphen-heavy ({book-slug},
# analysis-{title}.md), so a #381-shaped bug written with a hyphenated token
# must be visible to this scan too, not just underscore-style tokens.
PLACEHOLDER_RE = re.compile(r"\{([a-z][a-z0-9_-]*)\}")

# Category 1 — plugin-wide path conventions documented in the plugin root's
# CLAUDE.md ("Configuration" / "Project Structure" sections): {project} and
# {plugin_root} are defined there directly; {content_root} and {series} are
# the same family (content_root/projects/{slug}/ and content_root/series/
# {name}/ — see "Project Structure"). Plus the generic single-letter count
# convention ({n}, as in "Candidate {n}/{total}") used across many report
# templates. Legal in any skill, no per-skill listing.
GLOBAL_ALLOWLIST: set[str] = {"project", "plugin_root", "content_root", "series", "n"}

# Category 2 — report-template / per-item loop placeholders, verified per
# skill at introduction time. Each value is a computed count, an MCP-field
# echo, or a documented format-string component; none reference a variable
# that should have been named differently.
PER_SKILL_ALLOWLIST: dict[str, set[str]] = {
    "author-check": {"date"},
    "backfill-promises": {"p", "u", "un", "total"},
    "backfill-style-principles": {"total_new", "total_skipped"},
    "bootstrap-book-from-series": {"n_accepted", "n_edited", "n_new", "n_skipped", "n_with_prior"},
    "chapter-proofreader": {"count"},
    "continuity-checker": {"date"},
    "emotional-truth-prompt": {"chapter-path"},  # slug-in-file-path, self-evident from "{chapter-path}/draft.md"
    "harvest-author-rules": {"idx"},
    "harvest-character-evolution": {
        "n_accepted",
        "n_edited",
        "n_empty",
        "n_kept",
        "n_skipped",
        "n_with_existing",
        "next_book_slug",
        "proposed_summary",
        "recurs_in",
    },
    "ideas": {"logline", "title"},
    "new-book": {"prev", "tracker_slug"},
    "promote-rule": {"date", "from_scope", "source_file", "target_file", "to_scope"},
    "report-issue": {"book_title", "chapter_number"},
    "researcher": {"topic-slug"},  # slug-in-file-path, self-evident from "{topic-slug}.md"
    "rules-audit": {"book_title", "code", "count", "index", "message", "raw_text"},
    "series-planner": {"title", "book-level-slug", "tracker-slug"},  # tracker/book-level-slug: kwarg-value placeholders in a code example, self-evident from inline comments
    "study-author": {"approximate", "date", "theme", "word"},
    "translator": {"lang", "chapter-slug"},  # slug-in-file-path, self-evident from "{chapter-slug}.md"
    "world-builder": {"location-slug"},  # slug-in-file-path, self-evident from "setting-{location-slug}.md"
}


def _read_frontmatter_and_body(path: Path) -> tuple[str, str]:
    text = path.read_text(encoding="utf-8")
    m = FRONTMATTER_RE.match(text)
    if not m:
        return "", text
    return m.group(1), text[m.end() :]


def _find_backtick_spans(body: str) -> list[str]:
    blocks = re.findall(r"```.*?```", body, re.DOTALL)
    spans = re.findall(r"`([^`\n]+)`", body)
    return blocks + spans


def _is_bare_word_present(token: str, *texts: str) -> bool:
    # Split on both '_' and '-': the codebase mixes book_slug (Python-style
    # variable) and book-slug (filesystem/URL-slug style) for the same
    # concept, so normalize both to the same [-_] class before matching.
    parts = [re.escape(p) for p in re.split(r"[_-]", token)]
    pattern = re.compile(r"(?<!\{)\b" + r"[-_]".join(parts) + r"\b(?!\})", re.IGNORECASE)
    return any(pattern.search(text) for text in texts)


def _flagged_tokens_for_skill(skill_dir: Path) -> list[str]:
    skill_md = skill_dir / "SKILL.md"
    if not skill_md.is_file():
        return []
    frontmatter, body = _read_frontmatter_and_body(skill_md)
    code_text = "\n".join(_find_backtick_spans(body))
    tokens = set(PLACEHOLDER_RE.findall(code_text))

    allowed = GLOBAL_ALLOWLIST | PER_SKILL_ALLOWLIST.get(skill_dir.name, set())
    tokens -= allowed

    # Definedness is checked against code_text only, not the full prose body.
    # An ordinary English word that happens to match a placeholder's spelling
    # (e.g. "title" appearing in plain prose like "the book's title") must
    # NOT count as establishing {title} as a variable — that's exactly the
    # #381 bug shape, where {title} was never actually bound to anything.
    # Genuine established variables in this codebase are always introduced
    # inside backtick-wrapped MCP calls or code spans (e.g.
    # `get_chapter_writing_brief(book_slug, chapter_slug)`), so restricting
    # the search to code_text + frontmatter (argument-hint) is deliberate,
    # not an oversight.
    return sorted(tok for tok in tokens if not _is_bare_word_present(tok, code_text, frontmatter))


def _all_skill_dirs() -> list[Path]:
    return sorted(p for p in SKILLS_DIR.iterdir() if (p / "SKILL.md").is_file())


class TestPlaceholderLint:
    @pytest.mark.parametrize("skill_dir", _all_skill_dirs(), ids=lambda p: p.name)
    def test_no_undefined_placeholders(self, skill_dir: Path) -> None:
        flagged = _flagged_tokens_for_skill(skill_dir)
        assert not flagged, (
            f"{skill_dir.name}/SKILL.md references undefined template "
            f"placeholder(s) {flagged} — not established anywhere in the "
            f"skill's own prose, not an MCP-field echo, and not a documented "
            f"plugin-wide convention. This is the #381 bug class (undefined "
            f"{{title}} — should have been {{book_slug}}). Either fix the "
            f"reference to use the correct established variable, or if this "
            f"is a legitimate report-template/MCP-field placeholder, add it "
            f"to PER_SKILL_ALLOWLIST in this test with a one-line reason."
        )

    def test_backfill_style_principles_regression(self) -> None:
        # Direct regression guard for the exact bug #381 fixed — kept
        # alongside the general lint so this specific case stays pinned
        # even if the general heuristic's allowlists are ever refactored.
        # Deliberately over-constrained versus the general lint: this bans
        # {title} outright in this one file, even if {title} were ever a
        # legitimate MCP-field placeholder here in the future (it wasn't at
        # introduction time, and #381's specificity makes an outright ban
        # the simplest guard). If that ever changes, scope this assertion
        # to the offending step instead of loosening it wholesale.
        body = (SKILLS_DIR / "backfill-style-principles" / "SKILL.md").read_text(encoding="utf-8")
        assert "{title}" not in body

    def test_per_skill_allowlist_keys_match_real_skills(self) -> None:
        # Catches a typo'd or stale PER_SKILL_ALLOWLIST key silently going
        # dead (e.g. after a skill rename) — without this, a maintainer who
        # thinks a token is allowlisted would get a confusing "undefined
        # placeholder" failure instead of a clear "this allowlist key
        # doesn't match any skill" one.
        real_skill_names = {p.name for p in _all_skill_dirs()}
        stale_keys = set(PER_SKILL_ALLOWLIST) - real_skill_names
        assert not stale_keys, (
            f"PER_SKILL_ALLOWLIST has key(s) {stale_keys} that don't match "
            f"any skills/*/ directory — typo, or the skill was renamed/removed."
        )
