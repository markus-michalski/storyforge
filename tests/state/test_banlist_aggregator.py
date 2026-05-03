"""Tests for ``collect_banned_phrases`` (Issue #151 follow-up).

The aggregator merges four sources in priority order. After #151 the fourth
source is author Writing Discoveries — without it, phrases promoted via
``/storyforge:harvest-author-rules`` were invisible to the chapter-writing
brief and the manuscript-checker.
"""

from __future__ import annotations

import pytest
from pathlib import Path

from tools.state.loaders.banlist import collect_banned_phrases

PLUGIN_ROOT = Path(__file__).resolve().parent.parent.parent


def _make_book(tmp_path: Path, *, author: str = "ethan-cole", rules: str = "") -> Path:
    """Create a minimal book with an Author line and optional rules."""
    book = tmp_path / "test-book"
    book.mkdir()
    body = (
        "# Test Book\n\n"
        "## Book Facts\n\n"
        f"- **Author:** {author.replace('-', ' ').title()}\n\n"
        "## Rules\n\n"
        f"{rules}\n"
    )
    (book / "CLAUDE.md").write_text(body, encoding="utf-8")
    return book


def _make_author_home(
    tmp_path: Path,
    *,
    slug: str = "ethan-cole",
    vocab_body: str = "",
    discoveries_body: str = "",
) -> Path:
    """Create a fake ~/.storyforge tree with vocabulary.md + profile.md."""
    home = tmp_path / ".storyforge"
    author_dir = home / "authors" / slug
    author_dir.mkdir(parents=True)

    if vocab_body:
        (author_dir / "vocabulary.md").write_text(vocab_body, encoding="utf-8")
    else:
        (author_dir / "vocabulary.md").write_text(
            "# Vocab\n\n## Banned Words\n\n### Absolutely Forbidden\n\n- delve\n",
            encoding="utf-8",
        )

    discoveries = discoveries_body or "_Frei._\n"
    (author_dir / "profile.md").write_text(
        '---\nname: "Ethan Cole"\nslug: "ethan-cole"\n---\n\n'
        "# Ethan Cole\n\n"
        "## Writing Discoveries\n\n"
        f"{discoveries}",
        encoding="utf-8",
    )
    return home


@pytest.fixture
def patch_storyforge_home(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Redirect ``Path.home()/.storyforge`` lookups to ``tmp_path``.

    ``load_author_vocab`` and ``load_author_writing_discoveries`` accept a
    ``storyforge_home`` override but the public ``collect_banned_phrases``
    helper does not — patching ``Path.home`` is the smallest seam.
    """
    monkeypatch.setattr(Path, "home", classmethod(lambda cls: tmp_path))
    return tmp_path


# ---------------------------------------------------------------------------
# Writing Discoveries source (the new 4th source)
# ---------------------------------------------------------------------------


class TestWritingDiscoveriesSource:
    def test_picks_up_recurring_tic_quoted_phrase(self, tmp_path, patch_storyforge_home):
        """A discovery like `**Vague-noun "thing" als Fallback**` must produce
        a banned-phrase entry for `thing`."""
        book = _make_book(tmp_path)
        _make_author_home(
            tmp_path,
            discoveries_body=(
                '### Recurring Tics\n\n'
                '- **Vague-noun "thing" als Fallback** — concretize. '
                '_(emerged from firelight, 2026-05)_\n'
            ),
        )

        result = collect_banned_phrases(book, PLUGIN_ROOT)
        phrases = [r["phrase"] for r in result]
        assert "thing" in phrases

    def test_writing_discoveries_severity_is_block(self, tmp_path, patch_storyforge_home):
        book = _make_book(tmp_path)
        _make_author_home(
            tmp_path,
            discoveries_body=(
                '### Recurring Tics\n\n'
                '- **Vague-noun "thing" als Fallback** — concretize.\n'
            ),
        )
        result = collect_banned_phrases(book, PLUGIN_ROOT)
        thing_entry = next(r for r in result if r["phrase"] == "thing")
        assert thing_entry["severity"] == "block"

    def test_source_string_identifies_writing_discoveries(self, tmp_path, patch_storyforge_home):
        book = _make_book(tmp_path)
        _make_author_home(
            tmp_path,
            discoveries_body=(
                '### Recurring Tics\n\n'
                '- **"thing"** — concretize.\n'
            ),
        )
        result = collect_banned_phrases(book, PLUGIN_ROOT)
        thing_entry = next(r for r in result if r["phrase"] == "thing")
        assert "writing discoveries" in thing_entry["source"].lower()

    def test_dedups_against_book_rules(self, tmp_path, patch_storyforge_home):
        """If a phrase is in both book CLAUDE.md ## Rules AND author Writing
        Discoveries, it appears once — book wins (higher priority source)."""
        book = _make_book(tmp_path, rules="- Avoid `thing` — concretize.\n")
        _make_author_home(
            tmp_path,
            discoveries_body=(
                '### Recurring Tics\n\n'
                '- **"thing"** — concretize.\n'
            ),
        )

        result = collect_banned_phrases(book, PLUGIN_ROOT)
        thing_entries = [r for r in result if r["phrase"] == "thing"]
        assert len(thing_entries) == 1
        # Book CLAUDE.md is the higher-priority source.
        assert "book" in thing_entries[0]["source"].lower()

    def test_dedups_against_author_vocabulary(self, tmp_path, patch_storyforge_home):
        """Vocabulary entries also win over Writing Discoveries (same author,
        different file — vocabulary is the canonical phrase store)."""
        book = _make_book(tmp_path)
        _make_author_home(
            tmp_path,
            vocab_body=(
                "# Vocab\n\n## Banned Words\n\n### Absolutely Forbidden\n\n- thing\n"
            ),
            discoveries_body=(
                '### Recurring Tics\n\n'
                '- **"thing"** — concretize.\n'
            ),
        )
        result = collect_banned_phrases(book, PLUGIN_ROOT)
        thing_entries = [r for r in result if r["phrase"] == "thing"]
        assert len(thing_entries) == 1
        assert "vocabulary" in thing_entries[0]["source"].lower()

    def test_falls_back_to_bold_title_when_no_inner_quote(self, tmp_path, patch_storyforge_home):
        book = _make_book(tmp_path)
        _make_author_home(
            tmp_path,
            discoveries_body=(
                '### Recurring Tics\n\n'
                '- **Opened his mouth. Closed it.** — vary.\n'
            ),
        )
        result = collect_banned_phrases(book, PLUGIN_ROOT)
        phrases = [r["phrase"] for r in result]
        assert "Opened his mouth. Closed it." in phrases

    def test_no_author_resolved_means_no_discoveries(self, tmp_path, patch_storyforge_home):
        """When the book has no Author line, the discoveries loader is skipped."""
        book = tmp_path / "no-author-book"
        book.mkdir()
        (book / "CLAUDE.md").write_text(
            "# No Author\n\n## Book Facts\n\n- **Genre:** test\n",
            encoding="utf-8",
        )
        # Author still exists on disk, but the book doesn't point at them.
        _make_author_home(
            tmp_path,
            discoveries_body=(
                '### Recurring Tics\n\n'
                '- **"thing"** — concretize.\n'
            ),
        )
        result = collect_banned_phrases(book, PLUGIN_ROOT)
        phrases = [r["phrase"] for r in result]
        assert "thing" not in phrases
