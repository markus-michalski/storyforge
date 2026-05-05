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

    def test_current_facts_item_schema(self, tmp_path):
        root = _book(tmp_path)
        _chapter(root, "01-setup", number=1)
        _canon_log(root, "## Chapter 01 — Setup\n\n### Theo: locations\n- Lives in Berlin.\n")
        brief = build_canon_brief(root, "02-conflict")

        assert brief["current_facts"]
        fact = brief["current_facts"][0]
        assert "fact" in fact
        assert "chapter" in fact
        assert "source" in fact

    def test_changed_facts_item_schema(self, tmp_path):
        root = _book(tmp_path)
        _chapter(root, "01-setup", number=1)
        _canon_log(
            root,
            "## Chapter 01 — Setup\n\n"
            "### Theo: skills\n"
            "- **CHANGED**: Speaks French → Speaks Spanish (revision_impact: 02-conflict)\n",
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


class TestSectionRegexExtraction:
    def _log(self) -> str:
        return (
            "# Test Book — Canon Log\n\n"
            "## Chapter 01 — Setup\n\n"
            "### Theo: locations\n"
            "- Lives in Berlin, Prenzlauer Berg.\n"
            "- Works at the university library.\n\n"
            "### Setting: world rules\n"
            "- Magic requires physical contact.\n\n"
            "## Chapter 02 — Conflict\n\n"
            "### Theo: relationships\n"
            "- Anna is his sister, NOT his girlfriend.\n\n"
        )

    def test_extraction_method_is_section_regex(self, tmp_path):
        root = _book(tmp_path)
        _chapter(root, "01-setup", number=1)
        _chapter(root, "02-conflict", number=2)
        _canon_log(root, self._log())
        brief = build_canon_brief(root, "03-climax", pov_character="Theo")

        assert brief["extraction_method"] == "section_regex"
        assert not brief["warnings"]

    def test_facts_from_scoped_chapters(self, tmp_path):
        root = _book(tmp_path)
        _chapter(root, "01-setup", number=1)
        _chapter(root, "02-conflict", number=2)
        _canon_log(root, self._log())
        brief = build_canon_brief(root, "03-climax")

        facts = {f["fact"] for f in brief["current_facts"]}
        assert "Lives in Berlin, Prenzlauer Berg." in facts
        assert "Anna is his sister, NOT his girlfriend." in facts

    def test_current_chapter_excluded(self, tmp_path):
        root = _book(tmp_path)
        _chapter(root, "03-climax", number=3)
        log = (
            "## Chapter 03 — Climax\n\n"
            "### Theo: actions\n- Does something climactic.\n"
        )
        _canon_log(root, log)
        brief = build_canon_brief(root, "03-climax")

        assert not brief["current_facts"]

    def test_future_chapter_excluded(self, tmp_path):
        root = _book(tmp_path)
        _chapter(root, "01-setup", number=1)
        log = (
            "## Chapter 01 — Setup\n\n- Early fact.\n\n"
            "## Chapter 05 — Future\n\n- Future fact.\n"
        )
        _canon_log(root, log)
        brief = build_canon_brief(root, "03-climax")

        facts = {f["fact"] for f in brief["current_facts"]}
        assert "Future fact." not in facts

    def test_source_pointer_includes_subject_topic(self, tmp_path):
        root = _book(tmp_path)
        _chapter(root, "01-setup", number=1)
        _canon_log(
            root,
            "## Chapter 01 — Setup\n\n### Theo: skills\n- Speaks German fluently.\n",
        )
        brief = build_canon_brief(root, "02-conflict")

        fact = brief["current_facts"][0]
        assert "Theo" in fact["source"]
        assert "skills" in fact["source"]

    def test_source_pointer_generic_without_subsections(self, tmp_path):
        root = _book(tmp_path)
        _chapter(root, "01-setup", number=1)
        _canon_log(
            root,
            "## Chapter 01 — Setup\n\n- A bare bullet without subsection.\n",
        )
        brief = build_canon_brief(root, "02-conflict")

        assert brief["current_facts"]
        assert brief["current_facts"][0]["source"].endswith(":canon-log")

    def test_scanned_chapters_populated(self, tmp_path):
        root = _book(tmp_path)
        _chapter(root, "01-setup", number=1)
        _chapter(root, "02-conflict", number=2)
        log = (
            "## Chapter 01 — Setup\n\n- Fact one.\n\n"
            "## Chapter 02 — Conflict\n\n- Fact two.\n"
        )
        _canon_log(root, log)
        brief = build_canon_brief(root, "03-climax")

        assert 1 in brief["scanned_chapters"]
        assert 2 in brief["scanned_chapters"]

    def test_as_of_is_highest_scanned_chapter(self, tmp_path):
        root = _book(tmp_path)
        _chapter(root, "01-setup", number=1)
        _chapter(root, "02-conflict", number=2)
        log = (
            "## Chapter 01 — Setup\n\n- Fact one.\n\n"
            "## Chapter 02 — Conflict\n\n- Fact two.\n"
        )
        _canon_log(root, log)
        brief = build_canon_brief(root, "03-climax")

        assert brief["as_of"] == "2"


# ---------------------------------------------------------------------------
# Scope window
# ---------------------------------------------------------------------------


class TestScopeWindow:
    def test_only_review_or_later_in_scope(self, tmp_path):
        root = _book(tmp_path)
        _chapter(root, "01-setup", number=1, status="Outline")  # too early
        _chapter(root, "02-conflict", number=2, status="Review")
        log = (
            "## Chapter 01 — Setup\n\n- Outline fact.\n\n"
            "## Chapter 02 — Conflict\n\n- Review fact.\n"
        )
        _canon_log(root, log)
        brief = build_canon_brief(root, "03-climax")

        facts = {f["fact"] for f in brief["current_facts"]}
        assert "Outline fact." not in facts
        assert "Review fact." in facts

    def test_scope_limits_chapter_count(self, tmp_path):
        root = _book(tmp_path)
        for i in range(1, 11):
            _chapter(root, f"{i:02d}-ch{i}", number=i)
        lines = "\n\n".join(
            f"## Chapter {i:02d} — Ch{i}\n\n- Fact from ch{i}." for i in range(1, 11)
        )
        _canon_log(root, lines)
        brief = build_canon_brief(root, "11-late", scope_chapters=3)

        # Only chapters 8, 9, 10 should be in scope
        assert set(brief["scanned_chapters"]) == {8, 9, 10}

    def test_changed_outside_scope_still_included(self, tmp_path):
        root = _book(tmp_path)
        _chapter(root, "01-setup", number=1)
        log = (
            "## Chapter 01 — Setup\n\n"
            "### Theo: skills\n"
            "- **CHANGED**: Old skill → New skill (revision_impact: 10-end)\n"
        )
        _canon_log(root, log)
        # Chapter 1 is outside scope=1 of chapter 10 because we only want the last 1
        brief = build_canon_brief(root, "10-end", scope_chapters=1)

        # CHANGED entry always included even outside scope
        assert brief["changed_facts"]
        assert brief["changed_facts"][0]["old"] == "Old skill"
        assert brief["changed_facts"][0]["new"] == "New skill"


# ---------------------------------------------------------------------------
# CHANGED entries
# ---------------------------------------------------------------------------


class TestChangedFacts:
    def test_changed_basic(self, tmp_path):
        root = _book(tmp_path)
        _chapter(root, "05-twist", number=5)
        log = (
            "## Chapter 05 — Twist\n\n"
            "### Theo: skills\n"
            "- **CHANGED**: Speaks French → Speaks Spanish "
            "(revision_impact: 06-aftermath, 08-reunion)\n"
        )
        _canon_log(root, log)
        brief = build_canon_brief(root, "09-end")

        cf = brief["changed_facts"][0]
        assert cf["old"] == "Speaks French"
        assert cf["new"] == "Speaks Spanish"
        assert cf["revision_impact"] == ["06-aftermath", "08-reunion"]
        assert cf["chapter"] == "05-twist"

    def test_changed_without_revision_impact(self, tmp_path):
        root = _book(tmp_path)
        _chapter(root, "02-conflict", number=2)
        log = (
            "## Chapter 02 — Conflict\n\n"
            "- **CHANGED**: Old → New\n"
        )
        _canon_log(root, log)
        brief = build_canon_brief(root, "03-climax")

        cf = brief["changed_facts"][0]
        assert cf["revision_impact"] == []

    def test_changed_not_in_current_facts(self, tmp_path):
        root = _book(tmp_path)
        _chapter(root, "01-setup", number=1)
        log = (
            "## Chapter 01 — Setup\n\n"
            "### Theo: skills\n"
            "- **CHANGED**: Old → New (revision_impact: 02-x)\n"
            "- Normal fact.\n"
        )
        _canon_log(root, log)
        brief = build_canon_brief(root, "02-conflict")

        facts_text = {f["fact"] for f in brief["current_facts"]}
        assert not any("CHANGED" in t for t in facts_text)
        assert "Normal fact." in facts_text

    def test_changed_source_includes_chapter_and_subject(self, tmp_path):
        root = _book(tmp_path)
        _chapter(root, "03-mid", number=3)
        log = (
            "## Chapter 03 — Mid\n\n"
            "### Anna: locations\n"
            "- **CHANGED**: In Hamburg → In Munich\n"
        )
        _canon_log(root, log)
        brief = build_canon_brief(root, "05-end")

        cf = brief["changed_facts"][0]
        assert "03-mid" in cf["source"]
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

    def test_pov_match_by_fact_text(self, tmp_path):
        root = _book(tmp_path)
        _chapter(root, "01-setup", number=1)
        log = (
            "## Chapter 01 — Setup\n\n"
            "- Theo is the protagonist.\n"
            "- Rain is falling.\n"
        )
        _canon_log(root, log)
        brief = build_canon_brief(root, "02-conflict", pov_character="Theo")

        pov_facts = {f["fact"] for f in brief["pov_relevant_facts"]}
        assert "Theo is the protagonist." in pov_facts
        assert "Rain is falling." not in pov_facts

    def test_multi_token_pov_matches_first_name_in_subject_header(self, tmp_path):
        # Issue #168: "Theo Wilkons" must match bullets under ### Theo: cognition
        # The old filter did whole-string substring match ("theo wilkons" not in source)
        root = _book(tmp_path)
        _chapter(root, "01-setup", number=1)
        log = (
            "## Chapter 01 — Setup\n\n"
            "### Theo: cognition\n"
            "- **Theo's question canon:** *\"Sera has been missing for three days.\"*\n\n"
            "### Kael: behavior\n"
            "- Kael avoids eye contact.\n"
        )
        _canon_log(root, log)
        brief = build_canon_brief(root, "02-conflict", pov_character="Theo Wilkons")

        assert len(brief["pov_relevant_facts"]) > 0, (
            "pov_relevant_facts must not be empty for multi-token POV name"
        )
        pov_sources = {f["source"] for f in brief["pov_relevant_facts"]}
        assert all("theo" in s.lower() for s in pov_sources)

    def test_multi_token_pov_no_false_positives_on_partial_match(self, tmp_path):
        # Word-boundary: "theo" must NOT match "theology"
        root = _book(tmp_path)
        _chapter(root, "01-setup", number=1)
        log = (
            "## Chapter 01 — Setup\n\n"
            "- Theology fascinates the scholar.\n"
            "- Theo arrived late.\n"
        )
        _canon_log(root, log)
        brief = build_canon_brief(root, "02-conflict", pov_character="Theo Wilkons")

        pov_facts = {f["fact"] for f in brief["pov_relevant_facts"]}
        assert "Theology fascinates the scholar." not in pov_facts
        assert "Theo arrived late." in pov_facts

    def test_single_token_pov_backward_compatible(self, tmp_path):
        # Single-name characters ("Kael") must still work after the token fix
        root = _book(tmp_path)
        _chapter(root, "01-setup", number=1)
        log = (
            "## Chapter 01 — Setup\n\n"
            "### Kael: behavior\n"
            "- Kael avoids eye contact.\n\n"
            "### Theo: cognition\n"
            "- Theo ponders the question.\n"
        )
        _canon_log(root, log)
        brief = build_canon_brief(root, "02-conflict", pov_character="Kael")

        assert len(brief["pov_relevant_facts"]) > 0
        pov_sources = {f["source"] for f in brief["pov_relevant_facts"]}
        assert all("kael" in s.lower() for s in pov_sources)

    def test_short_single_name_fallback(self, tmp_path):
        # Names shorter than 3 chars ("Bo") fall back to substring match, not empty list
        root = _book(tmp_path)
        _chapter(root, "01-setup", number=1)
        log = (
            "## Chapter 01 — Setup\n\n"
            "- Bo crossed the bridge.\n"
            "- Rain kept falling.\n"
        )
        _canon_log(root, log)
        brief = build_canon_brief(root, "02-conflict", pov_character="Bo")

        pov_facts = {f["fact"] for f in brief["pov_relevant_facts"]}
        assert "Bo crossed the bridge." in pov_facts
        assert "Rain kept falling." not in pov_facts

    def test_multi_token_pov_or_semantics_surname_match(self, tmp_path):
        # OR-semantics: a fact mentioning the surname alone still qualifies.
        # Documents the intentional behavior: canon logs referencing a character
        # by last name only are included in pov_relevant_facts.
        root = _book(tmp_path)
        _chapter(root, "01-setup", number=1)
        log = (
            "## Chapter 01 — Setup\n\n"
            "- Wilkons noticed the discrepancy.\n"
            "- Rain kept falling.\n"
        )
        _canon_log(root, log)
        brief = build_canon_brief(root, "02-conflict", pov_character="Theo Wilkons")

        pov_facts = {f["fact"] for f in brief["pov_relevant_facts"]}
        assert "Wilkons noticed the discrepancy." in pov_facts
        assert "Rain kept falling." not in pov_facts


# ---------------------------------------------------------------------------
# Slug normalisation
# ---------------------------------------------------------------------------


class TestSlugNormalisation:
    def test_chapter_slug_with_title(self, tmp_path):
        root = _book(tmp_path)
        _chapter(root, "01-setup", number=1)
        log = "## Chapter 01 — The Setup\n\n- A fact.\n"
        _canon_log(root, log)
        brief = build_canon_brief(root, "02-conflict")

        if brief["current_facts"]:
            assert brief["current_facts"][0]["chapter"] == "01-the-setup"

    def test_chapter_slug_without_title(self, tmp_path):
        root = _book(tmp_path)
        _chapter(root, "03-x", number=3)
        log = "## Chapter 03\n\n- A bare fact.\n"
        _canon_log(root, log)
        brief = build_canon_brief(root, "04-next")

        if brief["current_facts"]:
            assert brief["current_facts"][0]["chapter"] == "03"

    def test_as_of_string_type(self, tmp_path):
        root = _book(tmp_path)
        _chapter(root, "01-setup", number=1)
        _canon_log(root, "## Chapter 01 — Setup\n\n- Fact.\n")
        brief = build_canon_brief(root, "02-conflict")

        assert brief["as_of"] is None or isinstance(brief["as_of"], str)


# ---------------------------------------------------------------------------
# Heuristic fallback
# ---------------------------------------------------------------------------


class TestHeuristicFallback:
    def test_no_headers_uses_heuristic(self, tmp_path):
        root = _book(tmp_path)
        log = "Some fact about the world.\n- Another fact.\n- Third fact.\n"
        _canon_log(root, log)
        brief = build_canon_brief(root, "01-setup")

        assert brief["extraction_method"] == "heuristic"
        assert brief["warnings"]

    def test_heuristic_extracts_bullets(self, tmp_path):
        root = _book(tmp_path)
        log = "- First bullet.\n- Second bullet.\n"
        _canon_log(root, log)
        brief = build_canon_brief(root, "01-setup")

        facts = {f["fact"] for f in brief["current_facts"]}
        assert "First bullet." in facts
        assert "Second bullet." in facts

    def test_heuristic_scanned_chapters_empty(self, tmp_path):
        root = _book(tmp_path)
        _canon_log(root, "- Just a bullet.\n")
        brief = build_canon_brief(root, "01-setup")

        assert brief["scanned_chapters"] == []
        assert brief["as_of"] is None

    def test_heuristic_changed_extracted(self, tmp_path):
        root = _book(tmp_path)
        log = "- **CHANGED**: Old skill → New skill (revision_impact: 03-ch)\n- Normal.\n"
        _canon_log(root, log)
        brief = build_canon_brief(root, "01-setup")

        assert brief["changed_facts"]
        assert brief["changed_facts"][0]["source"] == "canon-log:CHANGED:heuristic"


# ---------------------------------------------------------------------------
# Memoir mode
# ---------------------------------------------------------------------------


class TestMemoirMode:
    def test_memoir_reads_people_log(self, tmp_path):
        root = _book(tmp_path, memoir=True)
        _chapter(root, "01-opening", number=1)
        (root / "plot" / "people-log.md").write_text(
            "## Chapter 01 — Opening\n\n### Mum: role\n- Mother of narrator.\n",
            encoding="utf-8",
        )
        brief = build_canon_brief(root, "02-next", book_category="memoir")

        assert brief["extraction_method"] == "section_regex"
        assert any("Mother of narrator." in f["fact"] for f in brief["current_facts"])

    def test_memoir_missing_people_log_returns_none(self, tmp_path):
        root = _book(tmp_path, memoir=True)
        brief = build_canon_brief(root, "01-opening", book_category="memoir")

        assert brief["extraction_method"] == "none"
        assert any("people-log.md" in w for w in brief["warnings"])

    def test_fiction_does_not_read_people_log(self, tmp_path):
        root = _book(tmp_path)
        (root / "plot" / "people-log.md").write_text(
            "## Chapter 01 — Setup\n\n- People fact.\n",
            encoding="utf-8",
        )
        brief = build_canon_brief(root, "02-conflict", book_category="fiction")

        # fiction reads canon-log.md which doesn't exist → none
        assert brief["extraction_method"] == "none"


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

    def test_pov_character_missing_yields_warning(self, tmp_path):
        """Issue #165 side observation: chapter without pov_character should warn
        so the skill knows why pov_relevant_facts is empty."""
        from tools.state.chapter_writing_brief import build_chapter_writing_brief
        from pathlib import Path as _Path

        plugin_root = _Path(__file__).resolve().parent.parent.parent
        book = _scaffold_book(tmp_path)
        # Populate canon-log so we hit the structured-extraction path.
        (book / "plot" / "canon-log.md").write_text(
            "## Chapter 01 — Setup\n\n- Some fact.\n", encoding="utf-8"
        )

        brief = build_chapter_writing_brief(
            book_root=book,
            book_slug="test-book",
            chapter_slug="01-setup",
            plugin_root=plugin_root,
        )

        warnings = brief["canon_brief"].get("warnings", [])
        assert any("pov_character" in w.lower() for w in warnings), (
            f"expected pov_character warning, got: {warnings}"
        )
