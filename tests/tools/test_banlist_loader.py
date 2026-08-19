"""Tests for ``tools.banlist_loader``.

Covers the three loaders (author-vocab, global anti-AI tells,
author-slug-from-book) and the BannedPattern dataclass.
"""

from __future__ import annotations

from pathlib import Path

from tools.banlist_loader import (
    SEVERITY_BLOCK,
    SEVERITY_WARN,
    _extract_phrases_from_bold_title,
    author_slug_from_book,
    load_author_dont_rules,
    load_author_vocab,
    load_author_writing_discoveries,
    load_global_ai_tells,
)

PLUGIN_ROOT = Path(__file__).resolve().parent.parent.parent


# ---------------------------------------------------------------------------
# _extract_phrases_from_bold_title — Issue #151 follow-up
# ---------------------------------------------------------------------------


class TestExtractPhrasesFromBoldTitle:
    """Bold-title bullets in `## Writing Discoveries` carry the scannable
    phrase inside double-quotes. The extractor must:

    - Pick all double-quoted phrases as the primary patterns
    - Fall back to the cleaned bold-title text when no quotes are present
    - Skip degenerate cases (empty title, title shorter than 2 chars)
    """

    def test_extracts_inner_double_quoted_phrase(self):
        title = '**Vague-noun "thing" als Fallback**'
        assert _extract_phrases_from_bold_title(title) == ["thing"]

    def test_extracts_multiple_inner_quotes(self):
        title = '**"count" als Tic / "for a count of X"**'
        assert _extract_phrases_from_bold_title(title) == ["count", "for a count of X"]

    def test_falls_back_to_bold_title_text_when_no_quotes(self):
        title = "**Opened his mouth. Closed it.**"
        assert _extract_phrases_from_bold_title(title) == ["Opened his mouth. Closed it."]

    def test_strips_outer_asterisks_and_whitespace(self):
        title = "  **the way als Vergleichs-Tic**  "
        assert _extract_phrases_from_bold_title(title) == ["the way als Vergleichs-Tic"]

    def test_handles_typographic_quotes(self):
        # German typographic quotes "..." should be picked up as well.
        title = '**Vague-noun „thing" als Fallback**'
        result = _extract_phrases_from_bold_title(title)
        assert "thing" in result

    def test_skips_too_short_quoted_content(self):
        title = '**"x" als Tic**'
        # Single-char quotes are noise — fall back to title text.
        result = _extract_phrases_from_bold_title(title)
        assert "x" not in result

    def test_returns_empty_for_no_bold(self):
        assert _extract_phrases_from_bold_title("not a bold title") == []
        assert _extract_phrases_from_bold_title("") == []



# ---------------------------------------------------------------------------
# author_slug_from_book
# ---------------------------------------------------------------------------


def _make_book_with_author(tmp_path: Path, author_line: str | None) -> Path:
    book = tmp_path / "test-book"
    book.mkdir()
    body = "# Test Book\n\n## Book Facts\n\n"
    if author_line:
        body += f"{author_line}\n"
    body += "- **Genre:** test\n"
    (book / "CLAUDE.md").write_text(body, encoding="utf-8")
    return book


class TestAuthorSlugFromBook:
    def test_basic_author_line(self, tmp_path):
        book = _make_book_with_author(tmp_path, "- **Author:** Ethan Cole")
        assert author_slug_from_book(book) == "ethan-cole"

    def test_author_with_parenthetical(self, tmp_path):
        book = _make_book_with_author(tmp_path, "- **Author:** Ethan Cole (Eddings-humor with Twilight-stakes)")
        assert author_slug_from_book(book) == "ethan-cole"

    def test_no_author_line(self, tmp_path):
        book = _make_book_with_author(tmp_path, None)
        assert author_slug_from_book(book) is None

    def test_no_claudemd(self, tmp_path):
        book = tmp_path / "empty-book"
        book.mkdir()
        assert author_slug_from_book(book) is None

    def test_multi_word_name(self, tmp_path):
        book = _make_book_with_author(tmp_path, "- **Author:** Ursula K. Le Guin")
        assert author_slug_from_book(book) == "ursula-k-le-guin"


# ---------------------------------------------------------------------------
# load_author_vocab — DB-backed since Issue #604 (was: vocabulary.md file)
# ---------------------------------------------------------------------------


def _seed_donts(storyforge_home: Path, author_slug: str, texts: list[str]) -> None:
    """Seed flat literal-phrase ``donts`` rows via the shared DB helper."""
    _make_authors_db(
        storyforge_home,
        author_slug,
        [{"discovery_type": "donts", "text": t} for t in texts],
    )


class TestLoadAuthorVocab:
    def test_missing_author_returns_empty(self, tmp_path):
        patterns = load_author_vocab("nonexistent", storyforge_home=tmp_path)
        assert patterns == []

    def test_empty_db_returns_empty(self, tmp_path):
        _make_authors_db(tmp_path, "alice", [])
        assert load_author_vocab("alice", storyforge_home=tmp_path) == []

    def test_parses_flat_donts_entries(self, tmp_path):
        _seed_donts(tmp_path, "alice", ["delve", "tapestry", "vibrant"])
        patterns = load_author_vocab("alice", storyforge_home=tmp_path)
        labels = [p.label for p in patterns]
        assert "delve" in labels
        assert "tapestry" in labels
        assert "vibrant" in labels
        assert all(p.severity == SEVERITY_BLOCK for p in patterns)
        assert all("author-vocab" in p.source for p in patterns)

    def test_splits_aliases_on_slash(self, tmp_path):
        _seed_donts(tmp_path, "bob", ["delve / delve into", "embark / embark on"])
        patterns = load_author_vocab("bob", storyforge_home=tmp_path)
        labels = [p.label for p in patterns]
        assert "delve" in labels
        assert "delve into" in labels
        assert "embark" in labels
        assert "embark on" in labels

    def test_strips_parenthetical_clarifications(self, tmp_path):
        _seed_donts(tmp_path, "carol", ["tapestry (metaphorical)", "landscape (metaphorical)"])
        patterns = load_author_vocab("carol", storyforge_home=tmp_path)
        labels = [p.label for p in patterns]
        assert "tapestry" in labels
        assert "landscape" in labels
        # Original parenthetical not present
        assert not any("metaphorical" in label for label in labels)

    def test_loads_multiple_entries(self, tmp_path):
        _seed_donts(
            tmp_path, "dora",
            ["delve", "it's worth noting that", "her heart raced", "in essence"],
        )
        patterns = load_author_vocab("dora", storyforge_home=tmp_path)
        labels = [p.label for p in patterns]
        assert "delve" in labels
        assert "it's worth noting that" in labels
        assert "her heart raced" in labels
        assert "in essence" in labels

    def test_dedupes_entries_that_normalize_to_the_same_label(self, tmp_path):
        # Two distinct DB rows ("delve" and "delve (informal)") both strip
        # to the same cleaned label — the loader's own seen-set must dedupe
        # them, same as it used to across two vocabulary.md sub-sections.
        _seed_donts(tmp_path, "eve", ["delve", "delve (informal)"])
        patterns = load_author_vocab("eve", storyforge_home=tmp_path)
        delves = [p for p in patterns if p.label == "delve"]
        assert len(delves) == 1

    def test_skips_short_entries(self, tmp_path):
        _seed_donts(tmp_path, "frank", ["a", "delve"])
        patterns = load_author_vocab("frank", storyforge_home=tmp_path)
        labels = [p.label for p in patterns]
        assert "delve" in labels
        assert "a" not in labels

    def test_pattern_catches_inflections_for_single_word(self, tmp_path):
        _seed_donts(tmp_path, "gina", ["delve"])
        patterns = load_author_vocab("gina", storyforge_home=tmp_path)
        delve = next(p for p in patterns if p.label == "delve")
        # Catches inflections (delved, delves, delving)
        assert delve.pattern.search("she delved into the box") is not None
        assert delve.pattern.search("she delves into") is not None
        assert delve.pattern.search("delving deep") is not None
        # Bare word still matches
        assert delve.pattern.search("she went to delve into") is not None
        # Mid-word matches NOT triggered (leading word-boundary)
        assert delve.pattern.search("the redelve was misnamed") is None
        # Case-insensitive
        assert delve.pattern.search("DELVE!") is not None
        # Unrelated word does not match
        assert delve.pattern.search("the deliverer arrived") is None

    def test_multi_word_phrase_uses_full_boundary(self, tmp_path):
        _seed_donts(tmp_path, "henrietta", ["it's worth noting that"])
        patterns = load_author_vocab("henrietta", storyforge_home=tmp_path)
        phrase = next(p for p in patterns if p.label == "it's worth noting that")
        assert phrase.pattern.search("Now it's worth noting that we tried.") is not None
        # Same phrase mid-sentence still works
        assert phrase.pattern.search("Look — it's worth noting that this fails.") is not None

    def test_other_discovery_types_do_not_leak_in(self, tmp_path):
        """Only ``donts`` rows are read — a ``style_principles`` entry for
        the same author must not surface as a vocab ban (mirrors the old
        vocabulary.md test's section-isolation guarantee)."""
        _make_authors_db(
            tmp_path, "henry",
            [
                {"discovery_type": "donts", "text": "delve"},
                {"discovery_type": "style_principles", "text": "said"},
            ],
        )
        patterns = load_author_vocab("henry", storyforge_home=tmp_path)
        labels = [p.label for p in patterns]
        assert "delve" in labels
        assert "said" not in labels

    def test_skips_backtick_wrapped_donts_entries(self, tmp_path):
        """Backtick-wrapped rows (written by write_author_banned_phrase) are
        already extracted by load_author_dont_rules() — this loader must
        skip them, not double-report the same DB row under a different
        category with a mangled label (Issue #604 review)."""
        _make_authors_db(
            tmp_path, "ivan",
            [{"discovery_type": "donts", "text": "`math` — too on the nose"}],
        )
        patterns = load_author_vocab("ivan", storyforge_home=tmp_path)
        assert patterns == []

    def test_skips_bold_titled_donts_entries(self, tmp_path):
        """Bold-titled harvest-author-rules rows are already extracted by
        load_author_dont_rules() via italic+ban-cue extraction."""
        _make_authors_db(
            tmp_path, "jane",
            [{"discovery_type": "donts", "text": "**Never use rooms** — *The room received it.*"}],
        )
        patterns = load_author_vocab("jane", storyforge_home=tmp_path)
        assert patterns == []

    def test_deleted_entry_immediately_disappears(self, tmp_path, monkeypatch):
        """Issue #604's core regression: a delete_discovery() removal must
        be reflected on the very next read — no frozen file to go stale."""
        import tools.db.connection as _db_conn
        from tools.db.author_discoveries import remove_discovery
        from tools.db.connection import open_authors_db

        _seed_donts(tmp_path, "kate", ["delve"])
        assert any(p.label == "delve" for p in load_author_vocab("kate", storyforge_home=tmp_path))

        monkeypatch.setattr(_db_conn, "DB_DIR", tmp_path / "db")
        conn = open_authors_db()
        try:
            remove_discovery(conn, author_slug="kate", discovery_type="donts", text="delve")
        finally:
            conn.close()

        assert load_author_vocab("kate", storyforge_home=tmp_path) == []


# ---------------------------------------------------------------------------
# load_global_ai_tells
# ---------------------------------------------------------------------------


class TestLoadGlobalAITells:
    def test_loads_from_real_anti_ai_patterns_md(self):
        """Sanity check against the actual repo file. Should yield > 30
        tells (the curated list is much longer)."""
        patterns = load_global_ai_tells(PLUGIN_ROOT)
        assert len(patterns) >= 30
        labels = [p.label.lower() for p in patterns]
        # Spot-check a few high-confidence entries
        assert "delve" in labels
        assert "tapestry" in labels
        assert "vibrant" in labels
        assert all(p.severity == SEVERITY_WARN for p in patterns)
        assert all(p.source == "global anti-ai" for p in patterns)

    def test_missing_file_returns_empty(self, tmp_path):
        patterns = load_global_ai_tells(tmp_path)
        assert patterns == []

    def test_parses_synthetic_section(self, tmp_path):
        # Simulate a minimal anti-ai-patterns.md
        ref = tmp_path / "reference" / "craft"
        ref.mkdir(parents=True)
        (ref / "anti-ai-patterns.md").write_text(
            "# Anti-AI Patterns\n\n"
            "## 1. Known AI Tells — Vocabulary\n\n"
            "### Heavily Flagged Words and Phrases (AI Tell Indicators)\n\n"
            "1. **Delve** / **Delve into** — One of the most notorious AI tells.\n"
            "2. **Tapestry** (metaphorical) — Almost never used by humans.\n"
            "3. **Vibrant** — Favored descriptor for colors.\n"
            "\n## 2. Other Section\n\n- something irrelevant\n",
            encoding="utf-8",
        )
        patterns = load_global_ai_tells(tmp_path)
        labels = [p.label for p in patterns]
        assert "Delve" in labels
        assert "Delve into" in labels
        assert "Tapestry" in labels
        assert "Vibrant" in labels
        # Section after `## 2.` must not be picked up.
        assert "something irrelevant" not in labels

    def test_explanation_truncated_into_reason(self, tmp_path):
        ref = tmp_path / "reference" / "craft"
        ref.mkdir(parents=True)
        long_expl = "Lorem ipsum " * 20
        (ref / "anti-ai-patterns.md").write_text(
            f"### Heavily Flagged Words and Phrases (X)\n\n1. **Delve** — {long_expl}\n",
            encoding="utf-8",
        )
        patterns = load_global_ai_tells(tmp_path)
        delve = next(p for p in patterns if p.label == "Delve")
        assert len(delve.reason) <= 120


# ---------------------------------------------------------------------------
# DB-first path: load_author_writing_discoveries from author_discoveries table
# ---------------------------------------------------------------------------


def _make_authors_db(storyforge_home: Path, author_slug: str, rows: list[dict]) -> None:
    """Create authors.db with the minimal schema and insert test rows."""
    import sqlite3
    db_dir = storyforge_home / "db"
    db_dir.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(db_dir / "authors.db"))
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS author_discoveries (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            author_slug TEXT NOT NULL,
            discovery_type TEXT NOT NULL,
            text TEXT NOT NULL,
            book_slug TEXT DEFAULT '',
            source_genres TEXT DEFAULT '',
            universal BOOLEAN DEFAULT FALSE,
            example TEXT DEFAULT '',
            date_added TEXT DEFAULT '',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(author_slug, discovery_type, text)
        )
        """
    )
    for row in rows:
        conn.execute(
            "INSERT OR IGNORE INTO author_discoveries "
            "(author_slug, discovery_type, text) VALUES (?, ?, ?)",
            (author_slug, row["discovery_type"], row["text"]),
        )
    conn.commit()
    conn.close()


class TestLoadAuthorWritingDiscoveriesFromDB:
    """DB-first path: discoveries stored in author_discoveries table."""

    def test_reads_from_db_when_present(self, tmp_path):
        _make_authors_db(
            tmp_path,
            "ethan-cole",
            [{"discovery_type": "recurring_tics", "text": '**"thing"** — concretize.'}],
        )
        patterns = load_author_writing_discoveries("ethan-cole", storyforge_home=tmp_path)
        assert any(p.label == "thing" for p in patterns)

    def test_db_wins_over_profile_md(self, tmp_path):
        """When DB exists, profile.md body is ignored — no double-loading."""
        _make_authors_db(
            tmp_path,
            "ethan-cole",
            [{"discovery_type": "recurring_tics", "text": '**"db-phrase"** — from DB.'}],
        )
        # Write a conflicting phrase into profile.md body.
        author_dir = tmp_path / "authors" / "ethan-cole"
        author_dir.mkdir(parents=True, exist_ok=True)
        (author_dir / "profile.md").write_text(
            '---\nname: "Ethan Cole"\n---\n\n'
            "## Writing Discoveries\n\n"
            "### Recurring Tics\n\n"
            "- **\"md-only-phrase\"** — only in profile.md.\n",
            encoding="utf-8",
        )
        patterns = load_author_writing_discoveries("ethan-cole", storyforge_home=tmp_path)
        labels = [p.label for p in patterns]
        assert "db-phrase" in labels
        assert "md-only-phrase" not in labels  # profile.md ignored when DB present

    def test_db_source_string_contains_writing_discoveries(self, tmp_path):
        _make_authors_db(
            tmp_path,
            "ethan-cole",
            [{"discovery_type": "recurring_tics", "text": '**"thing"** — fix.'}],
        )
        patterns = load_author_writing_discoveries("ethan-cole", storyforge_home=tmp_path)
        assert all("writing discoveries" in p.source.lower() for p in patterns)

    def test_empty_db_returns_empty_list(self, tmp_path):
        """DB present but no rows → empty list (not fallback to profile.md)."""
        _make_authors_db(tmp_path, "ethan-cole", [])
        # Write discoveries into profile.md to confirm it's NOT used.
        author_dir = tmp_path / "authors" / "ethan-cole"
        author_dir.mkdir(parents=True, exist_ok=True)
        (author_dir / "profile.md").write_text(
            '---\nname: "Ethan Cole"\n---\n\n'
            "## Writing Discoveries\n\n"
            "### Recurring Tics\n\n"
            "- **\"md-phrase\"** — should be ignored.\n",
            encoding="utf-8",
        )
        patterns = load_author_writing_discoveries("ethan-cole", storyforge_home=tmp_path)
        assert patterns == []

    def test_db_absent_returns_empty(self, tmp_path):
        """No authors.db → empty list. profile.md is not consulted."""
        author_dir = tmp_path / "authors" / "ethan-cole"
        author_dir.mkdir(parents=True, exist_ok=True)
        (author_dir / "profile.md").write_text(
            '---\nname: "Ethan Cole"\n---\n\n'
            "## Writing Discoveries\n\n"
            "### Recurring Tics\n\n"
            '- **"profile-phrase"** — must be ignored.\n',
            encoding="utf-8",
        )
        patterns = load_author_writing_discoveries("ethan-cole", storyforge_home=tmp_path)
        assert patterns == []

    def test_body_extraction_works_from_db(self, tmp_path):
        """Body-quoted phrases (German rule name + English examples) work via DB too."""
        _make_authors_db(
            tmp_path,
            "ethan-cole",
            [
                {
                    "discovery_type": "recurring_tics",
                    "text": (
                        "**Abstrakte Körperteil-Anthropomorphisierung** — "
                        '"his hands were having a conversation with each other".'
                    ),
                }
            ],
        )
        patterns = load_author_writing_discoveries("ethan-cole", storyforge_home=tmp_path)
        labels = [p.label for p in patterns]
        assert "his hands were having a conversation with each other" in labels
        assert "Abstrakte Körperteil-Anthropomorphisierung" not in labels

    def test_body_backtick_regex_from_db(self, tmp_path):
        """Backtick patterns in DB text load as regex — same heuristic as profile.md path."""
        _make_authors_db(
            tmp_path,
            "ethan-cole",
            [
                {
                    "discovery_type": "recurring_tics",
                    "text": (
                        r"**Body part as subject** — Körperteil-Subjekt: "
                        r"`\b(his|her) (hand|hands|breath|stomach) (was|were) (having|not|kept)\b`"
                    ),
                }
            ],
        )
        patterns = load_author_writing_discoveries("ethan-cole", storyforge_home=tmp_path)
        assert patterns, "expected at least one pattern from body backtick"
        assert any(
            p.pattern.search("his hands were having a conversation") for p in patterns
        )

    def test_title_quotes_take_priority_over_body_quotes_db(self, tmp_path):
        """Title-quoted phrase wins; body quotes are NOT added when title has quotes."""
        _make_authors_db(
            tmp_path,
            "ethan-cole",
            [
                {
                    "discovery_type": "recurring_tics",
                    "text": (
                        '**Vague-noun "thing" als Fallback** — concretize. '
                        'Example: "the thing happened".'
                    ),
                }
            ],
        )
        patterns = load_author_writing_discoveries("ethan-cole", storyforge_home=tmp_path)
        labels = [p.label for p in patterns]
        assert "thing" in labels
        assert "the thing happened" not in labels

    def test_falls_back_to_title_text_when_nothing_extractable_db(self, tmp_path):
        """English-prose bold-title tic with no quotes/backticks → title text is pattern."""
        _make_authors_db(
            tmp_path,
            "ethan-cole",
            [
                {
                    "discovery_type": "recurring_tics",
                    "text": "**Opened his mouth. Closed it.** — vary or skip.",
                }
            ],
        )
        patterns = load_author_writing_discoveries("ethan-cole", storyforge_home=tmp_path)
        labels = [p.label for p in patterns]
        assert "Opened his mouth. Closed it." in labels

    def test_body_pattern_matches_chapter_prose_db(self, tmp_path):
        """Body-quoted phrase compiles to a pattern that matches actual chapter prose."""
        _make_authors_db(
            tmp_path,
            "ethan-cole",
            [
                {
                    "discovery_type": "recurring_tics",
                    "text": (
                        '**Hand-as-decider** — grammatisches Subjekt: '
                        '"the hand had been deciding something".'
                    ),
                }
            ],
        )
        patterns = load_author_writing_discoveries("ethan-cole", storyforge_home=tmp_path)
        decider = next((p for p in patterns if "deciding" in p.label.lower()), None)
        assert decider is not None
        assert decider.pattern.search(
            "the hand had been deciding something the rest of Caelan had not yet caught up with"
        ) is not None

    def test_skips_short_body_quotes_db(self, tmp_path):
        """Single-char body quotes are noise; title text becomes the fallback pattern."""
        _make_authors_db(
            tmp_path,
            "ethan-cole",
            [
                {
                    "discovery_type": "recurring_tics",
                    "text": '**Stylistic German Rule Name** — example: "a" is too short.',
                }
            ],
        )
        patterns = load_author_writing_discoveries("ethan-cole", storyforge_home=tmp_path)
        labels = [p.label for p in patterns]
        assert "a" not in labels
        assert "Stylistic German Rule Name" in labels

    def test_multiple_bullets_independent_extraction_db(self, tmp_path):
        """Two DB rows, one title-quoted, one body-quoted — no cross-contamination."""
        _make_authors_db(
            tmp_path,
            "ethan-cole",
            [
                {
                    "discovery_type": "recurring_tics",
                    "text": '**Vague-noun "thing" als Fallback** — concretize.',
                },
                {
                    "discovery_type": "recurring_tics",
                    "text": '**German Rule Name** — example: "concrete English phrase".',
                },
            ],
        )
        patterns = load_author_writing_discoveries("ethan-cole", storyforge_home=tmp_path)
        labels = [p.label for p in patterns]
        assert "thing" in labels
        assert "concrete English phrase" in labels
        assert "German Rule Name" not in labels

    def test_dedup_within_db(self, tmp_path):
        """Two DB rows with the same quoted phrase → deduplicated to one pattern."""
        _make_authors_db(
            tmp_path,
            "ethan-cole",
            [
                {"discovery_type": "recurring_tics", "text": '**"thing" als Fallback** — fix.'},
                {"discovery_type": "recurring_tics", "text": '**"thing" als zweiter Tic** — fix again.'},
            ],
        )
        patterns = load_author_writing_discoveries("ethan-cole", storyforge_home=tmp_path)
        assert [p.label for p in patterns].count("thing") == 1


class TestLoadAuthorDontRulesFromDB:
    """DB-first path: dont-rules stored in author_discoveries table."""

    def test_reads_donts_from_db(self, tmp_path):
        _make_authors_db(
            tmp_path,
            "ethan-cole",
            [{"discovery_type": "donts", "text": "**Never use rooms** — *The room received it.*"}],
        )
        patterns = load_author_dont_rules("ethan-cole", storyforge_home=tmp_path)
        assert len(patterns) > 0
        assert all(p.severity == SEVERITY_BLOCK for p in patterns)

    def test_db_wins_over_profile_md_for_donts(self, tmp_path):
        _make_authors_db(
            tmp_path,
            "ethan-cole",
            [{"discovery_type": "donts", "text": "**Avoid `db-pattern`** — from DB."}],
        )
        author_dir = tmp_path / "authors" / "ethan-cole"
        author_dir.mkdir(parents=True, exist_ok=True)
        (author_dir / "profile.md").write_text(
            "---\nname: x\n---\n\n## Writing Discoveries\n\n"
            "### Don'ts\n\n- **Avoid `md-pattern`** — profile only.\n",
            encoding="utf-8",
        )
        patterns = load_author_dont_rules("ethan-cole", storyforge_home=tmp_path)
        labels = [p.label for p in patterns]
        assert "db-pattern" in labels
        assert "md-pattern" not in labels

    def test_db_absent_returns_empty_for_donts(self, tmp_path):
        """No authors.db → empty list. profile.md is not consulted."""
        author_dir = tmp_path / "authors" / "ethan-cole"
        author_dir.mkdir(parents=True, exist_ok=True)
        (author_dir / "profile.md").write_text(
            "---\nname: x\n---\n\n## Writing Discoveries\n\n"
            "### Don'ts\n\n- **Avoid `profile-pattern`** — must be ignored.\n",
            encoding="utf-8",
        )
        patterns = load_author_dont_rules("ethan-cole", storyforge_home=tmp_path)
        assert patterns == []
