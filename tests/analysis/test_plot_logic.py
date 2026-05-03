"""Tests for ``tools.analysis.plot_logic`` — Issue #150.

The plot_logic module is the deterministic half of the plothole
checker: it builds a knowledge index from canon-log + timeline +
chapter promises, then runs static detectors for the categories
that don't need an LLM (causality_inversion, chekhov_gun). The
semantic categories (information_leak, motivation_break,
premise_violation) are picked up later by the chapter-reviewer and
manuscript-checker skills using this module's index.
"""

from __future__ import annotations

import textwrap
from pathlib import Path

import pytest

from tools.analysis.plot_logic import (
    analyze_plot_logic,
    build_knowledge_index,
    detect_causality_inversion,
    detect_chekhov_guns,
)


# ---------------------------------------------------------------------------
# Test-book builder — minimal scaffold for plot-logic tests
# ---------------------------------------------------------------------------


def _make_book(
    root: Path,
    *,
    book_category: str = "fiction",
    timeline_md: str | None = None,
    canon_log: str | None = None,
    chapters: list[dict] | None = None,
) -> Path:
    """Build a minimal test book at ``root``. Returns ``root`` for chaining."""
    (root / "plot").mkdir(parents=True, exist_ok=True)
    (root / "chapters").mkdir(parents=True, exist_ok=True)

    (root / "README.md").write_text(
        f"---\ntitle: 'Test'\nslug: 'test-book'\nbook_category: {book_category}\n---\n# Test\n",
        encoding="utf-8",
    )

    if timeline_md is not None:
        (root / "plot" / "timeline.md").write_text(timeline_md, encoding="utf-8")
    if canon_log is not None:
        (root / "plot" / "canon-log.md").write_text(canon_log, encoding="utf-8")

    for ch in chapters or []:
        ch_dir = root / "chapters" / ch["slug"]
        ch_dir.mkdir(parents=True, exist_ok=True)
        (ch_dir / "README.md").write_text(ch.get("readme", ""), encoding="utf-8")
        if "draft" in ch:
            (ch_dir / "draft.md").write_text(ch["draft"], encoding="utf-8")

    return root


_BASIC_TIMELINE = textwrap.dedent(
    """\
    # Plot Timeline

    ## Anchor

    | Story Start | Real Date | DoW | Notes |
    |---|---|---|---|
    | Day 1 | Aug 3, 2026 | Monday | — |

    ## Event Calendar

    | Story Day | Real Date | Day of Week | Chapter | Location | Key Events | Characters |
    |---|---|---|---|---|---|---|
    | Day 1 | Aug 3, 2026 | Monday | Ch 01 | Cottage | Opening | Sarah |
    | Day 1 | Aug 3, 2026 | Monday | Ch 02 | Cottage | Continued | Sarah |
    | Day 3 | Aug 5, 2026 | Wednesday | Ch 03 | Forest | Discovery | Sarah, Tom |
    | Day 5 | Aug 7, 2026 | Friday | Ch 04 | Village | Confrontation | Sarah, Tom |
    """
)


# ---------------------------------------------------------------------------
# build_knowledge_index
# ---------------------------------------------------------------------------


class TestBuildKnowledgeIndex:
    def test_returns_empty_index_for_minimal_book(self, tmp_path: Path):
        book = _make_book(tmp_path)
        idx = build_knowledge_index(book)
        assert idx["chapter_story_days"] == {}
        assert idx["facts"] == []
        assert idx["promises"] == []
        assert idx["book_category"] == "fiction"

    def test_collects_chapter_story_days_from_timeline(self, tmp_path: Path):
        book = _make_book(
            tmp_path,
            timeline_md=_BASIC_TIMELINE,
            chapters=[
                {"slug": "01-opening", "readme": "# Ch 1\n"},
                {"slug": "02-rising", "readme": "# Ch 2\n"},
                {"slug": "03-twist", "readme": "# Ch 3\n"},
                {"slug": "04-clash", "readme": "# Ch 4\n"},
            ],
        )
        idx = build_knowledge_index(book)
        assert idx["chapter_story_days"]["01-opening"] == 1
        assert idx["chapter_story_days"]["02-rising"] == 1
        assert idx["chapter_story_days"]["03-twist"] == 3
        assert idx["chapter_story_days"]["04-clash"] == 5

    def test_collects_canon_log_facts(self, tmp_path: Path):
        canon = textwrap.dedent(
            """\
            # Canon Log

            ## Established Facts

            ### Character Facts

            | Fact | Established In | Status | Notes |
            |---|---|---|---|
            | Sarah is immortal | Ch 3 | ACTIVE | Revealed at the river |

            ### World / Setting Facts

            | Fact | Established In | Status | Notes |
            |---|---|---|---|
            | Bound spirits cannot cross water | Ch 2 | ACTIVE | First binder rule |
            """
        )
        book = _make_book(tmp_path, canon_log=canon)
        idx = build_knowledge_index(book)
        assert len(idx["facts"]) == 2
        sarah = next(f for f in idx["facts"] if "Sarah" in f["fact"])
        assert sarah["established_in"] == "Ch 3"
        assert sarah["domain"] == "Character Facts"

    def test_collects_promises_with_source_chapter(self, tmp_path: Path):
        readme = textwrap.dedent(
            """\
            # Ch 1

            ## Promises

            | Promise | Target | Status |
            |---|---|---|
            | The locked drawer | 04-clash | active |
            """
        )
        book = _make_book(
            tmp_path,
            chapters=[{"slug": "01-opening", "readme": readme}],
        )
        idx = build_knowledge_index(book)
        assert len(idx["promises"]) == 1
        assert idx["promises"][0]["source_chapter"] == "01-opening"
        assert idx["promises"][0]["target"] == "04-clash"

    def test_book_category_memoir_propagates(self, tmp_path: Path):
        book = _make_book(tmp_path, book_category="memoir")
        idx = build_knowledge_index(book)
        assert idx["book_category"] == "memoir"


# ---------------------------------------------------------------------------
# detect_causality_inversion
# ---------------------------------------------------------------------------


class TestDetectCausalityInversion:
    def test_no_findings_when_no_facts(self, tmp_path: Path):
        book = _make_book(tmp_path, timeline_md=_BASIC_TIMELINE)
        idx = build_knowledge_index(book)
        assert detect_causality_inversion(book, idx) == []

    def test_flags_reaction_before_event(self, tmp_path: Path):
        # Ch 03 (story-day 3) references a fact established in Ch 04 (story-day 5).
        # That's a causality inversion.
        canon = textwrap.dedent(
            """\
            ## Established Facts

            ### Plot Facts

            | Fact | Established In | Status | Notes |
            |---|---|---|---|
            | Tom confesses to the murder | Ch 04 | ACTIVE | First confession |
            """
        )
        ch3_draft = (
            "Sarah walked through the forest.\n\n"
            "She'd been thinking about Tom's confession all morning, "
            "the way his voice cracked when he finally said it.\n"
        )
        book = _make_book(
            tmp_path,
            timeline_md=_BASIC_TIMELINE,
            canon_log=canon,
            chapters=[
                {"slug": "01-opening", "readme": "# Ch 1\n", "draft": "Opening prose.\n"},
                {"slug": "02-rising", "readme": "# Ch 2\n", "draft": "Rising prose.\n"},
                {"slug": "03-twist", "readme": "# Ch 3\n", "draft": ch3_draft},
                {"slug": "04-clash", "readme": "# Ch 4\n", "draft": "Tom confesses.\n"},
            ],
        )
        idx = build_knowledge_index(book)
        findings = detect_causality_inversion(book, idx)
        assert len(findings) == 1
        f = findings[0]
        assert f.category == "causality_inversion"
        assert f.severity == "high"
        assert f.chapter == "03-twist"
        assert "confession" in f.snippet.lower()
        # Evidence must name both story-days for the human reviewer.
        assert "3" in f.evidence and "5" in f.evidence

    def test_no_findings_when_reference_in_later_chapter(self, tmp_path: Path):
        # Chapter 04 (story-day 5) referencing event established at Ch 04 — fine.
        canon = textwrap.dedent(
            """\
            ## Established Facts

            ### Plot Facts

            | Fact | Established In | Status | Notes |
            |---|---|---|---|
            | Tom confesses | Ch 04 | ACTIVE | — |
            """
        )
        book = _make_book(
            tmp_path,
            timeline_md=_BASIC_TIMELINE,
            canon_log=canon,
            chapters=[
                {"slug": "04-clash", "readme": "# Ch 4\n", "draft": "Tom's confession echoed.\n"},
            ],
        )
        idx = build_knowledge_index(book)
        # Even though the chapter mentions "confession", chapter 04 is the
        # establishing chapter — no inversion.
        assert detect_causality_inversion(book, idx) == []

    def test_skips_facts_without_parseable_chapter_anchor(self, tmp_path: Path):
        # An "established_in" value the timeline can't map to a story-day
        # should not produce a false-positive finding.
        canon = textwrap.dedent(
            """\
            ## Established Facts

            ### Plot Facts

            | Fact | Established In | Status | Notes |
            |---|---|---|---|
            | Some fact | (TBD) | ACTIVE | — |
            """
        )
        book = _make_book(
            tmp_path,
            timeline_md=_BASIC_TIMELINE,
            canon_log=canon,
            chapters=[
                {"slug": "01-opening", "readme": "# Ch 1\n", "draft": "Some fact appears.\n"},
            ],
        )
        idx = build_knowledge_index(book)
        assert detect_causality_inversion(book, idx) == []


# ---------------------------------------------------------------------------
# detect_chekhov_guns
# ---------------------------------------------------------------------------


class TestDetectChekhovGuns:
    def test_no_findings_when_no_promises(self, tmp_path: Path):
        book = _make_book(tmp_path, timeline_md=_BASIC_TIMELINE)
        idx = build_knowledge_index(book)
        assert detect_chekhov_guns(book, idx) == []

    def test_flags_dropped_promise_with_target_reached(self, tmp_path: Path):
        # Promise from Ch 01 with target Ch 03. Ch 03 draft does NOT
        # reference the promise → dropped.
        readme1 = textwrap.dedent(
            """\
            # Ch 1

            ## Promises

            | Promise | Target | Status |
            |---|---|---|
            | The locked drawer in the office | 03-twist | active |
            """
        )
        book = _make_book(
            tmp_path,
            chapters=[
                {"slug": "01-opening", "readme": readme1, "draft": "Marcus locked the drawer.\n"},
                {
                    "slug": "03-twist",
                    "readme": "# Ch 3\n",
                    "draft": "Sarah walked through the forest, no drawers in sight.\n",
                },
            ],
        )
        idx = build_knowledge_index(book)
        findings = detect_chekhov_guns(book, idx)
        assert len(findings) == 1
        f = findings[0]
        assert f.category == "chekhov_gun"
        assert f.severity == "high"
        assert "drawer" in f.snippet.lower() or "drawer" in f.evidence.lower()

    def test_satisfied_promise_when_target_references(self, tmp_path: Path):
        readme1 = textwrap.dedent(
            """\
            # Ch 1

            ## Promises

            | Promise | Target | Status |
            |---|---|---|
            | The locked drawer in the office | 03-twist | active |
            """
        )
        book = _make_book(
            tmp_path,
            chapters=[
                {"slug": "01-opening", "readme": readme1, "draft": "Setup.\n"},
                {
                    "slug": "03-twist",
                    "readme": "# Ch 3\n",
                    "draft": "She finally opened the locked drawer in the office.\n",
                },
            ],
        )
        idx = build_knowledge_index(book)
        # Token-overlap match — "locked drawer" present in target draft.
        assert detect_chekhov_guns(book, idx) == []

    def test_unfired_promise_at_book_end_flags_high(self, tmp_path: Path):
        # Promise marked target=unfired, no later chapter references it →
        # high severity at end-of-book scan.
        readme1 = textwrap.dedent(
            """\
            # Ch 1

            ## Promises

            | Promise | Target | Status |
            |---|---|---|
            | Maria's hidden camera | unfired | active |
            """
        )
        book = _make_book(
            tmp_path,
            chapters=[
                {"slug": "01-opening", "readme": readme1, "draft": "Setup.\n"},
                {"slug": "02-rising", "readme": "# Ch 2\n", "draft": "No camera.\n"},
            ],
        )
        idx = build_knowledge_index(book)
        findings = detect_chekhov_guns(book, idx)
        assert len(findings) == 1
        assert findings[0].severity == "high"
        assert "camera" in findings[0].snippet.lower()

    def test_retired_promise_is_ignored(self, tmp_path: Path):
        readme1 = textwrap.dedent(
            """\
            # Ch 1

            ## Promises

            | Promise | Target | Status |
            |---|---|---|
            | Old idea | 03-twist | retired |
            """
        )
        book = _make_book(
            tmp_path,
            chapters=[
                {"slug": "01-opening", "readme": readme1, "draft": "Setup.\n"},
                {"slug": "03-twist", "readme": "# Ch 3\n", "draft": "Different content.\n"},
            ],
        )
        idx = build_knowledge_index(book)
        assert detect_chekhov_guns(book, idx) == []


# ---------------------------------------------------------------------------
# analyze_plot_logic — top-level wrapper
# ---------------------------------------------------------------------------


class TestAnalyzePlotLogic:
    def test_returns_index_plus_findings_plus_gate(self, tmp_path: Path):
        book = _make_book(tmp_path, timeline_md=_BASIC_TIMELINE)
        result = analyze_plot_logic(book, scope="manuscript")
        assert "knowledge_index" in result
        assert "findings" in result
        assert "gate" in result
        assert result["gate"]["status"] == "PASS"

    def test_pass_gate_when_no_findings(self, tmp_path: Path):
        book = _make_book(tmp_path)
        result = analyze_plot_logic(book, scope="manuscript")
        assert result["gate"]["status"] == "PASS"
        assert result["findings"] == []

    def test_fail_gate_on_high_severity_finding(self, tmp_path: Path):
        canon = textwrap.dedent(
            """\
            ## Established Facts

            ### Plot Facts

            | Fact | Established In | Status | Notes |
            |---|---|---|---|
            | The confession | Ch 04 | ACTIVE | — |
            """
        )
        book = _make_book(
            tmp_path,
            timeline_md=_BASIC_TIMELINE,
            canon_log=canon,
            chapters=[
                {
                    "slug": "03-twist",
                    "readme": "# Ch 3\n",
                    "draft": "Sarah remembered the confession.\n",
                },
                {"slug": "04-clash", "readme": "# Ch 4\n", "draft": "The confession.\n"},
            ],
        )
        result = analyze_plot_logic(book, scope="manuscript")
        assert result["gate"]["status"] == "FAIL"
        assert any(f["category"] == "causality_inversion" for f in result["findings"])

    def test_memoir_skips_chekhov_gun(self, tmp_path: Path):
        readme1 = textwrap.dedent(
            """\
            # Ch 1

            ## Promises

            | Promise | Target | Status |
            |---|---|---|
            | A strange recurring dream | unfired | active |
            """
        )
        book = _make_book(
            tmp_path,
            book_category="memoir",
            chapters=[
                {"slug": "01-opening", "readme": readme1, "draft": "Setup.\n"},
                {"slug": "02-later", "readme": "# Ch 2\n", "draft": "No dream.\n"},
            ],
        )
        result = analyze_plot_logic(book, scope="manuscript")
        # Memoir skips chekhov_gun — even an unfired promise yields no
        # finding in this category.
        assert all(f["category"] != "chekhov_gun" for f in result["findings"])

    def test_chapter_scope_returns_findings_for_one_chapter_only(self, tmp_path: Path):
        canon = textwrap.dedent(
            """\
            ## Established Facts

            ### Plot Facts

            | Fact | Established In | Status | Notes |
            |---|---|---|---|
            | The confession | Ch 04 | ACTIVE | — |
            """
        )
        book = _make_book(
            tmp_path,
            timeline_md=_BASIC_TIMELINE,
            canon_log=canon,
            chapters=[
                {
                    "slug": "03-twist",
                    "readme": "# Ch 3\n",
                    "draft": "Sarah remembered the confession.\n",
                },
                {
                    "slug": "01-opening",
                    "readme": "# Ch 1\n",
                    "draft": "Different chapter, also references confession.\n",
                },
            ],
        )
        result = analyze_plot_logic(book, scope="chapter", chapter_slug="03-twist")
        # Only chapter 03's finding should be present.
        assert all(f["chapter"] == "03-twist" for f in result["findings"])

    def test_chapter_scope_skips_chekhov_gun(self, tmp_path: Path):
        # chekhov_gun requires manuscript-wide context; chapter scope skips it.
        readme1 = textwrap.dedent(
            """\
            # Ch 1

            ## Promises

            | Promise | Target | Status |
            |---|---|---|
            | The drawer | unfired | active |
            """
        )
        book = _make_book(
            tmp_path,
            chapters=[
                {"slug": "01-opening", "readme": readme1, "draft": "Setup.\n"},
            ],
        )
        result = analyze_plot_logic(book, scope="chapter", chapter_slug="01-opening")
        assert all(f["category"] != "chekhov_gun" for f in result["findings"])

    def test_invalid_scope_raises(self, tmp_path: Path):
        book = _make_book(tmp_path)
        with pytest.raises(ValueError, match="scope"):
            analyze_plot_logic(book, scope="bogus")  # type: ignore[arg-type]

    def test_chapter_scope_requires_chapter_slug(self, tmp_path: Path):
        book = _make_book(tmp_path)
        with pytest.raises(ValueError, match="chapter_slug"):
            analyze_plot_logic(book, scope="chapter")
