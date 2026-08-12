"""Tests for ``recurring_chars_for_book`` helper (Issue #196).

The helper surfaces which series-trackers belong in a given book band
(``B1`` / ``B2`` / ...) so the new-book auto-copy logic and the future
D-2 bootstrap skill know exactly which character files to handle.

Each entry mirrors the output of ``parse_series_tracker`` plus a
``prior_bands`` field — bands in ``recurs_in`` that come before the
target band — used to determine whether the character has a source
file in any prior book.
"""

from __future__ import annotations

from pathlib import Path

from tools.state.loaders.series import RE_BAND_ID, recurring_chars_for_book


def _write_tracker(
    chars_dir: Path,
    slug: str,
    *,
    name: str | None = None,
    role: str = "supporting",
    book_slug: str | None = None,
    recurs_in: list[str] | None = None,
) -> Path:
    chars_dir.mkdir(parents=True, exist_ok=True)
    book_slug_line = f"book_slug: {book_slug}\n" if book_slug else ""
    fm = (
        "---\n"
        f"name: {name or slug}\n"
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


class TestRecurringCharsForBook:
    def test_returns_only_trackers_recurring_in_band(self, tmp_path: Path) -> None:
        chars = tmp_path / "characters"
        _write_tracker(chars, "kael", recurs_in=["B1", "B2", "B3"])
        _write_tracker(chars, "viktor", recurs_in=["B1", "B2"])
        # Only-B1 char (e.g. dies in B1) — must be excluded for B2 query.
        _write_tracker(chars, "sera", recurs_in=["B1"])

        result, errors = recurring_chars_for_book(tmp_path, "B2")
        slugs = sorted(t["tracker_slug"] for t in result)
        assert slugs == ["kael", "viktor"]
        assert errors == []

    def test_includes_band_only_chars(self, tmp_path: Path) -> None:
        # A character that first appears in B2 (e.g. Tristan) — recurs_in
        # starts at B2. Must be returned for B2 with empty prior_bands so
        # the caller knows there's no source to copy from.
        chars = tmp_path / "characters"
        _write_tracker(chars, "tristan", recurs_in=["B2", "B3"])
        result, errors = recurring_chars_for_book(tmp_path, "B2")
        assert len(result) == 1
        assert result[0]["tracker_slug"] == "tristan"
        assert result[0]["prior_bands"] == []
        assert errors == []

    def test_prior_bands_sorted_and_filtered(self, tmp_path: Path) -> None:
        chars = tmp_path / "characters"
        _write_tracker(chars, "kael", recurs_in=["B1", "B2", "B3"])
        result, _errors = recurring_chars_for_book(tmp_path, "B3")
        entry = result[0]
        # prior_bands = bands in recurs_in that come BEFORE B3.
        assert entry["prior_bands"] == ["B1", "B2"]

    def test_prior_bands_empty_for_first_appearance(self, tmp_path: Path) -> None:
        chars = tmp_path / "characters"
        _write_tracker(chars, "tristan", recurs_in=["B2", "B3"])
        result, _errors = recurring_chars_for_book(tmp_path, "B2")
        assert result[0]["prior_bands"] == []

    def test_returns_empty_when_no_trackers(self, tmp_path: Path) -> None:
        # No characters/ dir at all.
        assert recurring_chars_for_book(tmp_path, "B1") == ([], [])

    def test_returns_empty_when_dir_empty(self, tmp_path: Path) -> None:
        (tmp_path / "characters").mkdir()
        assert recurring_chars_for_book(tmp_path, "B1") == ([], [])

    def test_rejects_band_with_trailing_newline(self) -> None:
        """Issue #525: `$` in RE_BAND_ID matches before a trailing newline,
        so "B1\\n" passed the top-level guard in recurring_chars_for_book()
        despite never appearing verbatim in any tracker's clean recurs_in
        list — a silent-data-loss failure mode distinct from (but adjacent
        to) the write_evolution_section() corruption path this issue also
        covers. Anchoring with \\Z closes the gap at the source."""
        assert RE_BAND_ID.match("B1\n") is None
        assert RE_BAND_ID.match("B1") is not None

    def test_excludes_index_md(self, tmp_path: Path) -> None:
        chars = tmp_path / "characters"
        _write_tracker(chars, "kael", recurs_in=["B1", "B2"])
        chars.mkdir(parents=True, exist_ok=True)
        (chars / "INDEX.md").write_text("---\nslug: index\nrecurs_in: [B1, B2]\n---\n", encoding="utf-8")
        result, _errors = recurring_chars_for_book(tmp_path, "B2")
        slugs = [t["tracker_slug"] for t in result]
        assert "kael" in slugs
        assert "index" not in slugs

    def test_carries_book_slug_for_resolver(self, tmp_path: Path) -> None:
        # Tracker with book_slug ≠ tracker slug (the #194 case).
        chars = tmp_path / "characters"
        _write_tracker(
            chars,
            "king-caelan",
            book_slug="caelan",
            recurs_in=["B1", "B2", "B3"],
        )
        result, _errors = recurring_chars_for_book(tmp_path, "B2")
        assert result[0]["tracker_slug"] == "king-caelan"
        assert result[0]["book_slug"] == "caelan"

    def test_falls_back_to_tracker_slug_when_book_slug_absent(self, tmp_path: Path) -> None:
        chars = tmp_path / "characters"
        _write_tracker(chars, "kael", recurs_in=["B1", "B2"])
        result, _errors = recurring_chars_for_book(tmp_path, "B2")
        assert result[0]["tracker_slug"] == "kael"
        assert result[0]["book_slug"] == "kael"

    def test_invalid_band_returns_empty(self, tmp_path: Path) -> None:
        # Non-band string — defensive: returns empty list rather than
        # exception.
        chars = tmp_path / "characters"
        _write_tracker(chars, "kael", recurs_in=["B1", "B2"])
        assert recurring_chars_for_book(tmp_path, "Book1") == ([], [])

    def test_results_sorted_by_tracker_slug(self, tmp_path: Path) -> None:
        # Stable ordering helps deterministic skill output.
        chars = tmp_path / "characters"
        _write_tracker(chars, "viktor", recurs_in=["B1", "B2"])
        _write_tracker(chars, "kael", recurs_in=["B1", "B2"])
        _write_tracker(chars, "dominic", recurs_in=["B1", "B2"])
        result, _errors = recurring_chars_for_book(tmp_path, "B2")
        slugs = [t["tracker_slug"] for t in result]
        assert slugs == sorted(slugs)

    def test_skips_malicious_tracker_and_surfaces_error(self, tmp_path: Path) -> None:
        # Issue #549: a single hand-edited/pre-#524 tracker with a
        # traversal book_slug must not abort the whole call — it's
        # skipped and reported in `errors`, the well-formed trackers
        # around it are still returned in `trackers`.
        chars = tmp_path / "characters"
        _write_tracker(chars, "a-good", recurs_in=["B1", "B2"])
        _write_tracker(
            chars,
            "z-evil",
            book_slug="../../../../tmp/pwned",
            recurs_in=["B1", "B2"],
        )
        result, errors = recurring_chars_for_book(tmp_path, "B2")
        slugs = [t["tracker_slug"] for t in result]
        assert slugs == ["a-good"]
        assert len(errors) == 1
        assert errors[0]["tracker_slug"] == "z-evil"
        assert "book_slug" in errors[0]["error"]

    def test_skips_unreadable_tracker_file(self, tmp_path: Path) -> None:
        # Review finding L-4 on issue #549: a non-UTF-8 tracker file must
        # not abort the whole call any more than an invalid slug does —
        # same bug shape, narrower trigger (a corrupt/foreign-encoding
        # file predating this repo's UTF-8-only convention).
        chars = tmp_path / "characters"
        _write_tracker(chars, "a-good", recurs_in=["B1", "B2"])
        (chars / "z-corrupt.md").write_bytes(b"\xff\xfe\x00\x01garbage")
        result, errors = recurring_chars_for_book(tmp_path, "B2")
        slugs = [t["tracker_slug"] for t in result]
        assert slugs == ["a-good"]
        assert len(errors) == 1
        assert errors[0]["tracker_slug"] == "z-corrupt"

    def test_skips_malicious_tracker_sorted_before_a_good_one(self, tmp_path: Path) -> None:
        # Test-gap closed after the branch's own test-execution report
        # (Q2): every prior malicious-tracker test here sorted the bad
        # tracker AFTER the good one. The loop uses `continue`, not an
        # early return or eager comprehension, so order shouldn't matter
        # — this pins that for the sibling function that matters most
        # (find_tracker_for_book_character's own before/after test exists
        # precisely because order DID matter there pre-fix).
        chars = tmp_path / "characters"
        _write_tracker(chars, "a-evil", book_slug="../../../../tmp/pwned3", recurs_in=["B1", "B2"])
        _write_tracker(chars, "z-good", recurs_in=["B1", "B2"])
        result, errors = recurring_chars_for_book(tmp_path, "B2")
        slugs = [t["tracker_slug"] for t in result]
        assert slugs == ["z-good"]
        assert len(errors) == 1
        assert errors[0]["tracker_slug"] == "a-evil"

    def test_reports_multiple_errors_independently(self, tmp_path: Path) -> None:
        # Test-gap closed after the branch's own test-execution report
        # (Q1): the loader's own test file had no direct multi-error
        # test — only a router-level one (copy_recurring_chars_to_new_book's
        # test_reports_every_invalid_tracker_not_just_the_first) exercised
        # more than one bad tracker at once.
        chars = tmp_path / "characters"
        _write_tracker(chars, "a-evil", book_slug="../../../../tmp/pwned-a", recurs_in=["B1", "B2"])
        _write_tracker(chars, "m-good", recurs_in=["B1", "B2"])
        _write_tracker(chars, "z-evil", book_slug="../../../../tmp/pwned-z", recurs_in=["B1", "B2"])
        result, errors = recurring_chars_for_book(tmp_path, "B2")
        slugs = [t["tracker_slug"] for t in result]
        assert slugs == ["m-good"]
        error_slugs = {e["tracker_slug"] for e in errors}
        assert error_slugs == {"a-evil", "z-evil"}


class TestBandRegexConsolidation:
    """Issue #529: routers/series.py's _RE_BAND_ID and this module's
    RE_BAND_ID used to be byte-identical, copy-pasted compiled patterns —
    the same anchoring bug (#525) had to be fixed twice, in two files, for
    that reason. RE_BAND_ID here is now the single source of truth; the
    router imports it instead of keeping its own copy."""

    def test_router_band_regex_is_the_same_object(self) -> None:
        import sys
        from pathlib import Path

        server_dir = Path(__file__).resolve().parents[2] / "servers" / "storyforge-server"
        if str(server_dir) not in sys.path:
            sys.path.insert(0, str(server_dir))
        from routers.series import RE_BAND_ID as router_re_band_id

        assert router_re_band_id is RE_BAND_ID
