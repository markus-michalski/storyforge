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
    vocab_words: list[str] | None = None,
    tic_texts: list[str] | None = None,
) -> Path:
    """Create a fake ~/.storyforge tree with DB donts (vocab) and tic rows.

    ``vocab_words`` seeds flat literal-phrase ``donts`` rows — the same
    source ``load_author_vocab()`` reads since Issue #604 (previously a
    ``vocabulary.md`` file write). Defaults to ``["delve"]`` to preserve
    every existing caller's incidental non-empty vocab source.
    """
    import sqlite3

    from tools.db.connection import ensure_authors_schema

    home = tmp_path / ".storyforge"
    author_dir = home / "authors" / slug
    author_dir.mkdir(parents=True)

    db_dir = home / "db"
    db_dir.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(db_dir / "authors.db"))
    ensure_authors_schema(conn)
    for word in (vocab_words if vocab_words is not None else ["delve"]):
        conn.execute(
            "INSERT OR IGNORE INTO author_discoveries "
            "(author_slug, discovery_type, text) VALUES (?, ?, ?)",
            (slug, "donts", word),
        )
    for text in (tic_texts or []):
        conn.execute(
            "INSERT OR IGNORE INTO author_discoveries "
            "(author_slug, discovery_type, text) VALUES (?, ?, ?)",
            (slug, "recurring_tics", text),
        )
    conn.commit()
    conn.close()

    return home


@pytest.fixture
def patch_storyforge_home(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Redirect ``Path.home()/.storyforge`` lookups to ``tmp_path``.

    ``load_author_vocab`` and ``load_author_writing_discoveries`` accept a
    ``storyforge_home`` override but the public ``collect_banned_phrases``
    helper does not — patching ``Path.home`` is the smallest seam.
    Also redirects DB_DIR so tests don't touch ~/.storyforge/db/.
    """
    import tools.db.connection as _conn
    monkeypatch.setattr(_conn, "DB_DIR", tmp_path / "db")
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
            tic_texts=['**Vague-noun "thing" als Fallback** — concretize. _(emerged from firelight, 2026-05)_'],
        )

        result = collect_banned_phrases(book, PLUGIN_ROOT)
        phrases = [r["phrase"] for r in result]
        assert "thing" in phrases

    def test_writing_discoveries_severity_is_block(self, tmp_path, patch_storyforge_home):
        book = _make_book(tmp_path)
        _make_author_home(
            tmp_path,
            tic_texts=['**Vague-noun "thing" als Fallback** — concretize.'],
        )
        result = collect_banned_phrases(book, PLUGIN_ROOT)
        thing_entry = next(r for r in result if r["phrase"] == "thing")
        assert thing_entry["severity"] == "block"

    def test_source_string_identifies_writing_discoveries(self, tmp_path, patch_storyforge_home):
        book = _make_book(tmp_path)
        _make_author_home(
            tmp_path,
            tic_texts=['**"thing"** — concretize.'],
        )
        result = collect_banned_phrases(book, PLUGIN_ROOT)
        thing_entry = next(r for r in result if r["phrase"] == "thing")
        assert "writing discoveries" in thing_entry["source"].lower()

    def test_dedups_against_book_rules(self, tmp_path, patch_storyforge_home):
        """If a phrase is in both book_rules DB AND author Writing Discoveries,
        it appears once — book wins (higher priority source)."""
        import sqlite3

        book = _make_book(tmp_path)
        _make_author_home(
            tmp_path,
            tic_texts=['**"thing"** — concretize.'],
        )

        # Seed the book's DB rule (DB_DIR already patched via patch_storyforge_home).
        db_dir = patch_storyforge_home / "db"
        db_dir.mkdir(parents=True, exist_ok=True)
        conn = sqlite3.connect(str(db_dir / "test-book.db"))
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS book_rules (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                book_num INTEGER,
                rule_type TEXT NOT NULL,
                text TEXT NOT NULL,
                added_at TEXT DEFAULT '',
                UNIQUE(book_num, rule_type, text)
            )
            """
        )
        conn.execute(
            "INSERT OR IGNORE INTO book_rules (book_num, rule_type, text) VALUES (?, ?, ?)",
            (1, "rule", "Avoid `thing` — concretize."),
        )
        conn.commit()
        conn.close()

        result = collect_banned_phrases(book, PLUGIN_ROOT)
        thing_entries = [r for r in result if r["phrase"] == "thing"]
        assert len(thing_entries) == 1
        # book_rules DB is the higher-priority source.
        assert "book" in thing_entries[0]["source"].lower()

    def test_dedups_against_author_vocabulary(self, tmp_path, patch_storyforge_home):
        """Vocabulary entries also win over Writing Discoveries (same author,
        different DB discovery_type — vocabulary is the canonical phrase
        store)."""
        book = _make_book(tmp_path)
        _make_author_home(
            tmp_path,
            vocab_words=["thing"],
            tic_texts=['**"thing"** — concretize.'],
        )
        result = collect_banned_phrases(book, PLUGIN_ROOT)
        thing_entries = [r for r in result if r["phrase"] == "thing"]
        assert len(thing_entries) == 1
        assert "vocabulary" in thing_entries[0]["source"].lower()

    def test_falls_back_to_bold_title_when_no_inner_quote(self, tmp_path, patch_storyforge_home):
        book = _make_book(tmp_path)
        _make_author_home(
            tmp_path,
            tic_texts=['**Opened his mouth. Closed it.** — vary.'],
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
        # DB rows exist for ethan-cole, but the book doesn't point at any author.
        _make_author_home(
            tmp_path,
            tic_texts=['**"thing"** — concretize.'],
        )
        result = collect_banned_phrases(book, PLUGIN_ROOT)
        phrases = [r["phrase"] for r in result]
        assert "thing" not in phrases


# ---------------------------------------------------------------------------
# Book-rule severity uses classify_rule — not hardcoded "block" (Issue #453)
# ---------------------------------------------------------------------------


def _seed_book_rules(db_dir: "Path", book_slug: str, rules: list[str]) -> None:
    """Insert book rules into the SQLite DB used by _read_book_rules."""
    import sqlite3
    db_dir.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(db_dir / f"{book_slug}.db"))
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS book_rules (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            book_num INTEGER,
            rule_type TEXT NOT NULL,
            text TEXT NOT NULL,
            added_at TEXT DEFAULT '',
            UNIQUE(book_num, rule_type, text)
        )
        """
    )
    for rule in rules:
        conn.execute(
            "INSERT OR IGNORE INTO book_rules (book_num, rule_type, text) VALUES (?, ?, ?)",
            (1, "rule", rule),
        )
    conn.commit()
    conn.close()


class TestBookRuleSeverity:
    def test_ban_cued_rule_is_block(self, tmp_path, patch_storyforge_home):
        """``Avoid `phrase` — reason`` is block (ban-cue word + backtick)."""
        book = _make_book(tmp_path, author="ethan-cole")
        _make_author_home(tmp_path)
        _seed_book_rules(
            patch_storyforge_home / "db",
            "test-book",
            ["Avoid `zz-block-phrase` — test block rule"],
        )
        result = collect_banned_phrases(book, PLUGIN_ROOT)
        entry = next((r for r in result if r["phrase"] == "zz-block-phrase"), None)
        assert entry is not None, "Expected zz-block-phrase in output"
        assert entry["severity"] == "block"

    def test_watch_for_rule_is_advisory(self, tmp_path, patch_storyforge_home):
        """``Watch for `phrase` — reason`` is advisory (watch-cue, not ban-cue)."""
        book = _make_book(tmp_path, author="ethan-cole")
        _make_author_home(tmp_path)
        _seed_book_rules(
            patch_storyforge_home / "db",
            "test-book",
            ["Watch for `zz-advisory-phrase` — test advisory rule"],
        )
        result = collect_banned_phrases(book, PLUGIN_ROOT)
        entry = next((r for r in result if r["phrase"] == "zz-advisory-phrase"), None)
        assert entry is not None, "Expected zz-advisory-phrase in output"
        # advisory severity must match rules_to_honor — no longer hardcoded "block"
        assert entry["severity"] == "advisory", (
            f"Watch-for rule must be advisory, got: {entry['severity']}"
        )

    @pytest.mark.parametrize("rule,expected", [
        # English ban cues
        ("Avoid `ascii-apos` — reason", "block"),
        ("Don't use `ascii-dont` — reason", "block"),        # ASCII apostrophe
        ("Don’t use `curly-dont` — reason", "block"),  # curly apostrophe
        ("Never use `never-phrase`", "block"),
        ("banned: `banned-phrase`", "block"),
        # German ban cues
        ("Vermeide `german-phrase` — reason", "block"),
        ("Vermeiden: `german-inf`", "block"),
        ("Niemals `niemals-phrase` verwenden", "block"),
        ("Kein `kein-phrase` mehr schreiben", "block"),
        ("Nicht mehr verwenden: `nicht-phrase`", "block"),
        ("Das Wort ist verboten: `verboten-phrase`", "block"),
        # Non-ban cues (advisory)
        ("Watch for `watch-phrase` — use sparingly", "advisory"),
        ("Use `quotes` for emphasis", "advisory"),
        ("Note: `note-phrase` can work well", "advisory"),
    ])
    def test_classify_rule_cue_table(self, tmp_path, patch_storyforge_home, rule, expected):
        """classify_rule covers English + German ban cues and non-ban advisory patterns."""
        book = _make_book(tmp_path, author="ethan-cole")
        _make_author_home(tmp_path)
        _seed_book_rules(patch_storyforge_home / "db", "test-book", [rule])
        result = collect_banned_phrases(book, PLUGIN_ROOT)
        # Extract the first backtick-phrase from the rule as the phrase key
        import re
        m = re.search(r"`([^`]+)`", rule)
        if m is None:
            pytest.skip("No backtick phrase in rule")
        phrase = m.group(1)
        entry = next((r for r in result if r["phrase"] == phrase), None)
        if expected == "advisory":
            # advisory entries may not appear in banned_phrases at all — that is correct
            assert entry is None or entry["severity"] == "advisory", (
                f"Rule '{rule}' produced severity={entry['severity'] if entry else 'absent'}, expected advisory"
            )
        else:
            assert entry is not None, f"Expected phrase '{phrase}' in output for rule: {rule!r}"
            assert entry["severity"] == expected, (
                f"Rule '{rule}' produced severity={entry['severity']}, expected {expected}"
            )
