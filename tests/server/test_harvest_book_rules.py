"""Tests for the ``harvest_book_rules`` MCP tool (Issue #151).

The tool composes:

- book CLAUDE.md ``## Rules`` → list_rules → classify_rule
- author profile + vocabulary → dedup target
- world terms from world/glossary.md + plot/canon-log.md + character names →
  world_rule classifier input

It does NOT run manuscript-checker inline (that's a slow, separate step
the skill orchestrates). Manuscript findings can be passed in via the
optional ``findings_path`` argument that points to a pre-computed report.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

import routers._app as _app
from routers.authors import harvest_book_rules
from routers.claudemd import init_book_claudemd, append_book_rule


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def book_with_rules(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> dict:
    """Set up a book + author + content_root and patch load_config."""
    content_root = tmp_path / "books"
    book_dir = content_root / "projects" / "firelight"
    book_dir.mkdir(parents=True)
    (book_dir / "README.md").write_text(
        '---\ntitle: "Firelight"\nauthor: "ethan-cole"\nstatus: "Revision"\n'
        'book_category: "fiction"\n---\n# Firelight\n',
        encoding="utf-8",
    )

    # World glossary + canon-log so world-term detection can mark book canon.
    world_dir = book_dir / "world"
    world_dir.mkdir()
    (world_dir / "glossary.md").write_text(
        "# Glossary\n\n- **Lykos** — fire-aware predator species.\n"
        "- **Fire affinity** — innate connection to flame.\n",
        encoding="utf-8",
    )

    # Author home with profile + vocabulary.
    author_home = tmp_path / ".storyforge"
    authors_root = author_home / "authors"
    authors_dir = authors_root / "ethan-cole"
    authors_dir.mkdir(parents=True)
    (authors_dir / "profile.md").write_text(
        '---\nname: "Ethan Cole"\nslug: "ethan-cole"\n---\n\n'
        "# Ethan Cole\n\n## Writing Discoveries\n\n"
        "### Recurring Tics\n\n_Frei._\n\n"
        "### Style Principles\n\n_Frei._\n\n"
        "### Don'ts (beyond banned phrases)\n\n_Frei._\n",
        encoding="utf-8",
    )
    (authors_dir / "vocabulary.md").write_text(
        "# Ethan Cole — Vocabulary\n\n## Banned Words\n\n### Absolutely Forbidden\n\n- delve\n",
        encoding="utf-8",
    )

    config = {
        "paths": {
            "content_root": str(content_root),
            "authors_root": str(authors_root),
        },
    }
    monkeypatch.setattr(_app, "load_config", lambda: config)

    # Initialize CLAUDE.md so list_rules has markers.
    init_book_claudemd("firelight", book_title="Firelight")

    return {
        "config": config,
        "book_dir": book_dir,
        "author_dir": authors_dir,
    }


# ---------------------------------------------------------------------------
# Smoke test — empty book
# ---------------------------------------------------------------------------


class TestEmptyBook:
    def test_returns_zero_candidates_for_book_without_rules(self, book_with_rules, monkeypatch):

        result = json.loads(harvest_book_rules("firelight"))

        assert result["book_slug"] == "firelight"
        assert result["candidates"] == []
        assert result["summary"]["total"] == 0


# ---------------------------------------------------------------------------
# Book-rule sourcing
# ---------------------------------------------------------------------------


class TestBookRuleSourcing:
    def test_picks_up_book_rules_and_classifies(self, book_with_rules, monkeypatch):

        # Append three rules of distinct types.
        append_book_rule("firelight", "Avoid `math` — Theo's analytical metaphor tic.")
        append_book_rule(
            "firelight",
            "Avoid `[Character] moved to [location]` — author default blocking pattern.",
        )
        append_book_rule(
            "firelight",
            "Lykos can sense fire affinity by scent — magic-system canon.",
        )

        result = json.loads(harvest_book_rules("firelight"))
        types = {c["type"] for c in result["candidates"]}
        assert "banned_phrase" in types
        assert "style_principle" in types
        assert "world_rule" in types

    def test_world_term_rule_recommends_keep_book_only(self, book_with_rules, monkeypatch):

        append_book_rule(
            "firelight",
            "Lykos can sense fire affinity by scent — canon.",
        )
        result = json.loads(harvest_book_rules("firelight"))
        world_cands = [c for c in result["candidates"] if c["type"] == "world_rule"]
        assert len(world_cands) == 1
        assert world_cands[0]["recommendation"] == "keep_book_only"


# ---------------------------------------------------------------------------
# Author-side dedup
# ---------------------------------------------------------------------------


class TestAuthorDedup:
    def test_phrase_already_in_vocabulary_is_dropped(self, book_with_rules, monkeypatch):

        # `delve` is already in the author's vocabulary fixture.
        append_book_rule("firelight", "Avoid `delve` — generic AI tell.")
        result = json.loads(harvest_book_rules("firelight"))
        values = [c["value"] for c in result["candidates"]]
        assert "delve" not in values

    def test_explicit_author_slug_overrides_book_author(self, book_with_rules, monkeypatch):

        # Pass a different author_slug; if the resolver respects it, dedup
        # should not match (different vocabulary).
        append_book_rule("firelight", "Avoid `delve` — generic AI tell.")
        result = json.loads(harvest_book_rules("firelight", author_slug="someone-else"))
        # someone-else doesn't exist → no dedup possible → candidate kept.
        values = [c["value"] for c in result["candidates"]]
        assert "delve" in values


# ---------------------------------------------------------------------------
# Output shape — must match the issue spec
# ---------------------------------------------------------------------------


class TestOutputShape:
    def test_response_has_required_top_level_fields(self, book_with_rules, monkeypatch):

        append_book_rule("firelight", "Avoid `math` — Theo's tic.")
        result = json.loads(harvest_book_rules("firelight"))
        assert set(result.keys()) >= {"book_slug", "author_slug", "candidates", "summary"}
        assert set(result["summary"].keys()) >= {
            "total",
            "recommended_promote",
            "recommended_keep_book",
        }

    def test_candidate_has_required_fields(self, book_with_rules, monkeypatch):

        append_book_rule("firelight", "Avoid `math` — Theo's tic.")
        result = json.loads(harvest_book_rules("firelight"))
        cand = result["candidates"][0]
        for key in ("id", "type", "value", "recommendation", "rationale", "source", "target_section"):
            assert key in cand


# ---------------------------------------------------------------------------
# Error handling
# ---------------------------------------------------------------------------


class TestErrorHandling:
    def test_unknown_book_returns_error(self, book_with_rules, monkeypatch):

        result = json.loads(harvest_book_rules("nonexistent-book"))
        assert "error" in result
