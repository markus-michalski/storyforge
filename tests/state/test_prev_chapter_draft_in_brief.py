"""Tests for prev_chapter_draft in get_chapter_writing_brief (Issue #342).

The model-compliance gap: chapter-writer skill had a manual instruction to
read the previous chapter draft, but the model skipped it under context
pressure and wrote Ch 32 as a replay of Ch 31. Fix: bundle the last ~500
words of the preceding chapter directly into the brief so it loads
automatically and cannot be skipped.
"""

from __future__ import annotations

from pathlib import Path

import pytest

import tools.db.connection as _db_conn
from tools.state.chapter_writing_brief import build_chapter_writing_brief


@pytest.fixture()
def db_dir(tmp_path, monkeypatch):
    d = tmp_path / "db"
    d.mkdir()
    monkeypatch.setattr(_db_conn, "DB_DIR", d)
    return d


def _make_book(tmp_path: Path) -> tuple[Path, Path]:
    book = tmp_path / "test-book"
    (book / "chapters").mkdir(parents=True)
    (book / "characters").mkdir()
    (book / "plot").mkdir()
    (book / "world").mkdir()
    (book / "README.md").write_text(
        '---\ntitle: "Test Book"\nauthor: ""\n---\n\n# Test Book\n',
        encoding="utf-8",
    )
    plugin_root = Path(__file__).resolve().parent.parent.parent
    return book, plugin_root


def _make_chapter(book: Path, slug: str, *, status: str = "Outline") -> Path:
    ch = book / "chapters" / slug
    ch.mkdir(parents=True, exist_ok=True)
    (ch / "README.md").write_text(
        f"---\ntitle: Chapter\nstatus: {status}\npov: Theo\n---\n\n## Outline\nA chapter.\n",
        encoding="utf-8",
    )
    (ch / "chapter.yaml").write_text(f"status: {status}\n", encoding="utf-8")
    return ch


class TestPrevChapterDraftInBrief:
    def test_prev_chapter_draft_present_when_predecessor_has_draft(
        self, tmp_path, db_dir
    ):
        """Brief includes prev_chapter_draft when the preceding chapter has a draft."""
        book, plugin_root = _make_book(tmp_path)

        ch31 = _make_chapter(book, "31-ashes", status="review")
        (ch31 / "draft.md").write_text(
            "# Chapter 31\n\nLong scene one.\n\nLong scene two.\n\n"
            + "A" * 200 + "\n\n"
            + "B" * 200 + "\n\n"
            + "The final paragraph of chapter thirty-one.",
            encoding="utf-8",
        )

        _make_chapter(book, "32-the-mask", status="Outline")

        brief = build_chapter_writing_brief(
            book_root=book,
            book_slug="test-book",
            chapter_slug="32-the-mask",
            plugin_root=plugin_root,
        )

        assert "prev_chapter_draft" in brief
        payload = brief["prev_chapter_draft"]
        assert payload is not None
        assert payload["chapter"] == "31-ashes"
        assert "The final paragraph of chapter thirty-one" in payload["text"]

    def test_prev_chapter_draft_none_for_first_chapter(self, tmp_path, db_dir):
        """Brief has prev_chapter_draft=None when writing Chapter 1."""
        book, plugin_root = _make_book(tmp_path)
        _make_chapter(book, "01-invisible", status="Outline")

        brief = build_chapter_writing_brief(
            book_root=book,
            book_slug="test-book",
            chapter_slug="01-invisible",
            plugin_root=plugin_root,
        )

        assert brief["prev_chapter_draft"] is None

    def test_prev_chapter_draft_none_when_predecessor_has_no_draft(
        self, tmp_path, db_dir
    ):
        """Brief has prev_chapter_draft=None when predecessor exists but has no draft.md."""
        book, plugin_root = _make_book(tmp_path)
        _make_chapter(book, "31-ashes", status="Outline")  # no draft.md
        _make_chapter(book, "32-the-mask", status="Outline")

        brief = build_chapter_writing_brief(
            book_root=book,
            book_slug="test-book",
            chapter_slug="32-the-mask",
            plugin_root=plugin_root,
        )

        assert brief["prev_chapter_draft"] is None

    def test_prev_chapter_draft_truncated_to_max_chars(self, tmp_path, db_dir):
        """Draft text is capped at max_chars — avoids brief size explosion."""
        book, plugin_root = _make_book(tmp_path)

        ch31 = _make_chapter(book, "31-ashes", status="review")
        # Write a very long draft (10k chars)
        (ch31 / "draft.md").write_text(
            "# Chapter 31\n\n" + ("word " * 2000),
            encoding="utf-8",
        )

        _make_chapter(book, "32-the-mask", status="Outline")

        brief = build_chapter_writing_brief(
            book_root=book,
            book_slug="test-book",
            chapter_slug="32-the-mask",
            plugin_root=plugin_root,
        )

        payload = brief["prev_chapter_draft"]
        assert payload is not None
        assert len(payload["text"]) <= 3600  # 3500 + ellipsis headroom

    def test_prev_chapter_draft_is_direct_predecessor_not_earlier(
        self, tmp_path, db_dir
    ):
        """prev_chapter_draft contains Ch 31, not Ch 30, when writing Ch 32."""
        book, plugin_root = _make_book(tmp_path)

        ch30 = _make_chapter(book, "30-rage", status="review")
        (ch30 / "draft.md").write_text(
            "# Chapter 30\n\nThis is chapter thirty.",
            encoding="utf-8",
        )

        ch31 = _make_chapter(book, "31-ashes", status="review")
        (ch31 / "draft.md").write_text(
            "# Chapter 31\n\nThis is chapter thirty-one.",
            encoding="utf-8",
        )

        _make_chapter(book, "32-the-mask", status="Outline")

        brief = build_chapter_writing_brief(
            book_root=book,
            book_slug="test-book",
            chapter_slug="32-the-mask",
            plugin_root=plugin_root,
        )

        payload = brief["prev_chapter_draft"]
        assert payload is not None
        assert payload["chapter"] == "31-ashes"
        assert "chapter thirty-one" in payload["text"]
        assert "chapter thirty." not in payload["text"]
