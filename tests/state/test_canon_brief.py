"""Tests for ``tools.state.loaders.canon_brief`` — Issue #161.

Covers:
- section_regex extraction: scoped current_facts, CHANGED facts, pov_relevant_facts
- heuristic fallback for logs without ## Chapter NN headers
- none path: missing file, empty file
- memoir mode: reads people-log.md
- scope window: only review-or-later chapters within N-chapter window
- CHANGED markers always included regardless of scope
- slug_from_sec: chapter slug normalisation
- subject_before: nearest preceding ### header
- Brief integration: canon_brief key present and JSON-serializable
- DB read path: canon_facts table queried first, merged with MD archive (Issue #291)
"""

from __future__ import annotations

import json as _json
from pathlib import Path

from tools.state.loaders.canon_brief import build_canon_brief


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _book(tmp: Path, *, memoir: bool = False) -> Path:
    root = tmp / "my-book"
    (root / "chapters").mkdir(parents=True)
    (root / "plot").mkdir(parents=True)
    if memoir:
        (root / "people").mkdir()
    else:
        (root / "characters").mkdir()
    return root


def _chapter(root: Path, slug: str, *, number: int, status: str = "Review") -> Path:
    ch = root / "chapters" / slug
    ch.mkdir(parents=True, exist_ok=True)
    (ch / "README.md").write_text(
        f"---\nnumber: {number}\nstatus: {status!r}\n---\n\n# Chapter {number}\n",
        encoding="utf-8",
    )
    return ch


def _canon_log(root: Path, content: str, *, memoir: bool = False) -> Path:
    name = "people-log.md" if memoir else "canon-log.md"
    path = root / "plot" / name
    path.write_text(content, encoding="utf-8")
    return path


# ---------------------------------------------------------------------------
# Schema contract
# ---------------------------------------------------------------------------


class TestCanonBriefSchema:
    def test_keys_present_on_valid_log(self, tmp_path):
        root = _book(tmp_path)
        _chapter(root, "01-setup", number=1)
        _canon_log(root, "## Chapter 01 — Setup\n\n- Some fact.\n")
        brief = build_canon_brief(root, "02-conflict")

        assert "current_facts" in brief
        assert "changed_facts" in brief
        assert "pov_relevant_facts" in brief
        assert "scanned_chapters" in brief
        assert "as_of" in brief
        assert "extraction_method" in brief
        assert "warnings" in brief

    def test_json_serializable(self, tmp_path):
        root = _book(tmp_path)
        _chapter(root, "01-setup", number=1)
        _canon_log(root, "## Chapter 01 — Setup\n\n- Fact one.\n")
        brief = build_canon_brief(root, "02-conflict")
        _json.dumps(brief)  # must not raise

    def test_current_facts_item_schema(self, tmp_path, _patch_db):
        root = _book_with_readme(tmp_path, "my-book")
        _insert_db_fact(root, chapter_num=1, subject="Theo", fact="Lives in Berlin.")
        brief = build_canon_brief(root, "02-conflict")

        assert brief["current_facts"]
        fact = brief["current_facts"][0]
        assert "fact" in fact
        assert "chapter" in fact
        assert "source" in fact

    def test_changed_facts_item_schema(self, tmp_path, _patch_db):
        root = _book_with_readme(tmp_path, "my-book")
        _insert_db_fact(
            root,
            chapter_num=1,
            subject="Theo",
            fact="Speaks Spanish",
            is_revision=True,
            old_value="Speaks French",
            revision_impacts=["02-conflict"],
        )
        brief = build_canon_brief(root, "03-climax")

        assert brief["changed_facts"]
        cf = brief["changed_facts"][0]
        assert "old" in cf
        assert "new" in cf
        assert "chapter" in cf
        assert "source" in cf
        assert "revision_impact" in cf


# ---------------------------------------------------------------------------
# None path
# ---------------------------------------------------------------------------


class TestNonePath:
    def test_missing_log_returns_none(self, tmp_path):
        root = _book(tmp_path)
        brief = build_canon_brief(root, "01-setup")

        assert brief["extraction_method"] == "none"
        assert brief["warnings"]
        assert not brief["current_facts"]
        assert not brief["changed_facts"]

    def test_empty_log_returns_none(self, tmp_path):
        root = _book(tmp_path)
        _canon_log(root, "   \n  ")
        brief = build_canon_brief(root, "01-setup")

        assert brief["extraction_method"] == "none"
        assert brief["warnings"]


# ---------------------------------------------------------------------------
# section_regex path
# ---------------------------------------------------------------------------


class TestDbExtractionBehavior:
    """DB-only extraction behavior (Issue #297 — replaces MD-path TestSectionRegexExtraction)."""

    def test_extraction_method_is_db(self, tmp_path, _patch_db):
        root = _book_with_readme(tmp_path, "my-book")
        _insert_db_fact(root, chapter_num=1, subject="Theo", fact="Lives in Berlin.")
        _insert_db_fact(root, chapter_num=2, subject="Theo", fact="Works at the library.")
        brief = build_canon_brief(root, "03-climax", pov_character="Theo")

        assert brief["extraction_method"] == "db"
        assert not any("pov_character" in w for w in brief["warnings"])

    def test_facts_from_scoped_chapters(self, tmp_path, _patch_db):
        root = _book_with_readme(tmp_path, "my-book")
        _insert_db_fact(root, chapter_num=1, subject="Theo", fact="Lives in Berlin.")
        _insert_db_fact(root, chapter_num=2, subject="Theo", fact="Anna is his sister.")
        brief = build_canon_brief(root, "03-climax")

        facts = {f["fact"] for f in brief["current_facts"]}
        assert "Lives in Berlin." in facts
        assert "Anna is his sister." in facts

    def test_source_pointer_includes_subject(self, tmp_path, _patch_db):
        root = _book_with_readme(tmp_path, "my-book")
        _insert_db_fact(root, chapter_num=1, subject="Theo", fact="Speaks German.", domain="skills")
        brief = build_canon_brief(root, "02-conflict")

        fact = brief["current_facts"][0]
        assert "Theo" in fact["source"]
        assert "skills" in fact["source"]

    def test_source_pointer_without_domain(self, tmp_path, _patch_db):
        root = _book_with_readme(tmp_path, "my-book")
        _insert_db_fact(root, chapter_num=1, subject="general", fact="Magic needs consent.")
        brief = build_canon_brief(root, "02-conflict")

        assert brief["current_facts"]
        # Source has no domain suffix when domain is empty
        assert brief["current_facts"][0]["source"].endswith(":general")

    def test_scanned_chapters_populated(self, tmp_path, _patch_db):
        root = _book_with_readme(tmp_path, "my-book")
        _insert_db_fact(root, chapter_num=1, subject="Theo", fact="Fact one.")
        _insert_db_fact(root, chapter_num=2, subject="Theo", fact="Fact two.")
        brief = build_canon_brief(root, "03-climax")

        assert 1 in brief["scanned_chapters"]
        assert 2 in brief["scanned_chapters"]

    def test_as_of_is_highest_scanned_chapter(self, tmp_path, _patch_db):
        root = _book_with_readme(tmp_path, "my-book")
        _insert_db_fact(root, chapter_num=1, subject="Theo", fact="Fact one.")
        _insert_db_fact(root, chapter_num=2, subject="Theo", fact="Fact two.")
        brief = build_canon_brief(root, "03-climax")

        assert brief["as_of"] == "2"


# ---------------------------------------------------------------------------
# Scope window
# ---------------------------------------------------------------------------


class TestScopeWindow:
    def test_scope_limits_chapter_count(self, tmp_path, _patch_db):
        root = _book_with_readme(tmp_path, "my-book")
        for i in range(1, 11):
            _insert_db_fact(root, chapter_num=i, subject="World", fact=f"Fact from ch{i}.")
        brief = build_canon_brief(root, "11-late", scope_chapters=3)

        # scope_min = max(1, 11-3) = 8 → only chapters 8, 9, 10 in current_facts
        assert set(brief["scanned_chapters"]) == {8, 9, 10}

    # Note: test_only_review_or_later_in_scope was MD-specific (chapter-dir status
    # filtering). DB scope uses numerical window only — covered by test_scope_limits.
    # test_changed_outside_scope_still_included is covered by
    # TestCanonBriefDbPath::test_db_revision_outside_scope_still_in_changed_facts.


# ---------------------------------------------------------------------------
# CHANGED entries
# ---------------------------------------------------------------------------


class TestChangedFacts:
    def test_changed_basic(self, tmp_path, _patch_db):
        root = _book_with_readme(tmp_path, "my-book")
        _insert_db_fact(
            root,
            chapter_num=5,
            subject="Theo",
            fact="Speaks Spanish",
            is_revision=True,
            old_value="Speaks French",
            revision_impacts=["06-aftermath", "08-reunion"],
        )
        brief = build_canon_brief(root, "09-end")

        cf = brief["changed_facts"][0]
        assert cf["old"] == "Speaks French"
        assert cf["new"] == "Speaks Spanish"
        assert cf["revision_impact"] == ["06-aftermath", "08-reunion"]
        assert cf["chapter"] == "5"  # DB stores chapter_num as int, serialized as str

    def test_changed_without_revision_impact(self, tmp_path, _patch_db):
        root = _book_with_readme(tmp_path, "my-book")
        _insert_db_fact(
            root,
            chapter_num=2,
            subject="unknown",
            fact="New state",
            is_revision=True,
            old_value="Old state",
        )
        brief = build_canon_brief(root, "03-climax")

        cf = brief["changed_facts"][0]
        assert cf["revision_impact"] == []

    def test_changed_not_in_current_facts(self, tmp_path, _patch_db):
        root = _book_with_readme(tmp_path, "my-book")
        _insert_db_fact(
            root, chapter_num=1, subject="Theo", fact="New state",
            is_revision=True, old_value="Old state",
        )
        _insert_db_fact(root, chapter_num=1, subject="Theo", fact="Normal fact.")
        brief = build_canon_brief(root, "02-conflict")

        facts_text = {f["fact"] for f in brief["current_facts"]}
        assert "Normal fact." in facts_text
        # revision facts appear in changed_facts only
        assert not any("New state" in t for t in facts_text)

    def test_changed_source_includes_chapter_and_subject(self, tmp_path, _patch_db):
        root = _book_with_readme(tmp_path, "my-book")
        _insert_db_fact(
            root,
            chapter_num=3,
            subject="Anna",
            fact="In Munich",
            is_revision=True,
            old_value="In Hamburg",
        )
        brief = build_canon_brief(root, "05-end")

        cf = brief["changed_facts"][0]
        assert "3" in cf["source"]
        assert "CHANGED" in cf["source"]
        assert "Anna" in cf["source"]


# ---------------------------------------------------------------------------
# POV filter
# ---------------------------------------------------------------------------


class TestPovFilter:
    def _log(self) -> str:
        return (
            "## Chapter 01 — Setup\n\n"
            "### Theo: skills\n"
            "- Speaks German fluently.\n\n"
            "### Anna: background\n"
            "- Grew up in Munich.\n"
        )

    def test_pov_relevant_facts_match_by_source(self, tmp_path):
        root = _book(tmp_path)
        _chapter(root, "01-setup", number=1)
        _canon_log(root, self._log())
        brief = build_canon_brief(root, "02-conflict", pov_character="Theo")

        pov_sources = {f["source"] for f in brief["pov_relevant_facts"]}
        assert all("theo" in s.lower() for s in pov_sources)

    def test_pov_filter_case_insensitive(self, tmp_path):
        root = _book(tmp_path)
        _chapter(root, "01-setup", number=1)
        _canon_log(root, self._log())
        brief_lower = build_canon_brief(root, "02-conflict", pov_character="theo")
        brief_upper = build_canon_brief(root, "02-conflict", pov_character="THEO")

        assert len(brief_lower["pov_relevant_facts"]) == len(brief_upper["pov_relevant_facts"])

    def test_pov_empty_returns_empty_list(self, tmp_path):
        root = _book(tmp_path)
        _chapter(root, "01-setup", number=1)
        _canon_log(root, self._log())
        brief = build_canon_brief(root, "02-conflict", pov_character="")

        assert brief["pov_relevant_facts"] == []

    def test_pov_match_by_fact_text(self, tmp_path, _patch_db):
        root = _book_with_readme(tmp_path, "my-book")
        _insert_db_fact(root, chapter_num=1, subject="general", fact="Theo is the protagonist.")
        _insert_db_fact(root, chapter_num=1, subject="weather", fact="Rain is falling.")
        brief = build_canon_brief(root, "02-conflict", pov_character="Theo")

        pov_facts = {f["fact"] for f in brief["pov_relevant_facts"]}
        assert "Theo is the protagonist." in pov_facts
        assert "Rain is falling." not in pov_facts

    def test_multi_token_pov_matches_first_name_in_subject_header(self, tmp_path, _patch_db):
        # Issue #168: "Theo Wilkons" must match facts whose source contains "Theo"
        root = _book_with_readme(tmp_path, "my-book")
        _insert_db_fact(root, chapter_num=1, subject="Theo", fact="Theo questions everything.", domain="cognition")
        _insert_db_fact(root, chapter_num=1, subject="Kael", fact="Kael avoids eye contact.", domain="behavior")
        brief = build_canon_brief(root, "02-conflict", pov_character="Theo Wilkons")

        assert len(brief["pov_relevant_facts"]) > 0, (
            "pov_relevant_facts must not be empty for multi-token POV name"
        )
        pov_sources = {f["source"] for f in brief["pov_relevant_facts"]}
        assert all("theo" in s.lower() for s in pov_sources)

    def test_multi_token_pov_no_false_positives_on_partial_match(self, tmp_path, _patch_db):
        # Word-boundary: "theo" must NOT match "Theology"
        root = _book_with_readme(tmp_path, "my-book")
        _insert_db_fact(root, chapter_num=1, subject="scholar", fact="Theology fascinates the scholar.")
        _insert_db_fact(root, chapter_num=1, subject="Theo", fact="Theo arrived late.")
        brief = build_canon_brief(root, "02-conflict", pov_character="Theo Wilkons")

        pov_facts = {f["fact"] for f in brief["pov_relevant_facts"]}
        assert "Theology fascinates the scholar." not in pov_facts
        assert "Theo arrived late." in pov_facts

    def test_single_token_pov_backward_compatible(self, tmp_path, _patch_db):
        root = _book_with_readme(tmp_path, "my-book")
        _insert_db_fact(root, chapter_num=1, subject="Kael", fact="Kael avoids eye contact.")
        _insert_db_fact(root, chapter_num=1, subject="Theo", fact="Theo ponders the question.")
        brief = build_canon_brief(root, "02-conflict", pov_character="Kael")

        assert len(brief["pov_relevant_facts"]) > 0
        pov_sources = {f["source"] for f in brief["pov_relevant_facts"]}
        assert all("kael" in s.lower() for s in pov_sources)

    def test_short_single_name_fallback(self, tmp_path, _patch_db):
        # Names shorter than 3 chars ("Bo") fall back to substring match, not empty list
        root = _book_with_readme(tmp_path, "my-book")
        _insert_db_fact(root, chapter_num=1, subject="general", fact="Bo crossed the bridge.")
        _insert_db_fact(root, chapter_num=1, subject="weather", fact="Rain kept falling.")
        brief = build_canon_brief(root, "02-conflict", pov_character="Bo")

        pov_facts = {f["fact"] for f in brief["pov_relevant_facts"]}
        assert "Bo crossed the bridge." in pov_facts
        assert "Rain kept falling." not in pov_facts

    def test_multi_token_pov_or_semantics_surname_match(self, tmp_path, _patch_db):
        # OR-semantics: a fact mentioning only the surname still qualifies.
        root = _book_with_readme(tmp_path, "my-book")
        _insert_db_fact(root, chapter_num=1, subject="general", fact="Wilkons noticed the discrepancy.")
        _insert_db_fact(root, chapter_num=1, subject="weather", fact="Rain kept falling.")
        brief = build_canon_brief(root, "02-conflict", pov_character="Theo Wilkons")

        pov_facts = {f["fact"] for f in brief["pov_relevant_facts"]}
        assert "Wilkons noticed the discrepancy." in pov_facts
        assert "Rain kept falling." not in pov_facts


# ---------------------------------------------------------------------------
# Slug normalisation
# ---------------------------------------------------------------------------


class TestSlugNormalisation:
    def test_chapter_numeric_string_in_facts(self, tmp_path, _patch_db):
        """Post-#297: chapter field is a numeric string, not a slug."""
        root = _book_with_readme(tmp_path, "my-book")
        _chapter(root, "01-setup", number=1)
        _insert_db_fact(root, chapter_num=1, subject="Theo", fact="A fact.")
        brief = build_canon_brief(root, "02-conflict")

        assert brief["current_facts"]
        assert brief["current_facts"][0]["chapter"] == "1"

    def test_chapter_three_numeric_string(self, tmp_path, _patch_db):
        """Chapter 3 fact → chapter field is "3", not "03" slug."""
        root = _book_with_readme(tmp_path, "my-book")
        _chapter(root, "03-x", number=3)
        _insert_db_fact(root, chapter_num=3, subject="Setting", fact="A bare fact.")
        brief = build_canon_brief(root, "04-next")

        assert brief["current_facts"]
        assert brief["current_facts"][0]["chapter"] == "3"

    def test_as_of_string_type(self, tmp_path, _patch_db):
        root = _book_with_readme(tmp_path, "my-book")
        _chapter(root, "01-setup", number=1)
        _insert_db_fact(root, chapter_num=1, subject="Theo", fact="Fact.")
        brief = build_canon_brief(root, "02-conflict")

        assert brief["as_of"] is None or isinstance(brief["as_of"], str)

    def test_heuristic_chapter_num_zero_always_in_scope(self, tmp_path, _patch_db):
        """chapter_num=0 (heuristic migration) must appear in current_facts for any chapter."""
        root = _book_with_readme(tmp_path, "my-book")
        _insert_db_fact(root, chapter_num=0, subject="general", fact="Legacy fact.")

        for chapter_slug in ("01-open", "05-middle", "30-climax"):
            brief = build_canon_brief(root, chapter_slug)
            facts = {f["fact"] for f in brief["current_facts"]}
            assert "Legacy fact." in facts, (
                f"chapter_num=0 fact must be in scope for {chapter_slug}"
            )


# ---------------------------------------------------------------------------
# Heuristic fallback
# ---------------------------------------------------------------------------


# TestHeuristicFallback removed (Issue #297): heuristic extraction lives in
# canon_log_extractor.py and is tested via tests/scripts/test_migrate_canon_log.py.
# build_canon_brief() uses the DB path exclusively.


# ---------------------------------------------------------------------------
# Memoir mode
# ---------------------------------------------------------------------------


class TestMemoirMode:
    def test_memoir_uses_same_db_as_fiction(self, tmp_path, _patch_db):
        """Post-#297: memoir and fiction both read from canon_facts DB."""
        root = _book_with_readme(tmp_path, "my-book")
        _insert_db_fact(root, chapter_num=1, subject="Mum", fact="Mother of narrator.")
        brief = build_canon_brief(root, "02-next", book_category="memoir")

        assert brief["extraction_method"] == "db"
        assert any("Mother of narrator." in f["fact"] for f in brief["current_facts"])

    def test_empty_db_returns_none_for_memoir(self, tmp_path, _patch_db):
        """Empty DB returns none regardless of book_category."""
        root = _book_with_readme(tmp_path, "my-book")
        brief = build_canon_brief(root, "01-opening", book_category="memoir")

        assert brief["extraction_method"] == "none"
        assert brief["warnings"]

    def test_book_category_param_does_not_affect_db_query(self, tmp_path, _patch_db):
        """book_category is retained for API compat but irrelevant post-#297."""
        root = _book_with_readme(tmp_path, "my-book")
        _insert_db_fact(root, chapter_num=1, subject="Theo", fact="A fact.")
        brief_fiction = build_canon_brief(root, "02-next", book_category="fiction")
        brief_memoir = build_canon_brief(root, "02-next", book_category="memoir")

        assert brief_fiction["current_facts"] == brief_memoir["current_facts"]


# ---------------------------------------------------------------------------
# Brief integration: canon_brief key in chapter_writing_brief
# ---------------------------------------------------------------------------


def _scaffold_book(
    tmp_path: Path,
    *,
    chapter_slug: str = "01-setup",
    chapter_status: str = "Draft",
    pov_character: str = "",
) -> Path:
    """Minimal book scaffold with a single target chapter for brief integration tests."""
    book = tmp_path / "test-book"
    (book / "chapters" / chapter_slug).mkdir(parents=True)
    (book / "characters").mkdir()
    (book / "plot").mkdir()
    (book / "world").mkdir()
    (book / "README.md").write_text(
        '---\ntitle: "Test"\nauthor: ""\n---\n', encoding="utf-8"
    )
    ch = book / "chapters" / chapter_slug
    pov_line = f'pov_character: "{pov_character}"\n' if pov_character else ""
    (ch / "README.md").write_text(
        f'---\nnumber: 1\nstatus: "{chapter_status}"\n{pov_line}---\n',
        encoding="utf-8",
    )
    (ch / "draft.md").write_text("# Chapter 1\n\nSome prose.\n", encoding="utf-8")
    return book


class TestBriefIntegration:
    def test_canon_brief_key_present(self, tmp_path):
        from tools.state.chapter_writing_brief import build_chapter_writing_brief
        from pathlib import Path as _Path

        plugin_root = _Path(__file__).resolve().parent.parent.parent
        book = _scaffold_book(tmp_path)

        brief = build_chapter_writing_brief(
            book_root=book,
            book_slug="test-book",
            chapter_slug="01-setup",
            plugin_root=plugin_root,
        )

        assert "canon_brief" in brief
        cb = brief["canon_brief"]
        # Issue #165: current_facts is NOT inlined; the skill calls
        # get_canon_brief() separately when it needs the full fact list.
        assert "current_facts" not in cb
        for key in (
            "changed_facts",
            "pov_relevant_facts",
            "scanned_chapters",
            "as_of",
            "extraction_method",
            "warnings",
        ):
            assert key in cb, f"missing key in inline canon_brief: {key}"
        _json.dumps(brief)  # full brief must be JSON-serializable

    def test_inline_canon_brief_size_under_budget(self, tmp_path):
        """Issue #165: brief stays well under the tool-result token limit
        even on long-running books with a dense canon log."""
        from tools.state.chapter_writing_brief import build_chapter_writing_brief
        from pathlib import Path as _Path

        plugin_root = _Path(__file__).resolve().parent.parent.parent

        book = tmp_path / "long-book"
        (book / "characters").mkdir(parents=True)
        (book / "plot").mkdir()
        (book / "world").mkdir()
        (book / "README.md").write_text(
            '---\ntitle: "Long Book"\nauthor: ""\n---\n', encoding="utf-8"
        )

        # 10 review-status chapters before the target — fully in scope_chapters=8 default
        for i in range(1, 11):
            ch = book / "chapters" / f"{i:02d}-ch{i}"
            ch.mkdir(parents=True)
            (ch / "README.md").write_text(
                f'---\nnumber: {i}\nstatus: "Review"\n---\n', encoding="utf-8"
            )
            (ch / "draft.md").write_text(
                f"# Chapter {i}\n\nSome prose.\n", encoding="utf-8"
            )

        target = book / "chapters" / "11-target"
        target.mkdir(parents=True)
        (target / "README.md").write_text(
            '---\nnumber: 11\nstatus: "Draft"\n---\n', encoding="utf-8"
        )

        # Realistic narrative-bullet density: ~50 facts per chapter at ~220 chars each.
        sections = []
        for i in range(1, 11):
            bullets = "\n".join(
                f"- This is a fairly long fact about chapter {i}, item {j}, "
                f"with enough text to make the canon log realistically dense — "
                f"around two hundred characters of narrative bullet content "
                f"that mirrors how authors actually write canon logs."
                for j in range(1, 51)
            )
            sections.append(
                f"## Chapter {i:02d} — Ch{i}\n\n### Theo: facts\n{bullets}\n"
            )
        (book / "plot" / "canon-log.md").write_text(
            "\n\n".join(sections), encoding="utf-8"
        )

        brief = build_chapter_writing_brief(
            book_root=book,
            book_slug="long-book",
            chapter_slug="11-target",
            plugin_root=plugin_root,
        )

        serialized = _json.dumps(brief)
        # Pre-fix on a comparable book: ~169k chars. Post-fix: well under 60k.
        assert len(serialized) < 60_000, (
            f"brief is {len(serialized)} chars — exceeds size budget. "
            f"canon_brief.current_facts is likely re-inlined; should be omitted (#165)."
        )

    def test_pov_character_missing_yields_warning(self, tmp_path, _patch_db):
        """Issue #165 side observation: chapter without pov_character should warn
        so the skill knows why pov_relevant_facts is empty."""
        from tools.state.chapter_writing_brief import build_chapter_writing_brief
        from pathlib import Path as _Path

        plugin_root = _Path(__file__).resolve().parent.parent.parent
        # Use "02-conflict" (current_num=2, up_to_chapter=1, scope_min=1) so
        # a fact at chapter_num=1 passes the scope filter and has_db is True.
        book = _scaffold_book(tmp_path, chapter_slug="02-conflict")
        _insert_db_fact(book, chapter_num=1, subject="general", fact="Some fact.")

        brief = build_chapter_writing_brief(
            book_root=book,
            book_slug="test-book",
            chapter_slug="02-conflict",
            plugin_root=plugin_root,
        )

        warnings = brief["canon_brief"].get("warnings", [])
        assert any("pov_character" in w.lower() for w in warnings), (
            f"expected pov_character warning, got: {warnings}"
        )


# ---------------------------------------------------------------------------
# Issue #170: pov_relevant_facts char-budget trim (symmetric to #167)
# ---------------------------------------------------------------------------


def _scaffold_long_book_with_pov(
    tmp_path: Path,
    *,
    bullets_per_chapter: int = 50,
    bullet_text_template: str | None = None,
    pov_character: str = "Theo",
) -> Path:
    """Build a 10-chapter book with Theo-tagged DB facts (Issue #297: DB-only)."""
    book = tmp_path / "long-book"
    (book / "characters").mkdir(parents=True)
    (book / "plot").mkdir()
    (book / "world").mkdir()
    (book / "README.md").write_text(
        '---\ntitle: "Long Book"\nauthor: ""\n---\n', encoding="utf-8"
    )

    for i in range(1, 11):
        ch = book / "chapters" / f"{i:02d}-ch{i}"
        ch.mkdir(parents=True)
        (ch / "README.md").write_text(
            f'---\nnumber: {i}\nstatus: "Review"\n---\n', encoding="utf-8"
        )
        (ch / "draft.md").write_text(
            f"# Chapter {i}\n\nSome prose.\n", encoding="utf-8"
        )

    target = book / "chapters" / "11-target"
    target.mkdir(parents=True)
    pov_line = f'pov_character: "{pov_character}"\n' if pov_character else ""
    (target / "README.md").write_text(
        f'---\nnumber: 11\nstatus: "Draft"\n{pov_line}---\n',
        encoding="utf-8",
    )

    template = bullet_text_template or (
        "This is a fairly long fact about chapter {chapter}, item {item}, "
        "with enough text to make the canon log realistically dense — "
        "around two hundred characters of narrative bullet content "
        "that mirrors how authors actually write canon logs."
    )

    for i in range(1, 11):
        for j in range(1, bullets_per_chapter + 1):
            fact_text = template.format(chapter=i, item=j)
            _insert_db_fact(book, chapter_num=i, subject="Theo", fact=fact_text, domain="facts")

    return book


class TestPovFactsCharBudget:
    """Issue #170: pov_relevant_facts must respect a char-budget so it doesn't
    push the chapter-writing brief past the tool-result token limit on books
    with narrative-style canon logs."""

    def test_pov_facts_char_budget_trims_on_long_canon_log(self, tmp_path, _patch_db):
        from tools.state.chapter_writing_brief import (
            POV_FACTS_CHAR_BUDGET,
            build_chapter_writing_brief,
        )
        from pathlib import Path as _Path

        plugin_root = _Path(__file__).resolve().parent.parent.parent
        # 10 chapters × 50 dense bullets = 500 facts, ~110k chars of POV-matching content
        book = _scaffold_long_book_with_pov(tmp_path, bullets_per_chapter=50)

        brief = build_chapter_writing_brief(
            book_root=book,
            book_slug="long-book",
            chapter_slug="11-target",
            plugin_root=plugin_root,
        )

        cb = brief["canon_brief"]
        pov_facts = cb["pov_relevant_facts"]
        assert pov_facts, "pov_relevant_facts must not be empty after trim"

        serialized_pov = _json.dumps(pov_facts, ensure_ascii=False)
        assert len(serialized_pov) <= POV_FACTS_CHAR_BUDGET, (
            f"pov_relevant_facts is {len(serialized_pov)} chars — "
            f"exceeds char-budget {POV_FACTS_CHAR_BUDGET}"
        )

        assert cb.get("pov_relevant_facts_truncated") is True, (
            "pov_relevant_facts_truncated must be True when trim fires"
        )
        total = cb.get("pov_relevant_facts_total_count")
        assert isinstance(total, int)
        assert total > len(pov_facts), (
            f"pov_relevant_facts_total_count ({total}) must exceed kept count "
            f"({len(pov_facts)}) when truncated"
        )

    def test_pov_facts_kept_are_from_newest_chapters(self, tmp_path, _patch_db):
        """Newest-first preservation: when trimming, keep facts from the
        highest-numbered chapters because those are the highest-risk
        continuity zone for the current chapter."""
        from tools.state.chapter_writing_brief import build_chapter_writing_brief
        from pathlib import Path as _Path

        plugin_root = _Path(__file__).resolve().parent.parent.parent
        book = _scaffold_long_book_with_pov(tmp_path, bullets_per_chapter=50)

        brief = build_chapter_writing_brief(
            book_root=book,
            book_slug="long-book",
            chapter_slug="11-target",
            plugin_root=plugin_root,
        )

        pov_facts = brief["canon_brief"]["pov_relevant_facts"]
        assert pov_facts
        # Extract chapter numbers (chapter slugs look like "10-ch10")
        kept_chapter_nums = sorted(
            {int(f["chapter"].split("-")[0]) for f in pov_facts}
        )
        # Trim must preserve the most recent chapters; chapter 10 is the
        # newest in scope and MUST be kept.
        assert 10 in kept_chapter_nums, (
            f"newest chapter (10) was dropped; kept chapters: {kept_chapter_nums}"
        )
        # And it must not have skipped chapter 10 in favor of older chapters:
        # if any older chapter is kept, every chapter newer than it must also be kept.
        if kept_chapter_nums:
            oldest_kept = min(kept_chapter_nums)
            expected_window = set(range(oldest_kept, 11))
            assert set(kept_chapter_nums) == expected_window, (
                f"kept chapters {kept_chapter_nums} are not a contiguous "
                f"newest-first window; expected {sorted(expected_window)}"
            )

    def test_pov_facts_no_trim_on_short_canon_log(self, tmp_path, _patch_db):
        """Short canon log: nothing to trim — all matching facts kept,
        truncated flag is False, total_count equals kept count."""
        from tools.state.chapter_writing_brief import build_chapter_writing_brief
        from pathlib import Path as _Path

        plugin_root = _Path(__file__).resolve().parent.parent.parent
        # 10 chapters × 5 short bullets = 50 facts, well under 30k chars
        book = _scaffold_long_book_with_pov(
            tmp_path,
            bullets_per_chapter=5,
            bullet_text_template="Short fact ch{chapter} item {item}.",
        )

        brief = build_chapter_writing_brief(
            book_root=book,
            book_slug="long-book",
            chapter_slug="11-target",
            plugin_root=plugin_root,
        )

        cb = brief["canon_brief"]
        pov_facts = cb["pov_relevant_facts"]
        assert pov_facts
        # 8 in scope × 5 = 40 facts (default scope_chapters=8)
        assert len(pov_facts) == 40, (
            f"expected 40 pov facts on short log, got {len(pov_facts)}"
        )
        assert cb.get("pov_relevant_facts_truncated") is False
        assert cb.get("pov_relevant_facts_total_count") == 40

    def test_inline_canon_brief_size_under_budget_with_pov(self, tmp_path, _patch_db):
        """Issue #170: with a POV character set on a long-running DB-backed book,
        the full brief must still fit comfortably under the tool-result token limit."""
        from tools.state.chapter_writing_brief import build_chapter_writing_brief
        from pathlib import Path as _Path

        plugin_root = _Path(__file__).resolve().parent.parent.parent
        book = _scaffold_long_book_with_pov(tmp_path, bullets_per_chapter=50)

        brief = build_chapter_writing_brief(
            book_root=book,
            book_slug="long-book",
            chapter_slug="11-target",
            plugin_root=plugin_root,
        )

        serialized = _json.dumps(brief, ensure_ascii=False)
        # Pre-#170 with POV set: ~105k chars (per Issue #170 reproduction).
        # Post-#170 with 30k pov-budget: ~55-60k on dense books — still
        # crossed the real MCP output cap (~50k) on act-3 chapters.
        # Follow-up tightened pov-budget to 15k; brief now stays well
        # under 45k even with the densest synthetic canon log.
        assert len(serialized) < 45_000, (
            f"brief is {len(serialized)} chars — exceeds size budget. "
            f"pov_relevant_facts trim is likely missing or too generous (#170)."
        )


# ---------------------------------------------------------------------------
# Issue #291: DB read path — build_canon_brief() must query canon_facts table
# ---------------------------------------------------------------------------
#
# These tests are RED until the DB read path is added to build_canon_brief().
# The fix: query canon_facts first, map DB rows to the brief schema, then
# merge with any legacy MD content from the read-only archive.
# ---------------------------------------------------------------------------

import pytest
import tools.db.connection as _db_conn


def _book_with_readme(
    root: Path,
    slug: str,
    *,
    series: str = "",
    series_number: int = 1,
) -> Path:
    book = root / slug
    (book / "chapters").mkdir(parents=True)
    (book / "plot").mkdir()
    (book / "characters").mkdir()
    readme = (
        f"---\ntitle: {slug}\nslug: {slug}\n"
        f"series: \"{series}\"\nseries_number: {series_number}\n---\n"
    )
    (book / "README.md").write_text(readme, encoding="utf-8")
    return book


def _insert_db_fact(
    book_root: Path,
    *,
    chapter_num: int,
    subject: str,
    fact: str,
    book_num: int = 1,
    domain: str = "",
    is_revision: bool = False,
    old_value: str = "",
    revision_impacts: list | None = None,
) -> None:
    import json
    from tools.db.canon_facts import insert_fact
    from tools.db.connection import get_db_slug_for_book, open_canon_db
    db_slug = get_db_slug_for_book(book_root)
    conn = open_canon_db(db_slug)
    try:
        insert_fact(
            conn,
            book_num=book_num,
            chapter_num=chapter_num,
            subject=subject,
            fact=fact,
            domain=domain,
            is_revision=is_revision,
            old_value=old_value or None,
            revision_impacts=json.dumps(revision_impacts) if revision_impacts else None,
        )
    finally:
        conn.close()


@pytest.fixture()
def _patch_db(tmp_path, monkeypatch):
    """Redirect all DB operations to a fresh tmp_path/db/ directory."""
    db_dir = tmp_path / "db"
    db_dir.mkdir()
    monkeypatch.setattr(_db_conn, "DB_DIR", db_dir)


class TestCanonBriefDbPath:
    """DB read path for build_canon_brief() — Issue #291.

    RED until the DB query + merge is implemented in canon_brief.py.
    """

    def test_db_fact_appears_in_current_facts(self, tmp_path, _patch_db):
        root = _book_with_readme(tmp_path, "my-book")
        _insert_db_fact(root, chapter_num=1, subject="Theo", fact="Theo is 26 years old")

        brief = build_canon_brief(root, "02-conflict")

        facts = {f["fact"] for f in brief["current_facts"]}
        assert "Theo is 26 years old" in facts

    def test_db_revision_fact_appears_in_changed_facts(self, tmp_path, _patch_db):
        root = _book_with_readme(tmp_path, "my-book")
        _insert_db_fact(
            root,
            chapter_num=5,
            subject="Kael",
            fact="Kael eats food",
            is_revision=True,
            old_value="Kael does not eat",
            revision_impacts=["06-garlic-bread", "07-the-world"],
        )

        brief = build_canon_brief(root, "08-resolution")

        assert brief["changed_facts"], "DB revision fact must appear in changed_facts"
        cf = brief["changed_facts"][0]
        assert cf["old"] == "Kael does not eat"
        assert cf["new"] == "Kael eats food"
        assert cf["revision_impact"] == ["06-garlic-bread", "07-the-world"]
        assert "chapter" in cf
        assert "source" in cf

    def test_db_fact_chapter_number_in_source(self, tmp_path, _patch_db):
        root = _book_with_readme(tmp_path, "my-book")
        _insert_db_fact(root, chapter_num=3, subject="Anna", fact="Anna is Theo's sister")

        brief = build_canon_brief(root, "05-end")

        db_facts = [f for f in brief["current_facts"] if "db" in f.get("source", "")]
        assert db_facts, "DB-sourced facts must have 'db' in their source pointer"
        assert "Anna" in db_facts[0]["source"]

    def test_current_chapter_db_facts_excluded(self, tmp_path, _patch_db):
        """A fact inserted for chapter N must not appear when writing chapter N."""
        root = _book_with_readme(tmp_path, "my-book")
        _insert_db_fact(
            root, chapter_num=5, subject="Theo", fact="Fact from chapter five"
        )

        brief = build_canon_brief(root, "05-climax")

        facts = {f["fact"] for f in brief["current_facts"]}
        assert "Fact from chapter five" not in facts

    def test_db_fact_outside_scope_excluded_from_current_facts(self, tmp_path, _patch_db):
        """scope_chapters lower bound applies to DB facts, same as MD facts."""
        root = _book_with_readme(tmp_path, "my-book")
        _insert_db_fact(root, chapter_num=1, subject="World", fact="Early world fact")
        _insert_db_fact(root, chapter_num=9, subject="World", fact="Recent world fact")

        # scope=2 for chapter 11 → only chapters 9 and 10 in window
        brief = build_canon_brief(root, "11-end", scope_chapters=2)

        facts = {f["fact"] for f in brief["current_facts"]}
        assert "Recent world fact" in facts
        assert "Early world fact" not in facts

    def test_db_revision_outside_scope_still_in_changed_facts(self, tmp_path, _patch_db):
        """CHANGED facts always surface regardless of scope window — same rule as MD."""
        root = _book_with_readme(tmp_path, "my-book")
        _insert_db_fact(
            root,
            chapter_num=1,
            subject="Kael",
            fact="New canon",
            is_revision=True,
            old_value="Old canon",
        )

        # scope=1 for chapter 10 → chapter 1 outside scope, but CHANGED still appears
        brief = build_canon_brief(root, "10-end", scope_chapters=1)

        assert brief["changed_facts"], "DB revision must appear in changed_facts even outside scope"
        assert brief["changed_facts"][0]["old"] == "Old canon"

    def test_md_log_no_longer_read(self, tmp_path, _patch_db):
        """Post-#297: canon-log.md is no longer read by build_canon_brief().
        Only DB facts appear — MD archive is migration-only."""
        root = _book_with_readme(tmp_path, "my-book")
        _chapter(root, "01-setup", number=1)
        (root / "plot" / "canon-log.md").write_text(
            "## Chapter 01 — Setup\n\n- MD archive fact.\n",
            encoding="utf-8",
        )
        _chapter(root, "02-action", number=2)
        _insert_db_fact(root, chapter_num=2, subject="Theo", fact="DB new fact")

        brief = build_canon_brief(root, "03-climax")

        facts = {f["fact"] for f in brief["current_facts"]}
        assert "MD archive fact." not in facts, "canon-log.md must not be read post-#297"
        assert "DB new fact" in facts

    def test_empty_db_returns_none_even_if_log_exists(self, tmp_path, _patch_db):
        """Post-#297: empty DB returns none even when canon-log.md is present.
        Run scripts/migrate_canon_log_to_db.py to import legacy facts."""
        root = _book_with_readme(tmp_path, "my-book")
        _chapter(root, "01-setup", number=1)
        (root / "plot" / "canon-log.md").write_text(
            "## Chapter 01 — Setup\n\n- MD only fact.\n",
            encoding="utf-8",
        )
        # No DB inserts — migration not yet run

        brief = build_canon_brief(root, "02-conflict")

        assert brief["extraction_method"] == "none"
        assert brief["current_facts"] == []

    def test_db_only_extraction_method_not_none(self, tmp_path, _patch_db):
        """When DB has facts and MD log is absent, extraction_method must not be 'none'."""
        root = _book_with_readme(tmp_path, "my-book")
        _insert_db_fact(root, chapter_num=1, subject="Theo", fact="Theo exists")

        brief = build_canon_brief(root, "02-conflict")

        assert brief["extraction_method"] != "none"

    def test_db_pov_filter_applies_to_db_facts(self, tmp_path, _patch_db):
        """POV filter must filter DB-sourced facts just like MD facts."""
        root = _book_with_readme(tmp_path, "my-book")
        _insert_db_fact(root, chapter_num=1, subject="Theo", fact="Theo likes coffee")
        _insert_db_fact(root, chapter_num=1, subject="Anna", fact="Anna hates coffee")

        brief = build_canon_brief(root, "02-conflict", pov_character="Theo")

        pov_facts = {f["fact"] for f in brief["pov_relevant_facts"]}
        assert "Theo likes coffee" in pov_facts
        assert "Anna hates coffee" not in pov_facts

    def test_db_changed_revision_impact_parsed_from_json(self, tmp_path, _patch_db):
        """revision_impacts stored as JSON string in DB must be deserialized to list."""
        root = _book_with_readme(tmp_path, "my-book")
        _insert_db_fact(
            root,
            chapter_num=3,
            subject="Setting",
            fact="Mine is closed",
            is_revision=True,
            old_value="Mine is open",
            revision_impacts=["04-descent", "05-the-dark", "08-aftermath"],
        )

        brief = build_canon_brief(root, "10-end")

        assert brief["changed_facts"]
        cf = brief["changed_facts"][0]
        assert isinstance(cf["revision_impact"], list)
        assert cf["revision_impact"] == ["04-descent", "05-the-dark", "08-aftermath"]

    def test_db_revision_without_impacts_yields_empty_list(self, tmp_path, _patch_db):
        root = _book_with_readme(tmp_path, "my-book")
        _insert_db_fact(
            root,
            chapter_num=2,
            subject="Theo",
            fact="Changed fact",
            is_revision=True,
            old_value="Old fact",
        )

        brief = build_canon_brief(root, "05-end")

        cf = brief["changed_facts"][0]
        assert isinstance(cf["revision_impact"], list)
        assert cf["revision_impact"] == []

    def test_db_result_is_json_serializable(self, tmp_path, _patch_db):
        import json as _json
        root = _book_with_readme(tmp_path, "my-book")
        _insert_db_fact(root, chapter_num=1, subject="Theo", fact="Some fact")
        _insert_db_fact(
            root, chapter_num=2, subject="Anna", fact="New state",
            is_revision=True, old_value="Old state",
            revision_impacts=["03-aftermath"],
        )

        brief = build_canon_brief(root, "05-end")
        _json.dumps(brief)  # must not raise
