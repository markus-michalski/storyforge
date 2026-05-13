"""Tests for the manuscript-checker author-vocab scanner (Issue #210).

``_scan_author_vocab`` reads ``vocabulary.md`` ``### Forbidden ...`` sections
from the author profile (via ``tools.banlist_loader.load_author_vocab``) and
emits :class:`Finding` instances with ``category="author_vocab_violation"`` —
the same category the hook (``chapter_validator._scan_author_banlist``) uses
so the two enforcement layers stay consistent.

Without this scanner, banned-vocabulary entries were enforced at write-time
by the hook but invisible in the manuscript-checker post-draft report —
violations could slip through if the hook was bypassed or temporarily set
to ``warn`` mode.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from tools.analysis.manuscript.rules import _scan_author_vocab

PLUGIN_ROOT = Path(__file__).resolve().parent.parent.parent


@pytest.fixture
def patch_storyforge_home(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
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


def _write_vocab(home: Path, slug: str, vocab_body: str) -> None:
    profile_dir = home / "authors" / slug
    profile_dir.mkdir(parents=True)
    (profile_dir / "vocabulary.md").write_text(
        f"# Vocabulary\n\n## Banned Words\n\n{vocab_body}",
        encoding="utf-8",
    )


class TestScanAuthorVocab:
    def test_finds_forbidden_word(self, tmp_path, patch_storyforge_home):
        book = _write_book(
            tmp_path,
            chapters={"01": "# Ch\n\nShe began to delve into the matter.\n"},
        )
        _write_vocab(
            patch_storyforge_home,
            "ethan-cole",
            "### Absolutely Forbidden\n\n- delve\n",
        )
        findings = _scan_author_vocab(book)
        assert findings
        assert all(f.category == "author_vocab_violation" for f in findings)

    def test_finds_word_inflections(self, tmp_path, patch_storyforge_home):
        """`load_author_vocab` builds inflection patterns — `delve` should
        also catch `delved`, `delving`, etc."""
        book = _write_book(
            tmp_path,
            chapters={"01": "# Ch\n\nThey delved into the archives.\n"},
        )
        _write_vocab(
            patch_storyforge_home,
            "ethan-cole",
            "### Absolutely Forbidden\n\n- delve\n",
        )
        findings = _scan_author_vocab(book)
        assert findings, "inflection-aware match expected"

    def test_severity_high(self, tmp_path, patch_storyforge_home):
        book = _write_book(
            tmp_path,
            chapters={"01": "# Ch\n\nShe began to delve.\n"},
        )
        _write_vocab(
            patch_storyforge_home,
            "ethan-cole",
            "### Absolutely Forbidden\n\n- delve\n",
        )
        findings = _scan_author_vocab(book)
        assert findings
        assert all(f.severity == "high" for f in findings)

    def test_source_rule_points_to_vocab(self, tmp_path, patch_storyforge_home):
        book = _write_book(
            tmp_path,
            chapters={"01": "# Ch\n\nShe began to delve.\n"},
        )
        _write_vocab(
            patch_storyforge_home,
            "ethan-cole",
            "### Absolutely Forbidden\n\n- delve\n",
        )
        findings = _scan_author_vocab(book)
        assert findings
        source = (findings[0].source_rule or "").lower()
        assert "vocab" in source
        assert "ethan-cole" in source

    def test_no_violations_returns_empty(self, tmp_path, patch_storyforge_home):
        book = _write_book(
            tmp_path,
            chapters={"01": "# Ch\n\nClean prose with no banned words.\n"},
        )
        _write_vocab(
            patch_storyforge_home,
            "ethan-cole",
            "### Absolutely Forbidden\n\n- delve\n",
        )
        assert _scan_author_vocab(book) == []

    def test_no_author_returns_empty(self, tmp_path, patch_storyforge_home):
        book = _write_book(
            tmp_path,
            author_line="- **Genre:** test",
            chapters={"01": "# Ch\n\nShe began to delve.\n"},
        )
        _write_vocab(
            patch_storyforge_home,
            "ethan-cole",
            "### Absolutely Forbidden\n\n- delve\n",
        )
        assert _scan_author_vocab(book) == []

    def test_no_vocab_file_returns_empty(self, tmp_path, patch_storyforge_home):
        book = _write_book(
            tmp_path,
            chapters={"01": "# Ch\n\nShe began to delve.\n"},
        )
        # Profile/vocabulary.md not written.
        assert _scan_author_vocab(book) == []
