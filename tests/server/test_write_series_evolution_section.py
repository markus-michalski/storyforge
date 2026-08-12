"""Tests for ``write_series_evolution_section`` and
``list_series_trackers_for_book`` MCP tools (Issue #200, D-1 of #195).

These tools are the harvest skill's write side: they update the right
band's slot in a series-tracker, append a dated entry to the tracker's
Updates Log, and surface which trackers belong to the current book band.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

import routers._app as _app
from routers.series import (
    create_character_tracker,
    list_series_trackers_for_book,
    write_series_evolution_section,
)


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
    name: str | None = None,
    role: str = "supporting",
    recurs_in: list[str] | None = None,
    book_slug: str | None = None,
    body: str = "",
) -> Path:
    chars_dir = content_root / "series" / series / "characters"
    chars_dir.mkdir(parents=True, exist_ok=True)
    book_slug_line = f"book_slug: {book_slug}\n" if book_slug else ""
    recurs = recurs_in or ["B1"]
    fm = (
        "---\n"
        f"name: {name or slug}\n"
        f"slug: {slug}\n"
        f"{book_slug_line}"
        f"role: {role}\n"
        "status: Profile\n"
        f"recurs_in: {recurs}\n"
        "tracker_type: thin\n"
        "---\n\n"
    )
    path = chars_dir / f"{slug}.md"
    path.write_text(fm + body, encoding="utf-8")
    return path


class TestWriteSeriesEvolutionSection:
    def test_writes_ende_to_existing_band(self, mock_config, content_root: Path):
        tracker = _make_tracker(
            content_root,
            "blood-and-binary",
            "kael",
            recurs_in=["B1", "B2"],
            body=(
                "## Evolution per Band\n\n"
                "### B1 Firelight\n"
                "- **Start:** Cabin-Einsiedler.\n"
                "- **Ende:** old end.\n\n"
                "### B2 Moonrise (geplant)\n"
                "- Trauernder Bruder.\n\n"
                "## Updates Log\n\n"
                "(noch keine Eintraege)\n"
            ),
        )

        result = json.loads(
            write_series_evolution_section(
                "blood-and-binary",
                "kael",
                "B1",
                "ende",
                "Mit Theo zusammen, Sera tot.",
                "Harvested from B1 final state",
                date="2026-05-08",
            )
        )
        assert result.get("error") is None
        assert result["success"] is True

        text = tracker.read_text(encoding="utf-8")
        assert "- **Ende:** Mit Theo zusammen, Sera tot." in text
        assert "old end." not in text
        # Updates log got the dated entry; placeholder removed.
        assert "- 2026-05-08 — Harvested from B1 final state" in text
        assert "(noch keine Eintraege)" not in text
        # B2 untouched.
        assert "### B2 Moonrise (geplant)" in text
        assert "- Trauernder Bruder." in text

    def test_creates_band_when_missing(self, mock_config, content_root: Path):
        tracker = _make_tracker(
            content_root,
            "my-series",
            "viktor",
            recurs_in=["B1", "B2"],
            body="## Evolution per Band\n\n### B1 Firelight\n- **Start:** S.\n- **Ende:** E.\n",
        )
        result = json.loads(
            write_series_evolution_section(
                "my-series",
                "viktor",
                "B2",
                "ende",
                "B2 final state.",
                "Harvested from B2 final state",
                date="2026-05-09",
            )
        )
        assert result["success"] is True
        text = tracker.read_text(encoding="utf-8")
        assert "### B2" in text
        assert "B2 final state." in text

    def test_rejects_invalid_kind(self, mock_config, content_root: Path):
        _make_tracker(content_root, "my-series", "kael")
        result = json.loads(
            write_series_evolution_section(
                "my-series",
                "kael",
                "B1",
                "bogus-kind",
                "ignored",
                "ignored",
            )
        )
        assert result.get("success") is None
        assert "kind" in result["error"].lower()

    def test_rejects_invalid_band(self, mock_config, content_root: Path):
        _make_tracker(content_root, "my-series", "kael")
        result = json.loads(
            write_series_evolution_section(
                "my-series",
                "kael",
                "Book1",  # not B<N>
                "ende",
                "ignored",
                "ignored",
            )
        )
        assert "band" in result["error"].lower()

    def test_null_byte_series_slug_returns_clean_error(self, mock_config, content_root: Path):
        """Issue #523: resolve_series_path() raises ValueError via
        _validate_slug() on a null-byte series_slug; before the fix this
        propagated as a raw, unhandled exception instead of the standard
        {"error": ...} JSON contract. @catch_slug_value_error closes the gap."""
        result = json.loads(
            write_series_evolution_section(
                "bad\x00series",
                "kael",
                "B1",
                "ende",
                "...",
                "Harvested",
            )
        )
        assert "error" in result

    def test_rejects_band_with_trailing_newline(self, mock_config, content_root: Path):
        """Issue #525: `$` in RE_BAND_ID matches before a trailing newline, so
        band="B1\\n" passed the guard. Downstream, _find_band_bounds() compares
        the regex-captured band ("B1", never containing \\n) against the raw
        "B1\\n", which never matches — so an existing B1 section is never found
        and write_evolution_section() inserts a *duplicate* ### B1 block instead
        of updating the existing one, silently corrupting the tracker file.
        Anchoring with \\Z closes the gap and the write must not happen at all."""
        tracker = _make_tracker(
            content_root,
            "blood-and-binary",
            "kael",
            recurs_in=["B1"],
            body=(
                "## Evolution per Band\n\n"
                "### B1 Firelight\n"
                "- **Start:** Cabin-Einsiedler.\n"
                "- **Ende:** old end.\n\n"
                "## Updates Log\n\n"
                "(noch keine Eintraege)\n"
            ),
        )
        before = tracker.read_text(encoding="utf-8")

        result = json.loads(
            write_series_evolution_section(
                "blood-and-binary",
                "kael",
                "B1\n",
                "ende",
                "CORRUPTED",
                "Harvested",
            )
        )

        # Assert the file state first: this is what actually fails red-vs-green
        # (a KeyError on result["error"] would mask the corruption otherwise).
        after = tracker.read_text(encoding="utf-8")
        assert after == before
        assert after.count("### B1") == 1
        assert "CORRUPTED" not in after

        assert result.get("success") is not True
        assert "band" in result.get("error", "").lower()

    def test_series_not_found(self, mock_config, content_root: Path):
        result = json.loads(
            write_series_evolution_section(
                "ghost-series",
                "kael",
                "B1",
                "ende",
                "...",
                "Harvested",
            )
        )
        assert "not found" in result["error"].lower()

    def test_tracker_not_found(self, mock_config, content_root: Path):
        # Series exists but the tracker file does not.
        (content_root / "series" / "my-series" / "characters").mkdir(parents=True)
        result = json.loads(
            write_series_evolution_section(
                "my-series",
                "ghost-char",
                "B1",
                "ende",
                "...",
                "Harvested",
            )
        )
        assert "not found" in result["error"].lower()

    def test_rejects_traversal_tracker_slug(self, mock_config, content_root: Path):
        """Issue #524: tracker_path = series_dir / "characters" / f"{tracker_slug}.md"
        builds the path directly from the raw MCP parameter with zero
        validation — unlike series_slug (validated via resolve_series_path).
        Confirmed exploitable: a file outside the series characters/ dir was
        both read (existence check) and overwritten (Updates Log entry
        appended) via a traversal tracker_slug before this fix."""
        (content_root / "series" / "my-series" / "characters").mkdir(parents=True)
        # characters/../../SECRET.md -> my-series/.. -> series/SECRET.md
        secret = content_root / "series" / "SECRET.md"
        secret.write_text(
            "---\nname: leaked\n---\n\n## Evolution per Band\n\n## Updates Log\n\n(none)\n",
            encoding="utf-8",
        )

        result = json.loads(
            write_series_evolution_section(
                "my-series",
                "../../SECRET",
                "B1",
                "ende",
                "CORRUPTED",
                "Harvested",
            )
        )
        assert "tracker_slug" in result["error"]
        assert "CORRUPTED" not in secret.read_text(encoding="utf-8")


class TestListSeriesTrackersForBook:
    def test_returns_only_trackers_recurring_in_band(self, mock_config, content_root: Path):
        _make_tracker(content_root, "my-series", "kael", recurs_in=["B1", "B2", "B3"])
        _make_tracker(content_root, "my-series", "viktor", recurs_in=["B1", "B2"])
        # Tracker that doesn't recur in B1 — must be excluded.
        _make_tracker(content_root, "my-series", "newcomer", recurs_in=["B2", "B3"])

        result = json.loads(list_series_trackers_for_book("my-series", "B1"))
        slugs = sorted(t["tracker_slug"] for t in result["trackers"])
        assert slugs == ["kael", "viktor"]

    def test_resolves_book_slug_via_resolver(self, mock_config, content_root: Path):
        _make_tracker(
            content_root,
            "blood-and-binary",
            "king-caelan",
            book_slug="caelan",
            recurs_in=["B1", "B2", "B3"],
        )
        result = json.loads(list_series_trackers_for_book("blood-and-binary", "B1"))
        entry = result["trackers"][0]
        assert entry["tracker_slug"] == "king-caelan"
        assert entry["book_slug"] == "caelan"

    def test_falls_back_to_tracker_slug_when_book_slug_absent(self, mock_config, content_root: Path):
        _make_tracker(content_root, "my-series", "kael", recurs_in=["B1"])
        result = json.loads(list_series_trackers_for_book("my-series", "B1"))
        entry = result["trackers"][0]
        assert entry["tracker_slug"] == "kael"
        assert entry["book_slug"] == "kael"

    def test_surfaces_existing_ende_for_diff(self, mock_config, content_root: Path):
        _make_tracker(
            content_root,
            "my-series",
            "kael",
            recurs_in=["B1"],
            body=("## Evolution per Band\n\n### B1 Firelight\n- **Start:** S.\n- **Ende:** Existing end content.\n"),
        )
        result = json.loads(list_series_trackers_for_book("my-series", "B1"))
        entry = result["trackers"][0]
        assert entry["has_existing_ende"] is True
        assert "Existing end content" in entry["existing_ende"]

    def test_marks_missing_ende(self, mock_config, content_root: Path):
        _make_tracker(
            content_root,
            "my-series",
            "kael",
            recurs_in=["B1"],
            body="## Evolution per Band\n\n### B1 Firelight\n- **Start:** Just start.\n",
        )
        result = json.loads(list_series_trackers_for_book("my-series", "B1"))
        entry = result["trackers"][0]
        assert entry["has_existing_ende"] is False
        assert entry["existing_ende"] == ""

    def test_has_existing_ende_false_for_freshly_scaffolded_tracker(
        self, mock_config, content_root: Path
    ):
        """Issue #394: create_character_tracker's placeholder prose in the
        Ende slot must not be reported as pre-existing harvest content —
        the tracker has never been harvested."""
        (content_root / "series" / "my-series").mkdir(parents=True)
        create_character_tracker(
            series_slug="my-series",
            name="Kael",
            slug="kael",
            role="protagonist",
            recurs_in=["B1"],
        )
        result = json.loads(list_series_trackers_for_book("my-series", "B1"))
        entry = result["trackers"][0]
        assert entry["has_existing_ende"] is False
        assert entry["existing_ende"] == ""

    def test_rejects_invalid_band(self, mock_config, content_root: Path):
        result = json.loads(list_series_trackers_for_book("my-series", "Book1"))
        assert "band" in result["error"].lower()

    def test_rejects_band_with_trailing_newline(self, mock_config, content_root: Path):
        """Issue #525: same RE_BAND_ID anchoring gap as
        TestWriteSeriesEvolutionSection.test_rejects_band_with_trailing_newline."""
        result = json.loads(list_series_trackers_for_book("my-series", "B1\n"))
        assert "band" in result["error"].lower()

    def test_series_not_found(self, mock_config, content_root: Path):
        result = json.loads(list_series_trackers_for_book("ghost-series", "B1"))
        assert "not found" in result["error"].lower()

    def test_returns_empty_list_when_no_trackers(self, mock_config, content_root: Path):
        # Series exists but no characters dir / no .md files.
        (content_root / "series" / "my-series").mkdir(parents=True)
        result = json.loads(list_series_trackers_for_book("my-series", "B1"))
        assert result["trackers"] == []

    def test_skips_malicious_tracker_and_reports_it_in_invalid_trackers(self, mock_config, content_root: Path):
        # Issue #549: a hand-edited/pre-#524 tracker with a traversal
        # book_slug used to abort the whole listing via SlugValidationError
        # instead of being skipped — every other tracker in the series
        # (potentially dozens) disappeared from the result too.
        _make_tracker(content_root, "my-series", "a-good", recurs_in=["B1"])
        _make_tracker(
            content_root,
            "my-series",
            "z-evil",
            book_slug="../../../../tmp/evil",
            recurs_in=["B1"],
        )
        result = json.loads(list_series_trackers_for_book("my-series", "B1"))
        assert "error" not in result
        slugs = [t["tracker_slug"] for t in result["trackers"]]
        assert slugs == ["a-good"]
        assert len(result["invalid_trackers"]) == 1
        assert result["invalid_trackers"][0]["tracker_slug"] == "z-evil"
        assert "book_slug" in result["invalid_trackers"][0]["error"]

    def test_skips_unreadable_tracker_and_reports_it_in_invalid_trackers(self, mock_config, content_root: Path):
        # Review finding L-4 on issue #549: a non-UTF-8 tracker file must
        # not abort the whole listing any more than an invalid slug does.
        _make_tracker(content_root, "my-series", "a-good", recurs_in=["B1"])
        chars_dir = content_root / "series" / "my-series" / "characters"
        (chars_dir / "z-corrupt.md").write_bytes(b"\xff\xfe\x00\x01garbage")

        result = json.loads(list_series_trackers_for_book("my-series", "B1"))
        assert "error" not in result
        slugs = [t["tracker_slug"] for t in result["trackers"]]
        assert slugs == ["a-good"]
        assert len(result["invalid_trackers"]) == 1
        assert result["invalid_trackers"][0]["tracker_slug"] == "z-corrupt"

    def test_skips_malicious_tracker_sorted_before_a_good_one(self, mock_config, content_root: Path):
        # Test-gap closed after the branch's own test-execution report
        # (Q2): every prior malicious-tracker test at this layer sorted
        # the bad tracker AFTER the good one.
        _make_tracker(
            content_root,
            "my-series",
            "a-evil",
            book_slug="../../../../tmp/pwned-router",
            recurs_in=["B1"],
        )
        _make_tracker(content_root, "my-series", "z-good", recurs_in=["B1"])

        result = json.loads(list_series_trackers_for_book("my-series", "B1"))
        assert "error" not in result
        slugs = [t["tracker_slug"] for t in result["trackers"]]
        assert slugs == ["z-good"]
        assert len(result["invalid_trackers"]) == 1
        assert result["invalid_trackers"][0]["tracker_slug"] == "a-evil"
