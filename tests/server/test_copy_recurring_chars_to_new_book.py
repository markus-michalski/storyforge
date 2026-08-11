"""Tests for ``copy_recurring_chars_to_new_book`` MCP tool (Issue #196).

The tool is the dumb-copy precursor to D-2: 1:1 file copy from the
previous book's character files into the new book's character files,
filtered by ``recurs_in`` on the series-trackers. No frontmatter
mutation, no content transformation — D-2 lands the smart version on
top.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

import routers._app as _app
from routers.series import copy_recurring_chars_to_new_book


@pytest.fixture
def content_root(tmp_path: Path) -> Path:
    root = tmp_path / "content"
    root.mkdir()
    return root


@pytest.fixture
def mock_config(content_root: Path, monkeypatch: pytest.MonkeyPatch) -> dict:
    cfg = {
        "paths": {
            "content_root": str(content_root),
            "authors_root": str(content_root / "authors"),
        },
        "defaults": {"language": "en", "book_type": "novel"},
    }
    monkeypatch.setattr(_app, "load_config", lambda: cfg)
    _app._cache.invalidate()
    return cfg


def _make_tracker(
    content_root: Path,
    series: str,
    slug: str,
    *,
    book_slug: str | None = None,
    recurs_in: list[str] | None = None,
    role: str = "supporting",
) -> Path:
    chars_dir = content_root / "series" / series / "characters"
    chars_dir.mkdir(parents=True, exist_ok=True)
    book_slug_line = f"book_slug: {book_slug}\n" if book_slug else ""
    fm = (
        "---\n"
        f"name: {slug}\n"
        f"slug: {slug}\n"
        f"{book_slug_line}"
        f"role: {role}\n"
        "status: Profile\n"
        f"recurs_in: {recurs_in or ['B1']}\n"
        "tracker_type: thin\n"
        "---\n\n# Stub\n"
    )
    path = chars_dir / f"{slug}.md"
    path.write_text(fm, encoding="utf-8")
    return path


def _make_book_char(
    content_root: Path,
    book: str,
    slug: str,
    *,
    body: str = "Profile body",
    layout: str = "characters",
) -> Path:
    char_dir = content_root / "projects" / book / layout
    char_dir.mkdir(parents=True, exist_ok=True)
    char_file = char_dir / f"{slug}.md"
    char_file.write_text(
        f"---\nname: {slug}\nrole: protagonist\ncurrent_inventory: [knife]\n---\n\n{body}\n",
        encoding="utf-8",
    )
    return char_file


def _make_book_dir(content_root: Path, book: str) -> Path:
    project = content_root / "projects" / book
    project.mkdir(parents=True, exist_ok=True)
    (project / "characters").mkdir(exist_ok=True)
    return project


class TestCopyRecurringCharsHappyPath:
    def test_copies_files_for_recurring_trackers(self, mock_config, content_root: Path):
        # Series with three recurring trackers, one only in B1, one new in B2.
        _make_tracker(content_root, "blood-and-binary", "kael", recurs_in=["B1", "B2"])
        _make_tracker(content_root, "blood-and-binary", "viktor", recurs_in=["B1", "B2"])
        _make_tracker(content_root, "blood-and-binary", "sera", recurs_in=["B1"])
        _make_tracker(content_root, "blood-and-binary", "tristan", recurs_in=["B2", "B3"])

        # Source book (B1) with three book-level char files.
        _make_book_char(content_root, "firelight", "kael", body="Kael profile")
        _make_book_char(content_root, "firelight", "viktor", body="Viktor profile")
        _make_book_char(content_root, "firelight", "sera", body="Sera profile")
        # Destination book scaffold.
        _make_book_dir(content_root, "moonrise")

        result = json.loads(
            copy_recurring_chars_to_new_book(
                series_slug="blood-and-binary",
                prev_book_slug="firelight",
                new_book_slug="moonrise",
                new_band="B2",
            )
        )

        copied_slugs = sorted(c["book_slug"] for c in result["copied"])
        assert copied_slugs == ["kael", "viktor"]
        # Sera (only B1) was excluded entirely — not even surfaced.
        assert all(c["book_slug"] != "sera" for c in result["copied"])
        # Tristan recurs in B2 but had no source file → flagged as new char.
        new_slugs = [c["tracker_slug"] for c in result["new_chars"]]
        assert "tristan" in new_slugs

        # Files actually exist at dest.
        moonrise = content_root / "projects" / "moonrise" / "characters"
        assert (moonrise / "kael.md").exists()
        assert (moonrise / "viktor.md").exists()
        # Byte-identical copy.
        assert "Kael profile" in (moonrise / "kael.md").read_text()
        assert "current_inventory" in (moonrise / "kael.md").read_text()

    def test_resolves_book_slug_via_194(self, mock_config, content_root: Path):
        # Tracker slug ≠ book slug — uses #194's resolver.
        _make_tracker(
            content_root,
            "blood-and-binary",
            "king-caelan",
            book_slug="caelan",
            recurs_in=["B1", "B2", "B3"],
        )
        _make_book_char(content_root, "firelight", "caelan", body="Caelan profile")
        _make_book_dir(content_root, "moonrise")

        result = json.loads(copy_recurring_chars_to_new_book("blood-and-binary", "firelight", "moonrise", "B2"))
        assert len(result["copied"]) == 1
        entry = result["copied"][0]
        assert entry["tracker_slug"] == "king-caelan"
        assert entry["book_slug"] == "caelan"
        assert (content_root / "projects" / "moonrise" / "characters" / "caelan.md").exists()


class TestCopyRecurringCharsSkipBehavior:
    def test_skips_when_dest_already_exists(self, mock_config, content_root: Path):
        _make_tracker(content_root, "my-series", "kael", recurs_in=["B1", "B2"])
        _make_book_char(content_root, "book1", "kael", body="From book1")
        # Pre-create the dest with different content.
        _make_book_char(content_root, "book2", "kael", body="Author already started this")

        result = json.loads(copy_recurring_chars_to_new_book("my-series", "book1", "book2", "B2"))
        assert result["copied"] == []
        skipped = result["skipped"]
        assert len(skipped) == 1
        assert skipped[0]["book_slug"] == "kael"
        assert "exists" in skipped[0]["reason"].lower()
        # Pre-existing file content is preserved — not overwritten.
        text = (content_root / "projects" / "book2" / "characters" / "kael.md").read_text()
        assert "Author already started this" in text

    def test_marks_new_chars_when_no_source(self, mock_config, content_root: Path):
        # Tracker recurs in B2 but has no B1 source.
        _make_tracker(content_root, "my-series", "tristan", recurs_in=["B2", "B3"])
        _make_book_dir(content_root, "book1")
        _make_book_dir(content_root, "book2")

        result = json.loads(copy_recurring_chars_to_new_book("my-series", "book1", "book2", "B2"))
        assert result["copied"] == []
        assert len(result["new_chars"]) == 1
        entry = result["new_chars"][0]
        assert entry["tracker_slug"] == "tristan"
        assert entry["recurs_in"] == ["B2", "B3"]


class TestCopyRecurringCharsMemoir:
    def test_uses_people_dir_for_memoir(self, mock_config, content_root: Path):
        _make_tracker(content_root, "my-memoir-series", "mom", recurs_in=["B1", "B2"])
        # Source layout uses people/ for memoir.
        _make_book_char(content_root, "book1", "mom", body="Mom person profile", layout="people")
        # Dest dir.
        (content_root / "projects" / "book2" / "people").mkdir(parents=True)

        result = json.loads(
            copy_recurring_chars_to_new_book("my-memoir-series", "book1", "book2", "B2", book_category="memoir")
        )
        assert len(result["copied"]) == 1
        assert (content_root / "projects" / "book2" / "people" / "mom.md").exists()


class TestCopyRecurringCharsValidation:
    def test_invalid_band_returns_error(self, mock_config, content_root: Path):
        result = json.loads(copy_recurring_chars_to_new_book("my-series", "book1", "book2", "Book2"))
        assert "band" in result["error"].lower()

    def test_series_not_found(self, mock_config, content_root: Path):
        result = json.loads(copy_recurring_chars_to_new_book("ghost-series", "book1", "book2", "B2"))
        assert "not found" in result["error"].lower()

    def test_prev_book_not_found(self, mock_config, content_root: Path):
        _make_tracker(content_root, "my-series", "kael", recurs_in=["B1", "B2"])
        result = json.loads(copy_recurring_chars_to_new_book("my-series", "ghost-book", "book2", "B2"))
        assert "not found" in result["error"].lower()

    def test_new_book_not_found(self, mock_config, content_root: Path):
        _make_tracker(content_root, "my-series", "kael", recurs_in=["B1", "B2"])
        _make_book_dir(content_root, "book1")
        result = json.loads(copy_recurring_chars_to_new_book("my-series", "book1", "ghost-new", "B2"))
        assert "not found" in result["error"].lower()

    def test_empty_series_returns_empty_lists(self, mock_config, content_root: Path):
        # Series exists but has no trackers.
        (content_root / "series" / "my-series" / "characters").mkdir(parents=True)
        _make_book_dir(content_root, "book1")
        _make_book_dir(content_root, "book2")
        result = json.loads(copy_recurring_chars_to_new_book("my-series", "book1", "book2", "B2"))
        assert result["copied"] == []
        assert result["skipped"] == []
        assert result["new_chars"] == []

    def test_rejects_path_traversal_in_book_slug(self, mock_config, content_root: Path):
        # Issue #542 PoC: a hand-edited or pre-#524 tracker with a
        # traversal book_slug must not reach shutil.copy2's WRITE target.
        # dst_layout is content_root/projects/moonrise/characters — 3
        # levels below content_root, so "../../../../tmp/pwned" escapes
        # content_root entirely, landing at content_root.parent/tmp/pwned.md
        # (content_root itself is tmp_path/"content", so this is
        # tmp_path/"tmp"/"pwned.md" — a sibling of the whole content tree,
        # not merely a different book).
        _make_tracker(
            content_root,
            "blood-and-binary",
            "evil",
            book_slug="../../../../tmp/pwned",
            recurs_in=["B1", "B2"],
        )
        _make_book_char(content_root, "firelight", "evil", body="irrelevant")
        _make_book_dir(content_root, "moonrise")

        result = json.loads(copy_recurring_chars_to_new_book("blood-and-binary", "firelight", "moonrise", "B2"))
        assert "error" in result
        assert "book_slug" in result["error"]
        assert not (content_root.parent / "tmp" / "pwned.md").exists()

    def test_all_or_nothing_when_one_tracker_is_malicious(self, mock_config, content_root: Path):
        # Code review finding on #542: recurring_chars_for_book() calls
        # resolve_book_slug_for_series_tracker() for every tracker while
        # building its (eagerly-evaluated, non-generator) return list —
        # BEFORE this tool's own for-loop starts iterating. So a malicious
        # tracker sorting AFTER a legitimate one (by tracker_slug) must
        # still block the legitimate one's copy, not let it land first and
        # then abort partway through, which would leave a stale state
        # cache (skipped _cache.invalidate()) and a discarded `copied` list.
        _make_tracker(content_root, "blood-and-binary", "a-good", recurs_in=["B1", "B2"])
        _make_tracker(
            content_root,
            "blood-and-binary",
            "z-evil",
            book_slug="../../../../tmp/pwned2",
            recurs_in=["B1", "B2"],
        )
        _make_book_char(content_root, "firelight", "a-good", body="irrelevant")
        _make_book_char(content_root, "firelight", "z-evil", body="irrelevant")
        _make_book_dir(content_root, "moonrise")

        result = json.loads(copy_recurring_chars_to_new_book("blood-and-binary", "firelight", "moonrise", "B2"))
        assert "error" in result
        assert not (content_root / "projects" / "moonrise" / "characters" / "a-good.md").exists()

    def test_router_own_validate_slug_call_is_load_bearing(
        self, mock_config, content_root: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """The `_validate_slug(book_slug, "book_slug")` call right after
        `book_slug = tracker["book_slug"]` in this router function is
        documented as redundant defense-in-depth — recurring_chars_for_book()
        already validates internally via resolve_book_slug_for_series_tracker()
        (#542). That makes it untestable via a live tracker file (the
        resolver always raises first, so no traversal payload can ever reach
        this router's own call). Isolate it directly: monkeypatch
        recurring_chars_for_book() to simulate a future regression where it
        stops validating, and confirm this router-level call still catches
        the bad value on its own."""
        import routers.series as series_router

        monkeypatch.setattr(
            series_router,
            "recurring_chars_for_book",
            lambda series_dir, band: [
                {
                    "tracker_slug": "evil",
                    "book_slug": "../../../evil",
                    "recurs_in": ["B1", "B2"],
                    "prior_bands": ["B1"],
                }
            ],
        )
        # Series/book dirs must exist to pass the tool's own not-found
        # checks before it ever reaches the (monkeypatched) tracker loop —
        # no real tracker file needed since recurring_chars_for_book is
        # stubbed above.
        (content_root / "series" / "blood-and-binary" / "characters").mkdir(parents=True)
        _make_book_char(content_root, "firelight", "evil", body="irrelevant")
        _make_book_dir(content_root, "moonrise")

        result = json.loads(copy_recurring_chars_to_new_book("blood-and-binary", "firelight", "moonrise", "B2"))
        assert "error" in result
        assert "book_slug" in result["error"]
