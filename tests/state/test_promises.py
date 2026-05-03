"""Tests for ``tools.state.promises`` — Issue #150.

Persists per-chapter setup-element promises into the chapter README's
``## Promises`` section. Used by:
- chapter-writer (auto-extracts promises at Draft → Review transition)
- /storyforge:backfill-promises (LLM pass over already-drafted books)
- analyze_plot_logic (reads the index for chekhov_gun detection)
"""

from __future__ import annotations

import textwrap
from pathlib import Path

import pytest

from tools.state.promises import (
    Promise,
    collect_book_promises,
    parse_promises_section,
    render_promises_section,
    upsert_promises,
)


# ---------------------------------------------------------------------------
# Test fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def chapter_readme_no_promises(tmp_path: Path) -> Path:
    readme = tmp_path / "README.md"
    readme.write_text(
        textwrap.dedent(
            """\
            ---
            title: "Test Chapter"
            number: 5
            slug: "05-test"
            status: "Draft"
            ---

            # Chapter 5: Test

            ## Outline

            Some outline text.

            ## Chapter Timeline

            **Start:** Mon ~10:00
            **End:** Mon ~12:00

            ## Notes

            Writing notes.
            """
        ),
        encoding="utf-8",
    )
    return readme


@pytest.fixture
def chapter_readme_with_promises(tmp_path: Path) -> Path:
    readme = tmp_path / "README.md"
    readme.write_text(
        textwrap.dedent(
            """\
            ---
            title: "Test Chapter"
            ---

            # Chapter 5: Test

            ## Outline

            Some outline.

            ## Promises

            *Setup elements placed in this chapter that need payoff later.*

            | Promise | Target | Status |
            |---------|--------|--------|
            | The locked drawer in the office | 14-the-letter | active |
            | Theo's rifle claim | unfired | active |

            ## Notes

            More notes.
            """
        ),
        encoding="utf-8",
    )
    return readme


# ---------------------------------------------------------------------------
# parse_promises_section
# ---------------------------------------------------------------------------


class TestParsePromisesSection:
    def test_returns_empty_list_when_no_section(self, chapter_readme_no_promises: Path):
        promises = parse_promises_section(chapter_readme_no_promises.read_text(encoding="utf-8"))
        assert promises == []

    def test_parses_two_promises(self, chapter_readme_with_promises: Path):
        promises = parse_promises_section(chapter_readme_with_promises.read_text(encoding="utf-8"))
        assert len(promises) == 2
        assert promises[0] == Promise(
            description="The locked drawer in the office",
            target="14-the-letter",
            status="active",
        )
        assert promises[1] == Promise(
            description="Theo's rifle claim",
            target="unfired",
            status="active",
        )

    def test_normalizes_status_case(self):
        text = (
            "## Promises\n\n"
            "| Promise | Target | Status |\n"
            "|---------|--------|--------|\n"
            "| Thing one | unfired | ACTIVE |\n"
            "| Thing two | 10-payoff | Satisfied |\n"
        )
        promises = parse_promises_section(text)
        assert promises[0].status == "active"
        assert promises[1].status == "satisfied"

    def test_skips_empty_rows(self):
        text = (
            "## Promises\n\n"
            "| Promise | Target | Status |\n"
            "|---------|--------|--------|\n"
            "|  |  |  |\n"
            "| Real promise | unfired | active |\n"
        )
        promises = parse_promises_section(text)
        assert len(promises) == 1
        assert promises[0].description == "Real promise"

    def test_handles_chapter_number_targets(self):
        # "Ch 14" should be normalized to a comparable form.
        text = (
            "## Promises\n\n| Promise | Target | Status |\n|---------|--------|--------|\n| Drawer | Ch 14 | active |\n"
        )
        promises = parse_promises_section(text)
        assert promises[0].target == "Ch 14"

    def test_section_terminated_by_next_heading(self):
        text = (
            "## Promises\n\n"
            "| Promise | Target | Status |\n"
            "|---------|--------|--------|\n"
            "| First | unfired | active |\n\n"
            "## Notes\n\n"
            "| Promise | Target | Status |\n"
            "|---------|--------|--------|\n"
            "| Should not be parsed | x | active |\n"
        )
        promises = parse_promises_section(text)
        assert len(promises) == 1
        assert promises[0].description == "First"


# ---------------------------------------------------------------------------
# render_promises_section
# ---------------------------------------------------------------------------


class TestRenderPromisesSection:
    def test_empty_list_renders_placeholder_section(self):
        rendered = render_promises_section([])
        assert "## Promises" in rendered
        assert "no promises this chapter" in rendered.lower()

    def test_renders_table_with_two_rows(self):
        promises = [
            Promise(description="The drawer", target="14-letter", status="active"),
            Promise(description="The rifle", target="unfired", status="active"),
        ]
        rendered = render_promises_section(promises)
        assert "## Promises" in rendered
        assert "| Promise | Target | Status |" in rendered
        assert "| The drawer | 14-letter | active |" in rendered
        assert "| The rifle | unfired | active |" in rendered

    def test_includes_help_comment(self):
        rendered = render_promises_section([Promise("X", "unfired", "active")])
        assert "Setup elements" in rendered or "Auto-populated" in rendered


# ---------------------------------------------------------------------------
# upsert_promises — write/merge into chapter README
# ---------------------------------------------------------------------------


class TestUpsertPromises:
    def test_adds_section_to_readme_without_one(self, chapter_readme_no_promises: Path):
        result = upsert_promises(
            chapter_readme_no_promises,
            [Promise("Locked drawer", "14-letter", "active")],
        )
        text = chapter_readme_no_promises.read_text(encoding="utf-8")
        assert "## Promises" in text
        assert "| Locked drawer | 14-letter | active |" in text
        assert result["added"] == 1
        assert result["updated"] == 0
        assert result["unchanged"] == 0

    def test_section_inserted_before_notes(self, chapter_readme_no_promises: Path):
        upsert_promises(
            chapter_readme_no_promises,
            [Promise("X", "unfired", "active")],
        )
        text = chapter_readme_no_promises.read_text(encoding="utf-8")
        promises_idx = text.index("## Promises")
        notes_idx = text.index("## Notes")
        assert promises_idx < notes_idx

    def test_merges_with_existing_promises_no_duplicates(self, chapter_readme_with_promises: Path):
        # Existing: drawer + rifle. Add a new one + re-add the rifle.
        result = upsert_promises(
            chapter_readme_with_promises,
            [
                Promise("Theo's rifle claim", "unfired", "active"),  # duplicate
                Promise("Maria's camera", "unfired", "active"),  # new
            ],
        )
        text = chapter_readme_with_promises.read_text(encoding="utf-8")
        # Must contain all three, not four.
        assert text.count("Theo's rifle claim") == 1
        assert "Maria's camera" in text
        assert result["added"] == 1
        assert result["unchanged"] == 1

    def test_updates_status_change_on_existing_promise(self, chapter_readme_with_promises: Path):
        result = upsert_promises(
            chapter_readme_with_promises,
            [Promise("Theo's rifle claim", "unfired", "satisfied")],
        )
        text = chapter_readme_with_promises.read_text(encoding="utf-8")
        # Old "active" line must be gone, new "satisfied" line present.
        assert "| Theo's rifle claim | unfired | satisfied |" in text
        assert "| Theo's rifle claim | unfired | active |" not in text
        assert result["updated"] == 1

    def test_idempotent_second_call_no_change(self, chapter_readme_no_promises: Path):
        promises = [Promise("Drawer", "14-letter", "active")]
        upsert_promises(chapter_readme_no_promises, promises)
        first = chapter_readme_no_promises.read_text(encoding="utf-8")
        result = upsert_promises(chapter_readme_no_promises, promises)
        second = chapter_readme_no_promises.read_text(encoding="utf-8")
        assert first == second
        assert result["unchanged"] == 1
        assert result["added"] == 0

    def test_preserves_unrelated_sections(self, chapter_readme_with_promises: Path):
        upsert_promises(
            chapter_readme_with_promises,
            [Promise("New thing", "unfired", "active")],
        )
        text = chapter_readme_with_promises.read_text(encoding="utf-8")
        assert "## Outline" in text
        assert "## Notes" in text
        assert "More notes." in text

    def test_empty_promise_list_creates_placeholder_section(self, chapter_readme_no_promises: Path):
        # Calling with [] when section doesn't exist should write a
        # placeholder so downstream readers know "we checked, nothing
        # to promise" — distinct from "we never ran the extractor".
        result = upsert_promises(chapter_readme_no_promises, [])
        text = chapter_readme_no_promises.read_text(encoding="utf-8")
        assert "## Promises" in text
        assert "no promises this chapter" in text.lower()
        assert result["added"] == 0

    def test_rejects_invalid_status(self, chapter_readme_no_promises: Path):
        with pytest.raises(ValueError, match="status"):
            upsert_promises(
                chapter_readme_no_promises,
                [Promise("X", "unfired", "in-progress")],  # invalid
            )

    def test_rejects_empty_description(self, chapter_readme_no_promises: Path):
        with pytest.raises(ValueError, match="description"):
            upsert_promises(
                chapter_readme_no_promises,
                [Promise("", "unfired", "active")],
            )


# ---------------------------------------------------------------------------
# collect_book_promises — walk a book's chapters and gather all promises
# ---------------------------------------------------------------------------


class TestCollectBookPromises:
    def _make_chapter(self, root: Path, slug: str, body: str) -> None:
        ch_dir = root / "chapters" / slug
        ch_dir.mkdir(parents=True, exist_ok=True)
        (ch_dir / "README.md").write_text(body, encoding="utf-8")

    def test_returns_empty_when_no_chapters_dir(self, tmp_path: Path):
        assert collect_book_promises(tmp_path) == []

    def test_returns_empty_when_no_promises_anywhere(self, tmp_path: Path):
        self._make_chapter(tmp_path, "01-opening", "# Ch 1\n\n## Outline\n")
        self._make_chapter(tmp_path, "02-rising", "# Ch 2\n\n## Outline\n")
        assert collect_book_promises(tmp_path) == []

    def test_collects_across_chapters_in_order(self, tmp_path: Path):
        self._make_chapter(
            tmp_path,
            "01-opening",
            "# Ch 1\n\n## Promises\n\n"
            "| Promise | Target | Status |\n"
            "|---------|--------|--------|\n"
            "| The drawer | 14-letter | active |\n",
        )
        self._make_chapter(tmp_path, "02-rising", "# Ch 2\n")  # no promises
        self._make_chapter(
            tmp_path,
            "03-twist",
            "# Ch 3\n\n## Promises\n\n"
            "| Promise | Target | Status |\n"
            "|---------|--------|--------|\n"
            "| Maria's camera | unfired | active |\n",
        )
        result = collect_book_promises(tmp_path)
        assert len(result) == 2
        assert result[0]["source_chapter"] == "01-opening"
        assert result[0]["promise"].description == "The drawer"
        assert result[1]["source_chapter"] == "03-twist"
        assert result[1]["promise"].description == "Maria's camera"
