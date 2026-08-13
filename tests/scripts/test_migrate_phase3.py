"""Tests for scripts/migrate_phase3.py — Issue #584."""

from __future__ import annotations

import json
import sqlite3
import sys
from pathlib import Path

import pytest

import scripts.migrate_phase3 as migrate_phase3

# DB_DIR isolation comes from tests/conftest.py's autouse _isolate_db_dir
# fixture — no local fixture needed here.


def _book(root_dir: Path, slug: str, *, series: str = "", series_number: object = None) -> Path:
    root = root_dir / slug
    (root / "characters").mkdir(parents=True)
    lines = ["---", f"title: {slug}", f"slug: {slug}"]
    if series:
        lines.append(f'series: "{series}"')
    if series_number is not None:
        lines.append(f"series_number: {series_number}")
    lines.append("---\n")
    (root / "README.md").write_text("\n".join(lines), encoding="utf-8")
    return root


def _write_char_snapshot(book_root: Path, char_slug: str, *, inventory: list[str]) -> None:
    char_file = book_root / "characters" / f"{char_slug}.md"
    inv = ", ".join(f'"{i}"' for i in inventory)
    char_file.write_text(
        f"---\nname: {char_slug}\ncurrent_inventory: [{inv}]\nas_of_chapter: \"02-test\"\n---\n\nBody.\n",
        encoding="utf-8",
    )


class TestMigrateCharacterSnapshotsSkipsUnlinkedSeriesBooks:
    """Issue #584: get_book_num() (Issue #579) now raises
    BookNotLinkedToSeriesError for a book with series set but
    series_number=0. Without a catch, the per-book loop died on the first
    such book — books before it stayed committed, books after it were
    silently never attempted."""

    def test_skips_and_continues_past_unlinked_book(self, tmp_path, capsys):
        content_root = tmp_path / "content"
        projects_dir = content_root / "projects"
        projects_dir.mkdir(parents=True)

        good_book = _book(projects_dir, "aaa-good-book")
        _write_char_snapshot(good_book, "theo", inventory=["compass"])

        unlinked_book = _book(projects_dir, "unlinked-book", series="my-series", series_number=0)
        _write_char_snapshot(unlinked_book, "kael", inventory=["should-not-crash-the-run"])

        # Sorts after "unlinked-book" — proves the loop resumes past a
        # failure, not just that it doesn't crash on books seen before it.
        later_book = _book(projects_dir, "zzz-later-book")
        _write_char_snapshot(later_book, "mira", inventory=["lantern"])

        migrate_phase3.migrate_character_snapshots(content_root, dry_run=True)

        out = capsys.readouterr().out
        assert "SKIP: unlinked-book" in out
        assert "my-series" in out
        assert "theo" in out
        # The book scheduled AFTER the failure must also have been reached.
        assert "mira" in out

    def test_reaches_books_nested_under_series_tree(self, tmp_path, capsys):
        """Issue #584 (HIGH-1 of the code review): the pre-fix loop only
        ever scanned content_root/projects/ directly. But a book created
        via create_book_structure(series_slug=...) — the population that
        actually gets series_number: 0, i.e. the one this whole fix exists
        for — is scaffolded under content_root/series/{slug}/{book}/, not
        projects/ (servers/storyforge-server/routers/creation.py). A
        projects/-only scan would never reach the books most likely to
        need the skip-and-continue behavior at all. find_projects() covers
        both trees (Issue #279)."""
        content_root = tmp_path / "content"
        series_dir = content_root / "series" / "my-series"
        series_dir.mkdir(parents=True)

        # Properly linked series book (series_number != 0) — must be reached.
        linked_book = _book(series_dir, "book-one", series="my-series", series_number=1)
        _write_char_snapshot(linked_book, "elena", inventory=["map"])

        # Freshly scaffolded, not yet linked — must be skipped, not crash the run.
        unlinked_book = _book(series_dir, "book-two", series="my-series", series_number=0)
        _write_char_snapshot(unlinked_book, "dax", inventory=["should-not-appear"])

        migrate_phase3.migrate_character_snapshots(content_root, dry_run=True)

        out = capsys.readouterr().out
        assert "elena" in out
        assert "SKIP: book-two" in out

    def test_dry_run_false_does_not_leak_prior_book_num_into_next_book(
        self, tmp_path, capsys
    ):
        """Issue #584 (MEDIUM-2 of the code review): the skip must actually
        `continue` the loop. Without it, in execute mode, the next book's
        upsert_snapshot() call would run with `book_num` still holding the
        PREVIOUS iteration's value (a bare Python loop variable, not
        reset) — silently writing that book's snapshot under someone
        else's book_num. Real data corruption, not just a crash."""
        content_root = tmp_path / "content"
        projects_dir = content_root / "projects"
        projects_dir.mkdir(parents=True)

        # book_num=7 so a leak is unambiguous (not confusable with the
        # default book_num=1 a missing/absent series would also produce).
        leaky_source = _book(projects_dir, "aaa-book-num-7", series="shared-series", series_number=7)
        _write_char_snapshot(leaky_source, "shared-char", inventory=["should-not-leak"])

        unlinked_book = _book(projects_dir, "mmm-unlinked-book", series="shared-series", series_number=0)
        _write_char_snapshot(unlinked_book, "kael", inventory=["irrelevant"])

        victim = _book(projects_dir, "zzz-victim-book", series="shared-series", series_number=2)
        _write_char_snapshot(victim, "shared-char", inventory=["victims-real-inventory"])

        migrate_phase3.migrate_character_snapshots(content_root, dry_run=False)

        out = capsys.readouterr().out
        assert "SKIP: mmm-unlinked-book" in out

        conn = sqlite3.connect(str(tmp_path / "db" / "shared-series.db"))
        conn.row_factory = sqlite3.Row
        rows = [
            (r["char_slug"], r["book_num"], json.loads(r["inventory"]))
            for r in conn.execute("SELECT char_slug, book_num, inventory FROM character_snapshots")
        ]
        conn.close()

        # Both real books' own rows must be exactly as written — proves the
        # skip didn't also corrupt or drop unrelated, successfully-processed
        # books sharing the same char_slug ("shared-char") in different
        # books_num.
        assert ("shared-char", 7, ["should-not-leak"]) in rows
        assert ("shared-char", 2, ["victims-real-inventory"]) in rows
        # The skipped book's own character ("kael") must never be written
        # at all — not under its own book_num (unresolvable, that's why it
        # was skipped) and not under a stale book_num carried over from the
        # PREVIOUS successful iteration (book_num=7, a bare Python loop
        # variable that survives past a `continue`-less exception handler).
        kael_rows = [r for r in rows if r[0] == "kael"]
        assert kael_rows == [], f"unlinked book's character was written under a leaked book_num: {kael_rows}"

    def test_returns_skip_count(self, tmp_path):
        """Issue #588: the per-book SKIP lines scroll away on a real run —
        the return value is what main() uses to decide the process exit
        code, so it must actually reflect how many books were skipped."""
        content_root = tmp_path / "content"
        projects_dir = content_root / "projects"
        projects_dir.mkdir(parents=True)

        good_book = _book(projects_dir, "aaa-good-book")
        _write_char_snapshot(good_book, "theo", inventory=["compass"])

        unlinked_a = _book(projects_dir, "unlinked-a", series="my-series", series_number=0)
        _write_char_snapshot(unlinked_a, "kael", inventory=["x"])

        unlinked_b = _book(projects_dir, "unlinked-b", series="other-series", series_number=0)
        _write_char_snapshot(unlinked_b, "dax", inventory=["y"])

        skipped = migrate_phase3.migrate_character_snapshots(content_root, dry_run=True)

        assert skipped == 2

    def test_returns_zero_when_nothing_skipped(self, tmp_path):
        content_root = tmp_path / "content"
        projects_dir = content_root / "projects"
        projects_dir.mkdir(parents=True)
        good_book = _book(projects_dir, "aaa-good-book")
        _write_char_snapshot(good_book, "theo", inventory=["compass"])

        skipped = migrate_phase3.migrate_character_snapshots(content_root, dry_run=True)

        assert skipped == 0

    def test_dry_run_and_execute_agree_on_malformed_slug_skip_count(self, tmp_path, capsys):
        """Issue #588 code review, L-4: open_canon_db() — the call that
        validates a series value as a filesystem-safe slug and raises
        SlugValidationError for e.g. a stray "/" — previously only ran when
        not dry_run. get_book_num() alone doesn't catch a malformed (but
        nonzero) series_number, so a --dry-run pre-flight check could
        report 0 skips while the real --execute run on the same content
        root skips a book and exits 1 — undermining dry-run's whole
        purpose as a preview. Both modes must now agree."""
        content_root = tmp_path / "content"
        projects_dir = content_root / "projects"
        projects_dir.mkdir(parents=True)

        # series_number=1 (valid, nonzero) so get_book_num() doesn't raise
        # BookNotLinkedToSeriesError — isolates the SlugValidationError
        # path this fix is specifically about.
        malformed = _book(projects_dir, "malformed-book", series="a/b", series_number=1)
        _write_char_snapshot(malformed, "kael", inventory=["x"])

        skipped_dry_run = migrate_phase3.migrate_character_snapshots(content_root, dry_run=True)
        skipped_execute = migrate_phase3.migrate_character_snapshots(content_root, dry_run=False)

        assert skipped_dry_run == 1
        assert skipped_execute == 1


class TestMainExitsNonzeroOnSkips:
    """Issue #588: a cron/CI-invoked migration run must not report clean
    success when books were silently skipped — the SKIP lines above scroll
    away, but the exit code doesn't."""

    def test_main_exits_nonzero_when_books_skipped(self, tmp_path, capsys, monkeypatch):
        storyforge_home = tmp_path / "storyforge_home"
        (storyforge_home / "authors").mkdir(parents=True)
        content_root = tmp_path / "content"
        projects_dir = content_root / "projects"
        projects_dir.mkdir(parents=True)

        unlinked_book = _book(projects_dir, "unlinked-book", series="my-series", series_number=0)
        _write_char_snapshot(unlinked_book, "kael", inventory=["irrelevant"])

        monkeypatch.setattr(
            sys,
            "argv",
            [
                "migrate_phase3.py",
                "--dry-run",
                "--storyforge-home",
                str(storyforge_home),
                "--content-root",
                str(content_root),
            ],
        )

        with pytest.raises(SystemExit) as exc_info:
            migrate_phase3.main()
        assert exc_info.value.code == 1

        out = capsys.readouterr().out
        assert "SKIP: unlinked-book" in out
        assert "1 book(s) skipped" in out

    def test_main_does_not_exit_when_nothing_skipped(self, tmp_path, capsys, monkeypatch):
        storyforge_home = tmp_path / "storyforge_home"
        (storyforge_home / "authors").mkdir(parents=True)
        content_root = tmp_path / "content"
        projects_dir = content_root / "projects"
        projects_dir.mkdir(parents=True)

        good_book = _book(projects_dir, "aaa-good-book")
        _write_char_snapshot(good_book, "theo", inventory=["compass"])

        monkeypatch.setattr(
            sys,
            "argv",
            [
                "migrate_phase3.py",
                "--dry-run",
                "--storyforge-home",
                str(storyforge_home),
                "--content-root",
                str(content_root),
            ],
        )

        migrate_phase3.main()  # must NOT raise SystemExit

        out = capsys.readouterr().out
        assert "book(s) skipped" not in out
