"""Tests for the manuscript-checker global shape-bans scanner (Issue #213).

The scanner reads catalog-level shape regexes from
``reference/craft/anti-ai-patterns.md`` Section 11 via
``load_global_shape_bans``. Findings are emitted with
``category="global_shape_violation"`` and ``severity="medium"`` — advisory,
not user-asserted. Authors who want to hard-block a global shape can
override by adding the same regex to their profile's ``### Don'ts``.

Without this scanner, the elegant-abstraction patterns from PR #209 had to
be duplicated into each author profile to be enforced — friction every
new author profile must repeat.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from tools.analysis.manuscript.rules import _scan_global_shape_bans


@pytest.fixture(autouse=True)
def patch_storyforge_home(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Redirect ``Path.home()`` so author-profile dedup queries hit an empty
    fake home instead of the real ``~/.storyforge``. Without this, tests
    inherit the developer's local Ethan Cole patches and the dedup logic
    suppresses every global finding."""
    fake_home = tmp_path / "fake-home"
    fake_home.mkdir()
    monkeypatch.setattr(Path, "home", classmethod(lambda cls: fake_home))
    return fake_home / ".storyforge"


def _write_book(
    tmp_path: Path,
    *,
    author_line: str = "- **Author:** Ethan Cole",
    chapters: dict[str, str],
) -> Path:
    book = tmp_path / "book"
    book.mkdir()
    (book / "CLAUDE.md").write_text(
        f"# Test Book\n\n## Book Facts\n\n{author_line}\n\n## Rules\n",
        encoding="utf-8",
    )
    chapters_dir = book / "chapters"
    chapters_dir.mkdir()
    for slug, content in chapters.items():
        d = chapters_dir / slug
        d.mkdir()
        (d / "draft.md").write_text(content, encoding="utf-8")
    return book


def _write_catalog(plugin_root: Path, body: str) -> None:
    craft = plugin_root / "reference" / "craft"
    craft.mkdir(parents=True, exist_ok=True)
    (craft / "anti-ai-patterns.md").write_text(body, encoding="utf-8")


class TestScanGlobalShapeBans:
    def test_finds_shape_violation(self, tmp_path: Path):
        plugin_root = tmp_path / "plugin"
        plugin_root.mkdir()
        _write_catalog(
            plugin_root,
            "## 11. Elegant Abstraction\n\n"
            "**Banned shape:** `\\bthe (room|silence) (received|did|held)\\b`.\n",
        )
        book = _write_book(
            tmp_path,
            chapters={
                "01": "# Chapter 1\n\nThe room received it without complaint.\n",
            },
        )
        findings = _scan_global_shape_bans(book, plugin_root=plugin_root)
        assert findings
        assert all(f.category == "global_shape_violation" for f in findings)

    def test_severity_is_medium_not_high(self, tmp_path: Path):
        """Global shapes are advisory — they should not outrank book/author
        rules which are user-asserted blocks. Medium severity matches."""
        plugin_root = tmp_path / "plugin"
        plugin_root.mkdir()
        _write_catalog(
            plugin_root,
            "## 11.\n\n**Banned shape:** `\\bthe room received\\b`.\n",
        )
        book = _write_book(
            tmp_path,
            chapters={"01": "# Ch\n\nThe room received it.\n"},
        )
        findings = _scan_global_shape_bans(book, plugin_root=plugin_root)
        assert findings
        assert all(f.severity == "medium" for f in findings)

    def test_no_violations_returns_empty(self, tmp_path: Path):
        plugin_root = tmp_path / "plugin"
        plugin_root.mkdir()
        _write_catalog(
            plugin_root,
            "## 11.\n\n**Banned shape:** `\\bthe room received\\b`.\n",
        )
        book = _write_book(
            tmp_path,
            chapters={"01": "# Ch\n\nClean prose with no banned shapes.\n"},
        )
        assert _scan_global_shape_bans(book, plugin_root=plugin_root) == []

    def test_no_catalog_returns_empty(self, tmp_path: Path):
        plugin_root = tmp_path / "plugin"
        plugin_root.mkdir()
        book = _write_book(
            tmp_path,
            chapters={"01": "# Ch\n\nThe room received it.\n"},
        )
        # No anti-ai-patterns.md → loader returns [] → scanner returns [].
        assert _scan_global_shape_bans(book, plugin_root=plugin_root) == []

    def test_source_rule_attributes_to_catalog(self, tmp_path: Path):
        plugin_root = tmp_path / "plugin"
        plugin_root.mkdir()
        _write_catalog(
            plugin_root,
            "## 11.\n\n**Banned shape:** `\\bthe room received\\b`.\n",
        )
        book = _write_book(
            tmp_path,
            chapters={"01": "# Ch\n\nThe room received it.\n"},
        )
        findings = _scan_global_shape_bans(book, plugin_root=plugin_root)
        assert findings
        src = (findings[0].source_rule or "").lower()
        assert "section 11" in src or "anti-ai" in src


class TestScanGlobalShapeBansDedupesWithAuthorDonts:
    """When an author's ### Don'ts already block the same shape, the global
    warn-finding should be suppressed for that match — no double-flagging."""

    def test_global_finding_suppressed_when_author_dont_already_blocks(
        self, tmp_path: Path, patch_storyforge_home: Path
    ):
        plugin_root = tmp_path / "plugin"
        plugin_root.mkdir()
        # Catalog has the shape.
        _write_catalog(
            plugin_root,
            "## 11.\n\n**Banned shape:** `\\bthe room received\\b`.\n",
        )
        # Author profile ALSO bans the shape via Don'ts.
        profile_dir = patch_storyforge_home / "authors" / "ethan-cole"
        profile_dir.mkdir(parents=True)
        (profile_dir / "profile.md").write_text(
            "## Writing Discoveries\n\n"
            "### Don'ts\n\n"
            "- **Never personify rooms** — `\\bthe room received\\b`\n",
            encoding="utf-8",
        )
        book = _write_book(
            tmp_path,
            chapters={"01": "# Ch\n\nThe room received it.\n"},
        )

        # Run the global scanner. Author scanner already blocks this hit
        # (severity high). Global must suppress to avoid double-flag.
        from tools.analysis.manuscript.rules import _scan_author_rules

        author_findings = _scan_author_rules(book)
        global_findings = _scan_global_shape_bans(book, plugin_root=plugin_root)

        # Author finding present (high severity, author_rule_violation).
        assert author_findings
        # Global finding suppressed for this chapter/line — at most other
        # phrases catch global. For this exact phrase, no double finding.
        global_phrases_at_line = [
            f for f in global_findings
            if any(occ.chapter == "01" and "received" in occ.snippet.lower()
                   for occ in f.occurrences)
        ]
        assert not global_phrases_at_line
