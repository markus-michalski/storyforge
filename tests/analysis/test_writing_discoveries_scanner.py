"""Tests for the manuscript-checker Writing-Discoveries scanner (Issue #151
follow-up).

The scanner mirrors ``_scan_book_rules`` but reads from the author profile's
``## Writing Discoveries / ### Recurring Tics`` section instead of the
book's CLAUDE.md.

Without this scanner, phrases promoted via ``/storyforge:harvest-author-rules``
were invisible to the manuscript-checker — chapter drafts could re-introduce
already-flagged tics with no detection.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from tools.analysis.manuscript.rules import _scan_writing_discoveries

PLUGIN_ROOT = Path(__file__).resolve().parent.parent.parent


@pytest.fixture
def patch_storyforge_home(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Redirect ``Path.home()/.storyforge`` to a fake home rooted in tmp_path.

    Returns the resolved storyforge_home path (`tmp_path/.storyforge`) so
    helpers can write fixtures into the right place.
    """
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
    """Create a minimal book layout with an Author line so the scanner can
    resolve the author slug and load the discoveries."""
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


def _write_profile(home: Path, slug: str, discoveries_body: str) -> None:
    profile_dir = home / "authors" / slug
    profile_dir.mkdir(parents=True)
    (profile_dir / "profile.md").write_text(
        '---\nname: "Ethan Cole"\nslug: "ethan-cole"\n---\n\n'
        "# Ethan Cole\n\n"
        "## Writing Discoveries\n\n"
        f"{discoveries_body}",
        encoding="utf-8",
    )


# ---------------------------------------------------------------------------
# _scan_writing_discoveries
# ---------------------------------------------------------------------------


class TestScanWritingDiscoveries:
    def test_finds_quoted_tic_violation(self, tmp_path, patch_storyforge_home):
        book = _write_book(
            tmp_path,
            chapters={
                "01-open": "# Chapter 1\n\nHe was doing a thing with his hand again.\n",
            },
        )
        _write_profile(
            patch_storyforge_home,
            "ethan-cole",
            (
                '### Recurring Tics\n\n'
                '- **Vague-noun "thing" als Fallback** — concretize on sight.\n'
            ),
        )

        findings = _scan_writing_discoveries(book)
        assert findings, "expected at least one violation"
        assert any("thing" in f.phrase.lower() for f in findings)

    def test_falls_back_to_bold_title_text(self, tmp_path, patch_storyforge_home):
        book = _write_book(
            tmp_path,
            chapters={
                "01-open": '# Chapter 1\n\n"Wait." Opened his mouth. Closed it.\n',
            },
        )
        _write_profile(
            patch_storyforge_home,
            "ethan-cole",
            (
                '### Recurring Tics\n\n'
                '- **Opened his mouth. Closed it.** — vary or skip.\n'
            ),
        )

        findings = _scan_writing_discoveries(book)
        assert findings

    def test_severity_high(self, tmp_path, patch_storyforge_home):
        book = _write_book(
            tmp_path,
            chapters={
                "01-open": "# Chapter 1\n\nShe was doing a thing with the keys.\n",
            },
        )
        _write_profile(
            patch_storyforge_home,
            "ethan-cole",
            '### Recurring Tics\n\n- **"thing"** — concretize.\n',
        )

        findings = _scan_writing_discoveries(book)
        assert findings
        assert all(f.severity == "high" for f in findings)

    def test_category_distinguishes_from_book_rules(self, tmp_path, patch_storyforge_home):
        """Writing-Discoveries findings must carry their own category so the
        report can show their origin (author profile vs book CLAUDE.md)."""
        book = _write_book(
            tmp_path,
            chapters={"01-open": "# Chapter 1\n\nA thing happened, vaguely.\n"},
        )
        _write_profile(
            patch_storyforge_home,
            "ethan-cole",
            '### Recurring Tics\n\n- **"thing"** — concretize.\n',
        )

        findings = _scan_writing_discoveries(book)
        assert all(f.category == "writing_discovery_violation" for f in findings)

    def test_source_rule_points_to_writing_discoveries(self, tmp_path, patch_storyforge_home):
        book = _write_book(
            tmp_path,
            chapters={"01-open": "# Chapter 1\n\nA thing happened.\n"},
        )
        _write_profile(
            patch_storyforge_home,
            "ethan-cole",
            '### Recurring Tics\n\n- **"thing"** — concretize.\n',
        )

        findings = _scan_writing_discoveries(book)
        assert findings
        assert "writing discoveries" in (findings[0].source_rule or "").lower()

    def test_no_author_resolved_returns_empty(self, tmp_path, patch_storyforge_home):
        # Book has no Author line; cannot resolve a profile.
        book = _write_book(
            tmp_path,
            author_line="- **Genre:** test",
            chapters={"01-open": "# Chapter 1\n\nA thing happened.\n"},
        )
        _write_profile(
            patch_storyforge_home,
            "ethan-cole",
            '### Recurring Tics\n\n- **"thing"** — concretize.\n',
        )

        assert _scan_writing_discoveries(book) == []

    def test_no_violations_returns_empty(self, tmp_path, patch_storyforge_home):
        book = _write_book(
            tmp_path,
            chapters={"01-open": "# Chapter 1\n\nClean prose without any banned terms.\n"},
        )
        _write_profile(
            patch_storyforge_home,
            "ethan-cole",
            '### Recurring Tics\n\n- **"thing"** — concretize.\n',
        )

        assert _scan_writing_discoveries(book) == []

    def test_no_discoveries_section_returns_empty(self, tmp_path, patch_storyforge_home):
        book = _write_book(
            tmp_path,
            chapters={"01-open": "# Chapter 1\n\nA thing happened.\n"},
        )
        # Profile exists, but no Writing Discoveries section.
        profile_dir = patch_storyforge_home / "authors" / "ethan-cole"
        profile_dir.mkdir(parents=True)
        (profile_dir / "profile.md").write_text(
            '---\nname: x\n---\n\n# x\n\n## Writing Style\n\nSparse.\n',
            encoding="utf-8",
        )
        assert _scan_writing_discoveries(book) == []
