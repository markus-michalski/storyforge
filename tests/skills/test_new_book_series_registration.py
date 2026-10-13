"""Regression guard for Issue #633: `new-book/SKILL.md`'s Step 6
("Auto-copy recurring characters") ran directly after project creation,
while the book's `series_number` was still the `0` scaffold default — the
skill never called `add_book_to_series()`, never passed `series_slug` to
`create_book_structure()`, its skip rule covered `series_number` "missing
or 1" but not `0`, and its auto-detection pointed at a `series/{slug}/
books/` directory that doesn't exist (books are nested directly at
`series/{slug}/{book}/`; the real registry is `series.yaml`'s `books:`
list). The net effect: the step silently copied nothing for the standard
"create a book in an existing series" flow.

This checks the specific stale/missing pieces rather than re-parsing the
whole skill's workflow structure — there's no executable status model to
ground a drift guard against here (unlike #631/#642), just prose that
either does or doesn't mention the right calls.
"""

from __future__ import annotations

from pathlib import Path

PLUGIN_ROOT = Path(__file__).resolve().parent.parent.parent
NEW_BOOK_SKILL = PLUGIN_ROOT / "skills" / "new-book" / "SKILL.md"


class TestNewBookSeriesRegistration:
    def test_does_not_reference_the_nonexistent_books_directory(self) -> None:
        text = NEW_BOOK_SKILL.read_text(encoding="utf-8")
        assert "series/{slug}/books/" not in text, (
            "skills/new-book/SKILL.md still points auto-detection at "
            "series/{slug}/books/, which doesn't exist — books are nested "
            "directly at series/{slug}/{book}/ (Issue #633)."
        )

    def test_calls_add_book_to_series_before_the_copy_step(self) -> None:
        """`add_book_to_series(` alone is too loose — Step 1 and Step 6 both
        mention the tool name in passing (deferring the number, explaining
        where series_number comes from) without actually calling it. Anchor
        on the full call signature, which only the actual invocation uses.
        """
        text = NEW_BOOK_SKILL.read_text(encoding="utf-8")
        call_signature = "add_book_to_series(series_slug, book_slug, number)"
        assert call_signature in text, (
            "skills/new-book/SKILL.md never calls add_book_to_series() — "
            "series_number stays 0 for every book created in a series, so "
            "the recurring-characters copy step always finds nothing to "
            "copy (Issue #633)."
        )
        # It must appear before the copy step's own section, not just
        # anywhere in the file (e.g. a passing mention elsewhere) — Step 6
        # is the Issue #196 "Auto-copy recurring characters" heading.
        add_idx = text.index(call_signature)
        copy_step_idx = text.index("Auto-copy recurring characters from prior book in series")
        assert add_idx < copy_step_idx, (
            "add_book_to_series() must be called before the auto-copy step "
            "runs, not after — the copy step needs the real series_number."
        )

    def test_skip_rule_covers_the_series_number_zero_scaffold_default(self) -> None:
        """Scoped to Step 6's own skip-rule sentence, not the whole file —
        a future, unrelated mention of the literal `0` anywhere else would
        otherwise keep this green even if the skip rule itself regressed.
        """
        text = NEW_BOOK_SKILL.read_text(encoding="utf-8")
        skip_rule_idx = text.index("Skip this entire step")
        copy_step_idx = text.index("Show the planned copy")
        skip_rule_text = text[skip_rule_idx:copy_step_idx]
        assert "`0`" in skip_rule_text and "series_number" in skip_rule_text, (
            "skills/new-book/SKILL.md's Step 6 skip rule must explicitly "
            "cover series_number == 0 (the create_book_structure() scaffold "
            "default), not just 'missing or 1' (Issue #633)."
        )

    def test_create_project_step_can_pass_series_slug(self) -> None:
        """series_slug is mentioned several places in this skill already
        (the --series= CLI example, the copy_recurring_chars_to_new_book
        call) — this must specifically be about create_book_structure()'s
        own call, or it passes vacuously against the pre-#633 text too.
        """
        text = NEW_BOOK_SKILL.read_text(encoding="utf-8")
        create_call_idx = text.index("create_book_structure()")
        # The series_slug mention belongs to the same step as the
        # create_book_structure() call — look within the following ~800
        # chars (this step's own prose), not the whole file.
        step_text = text[create_call_idx : create_call_idx + 800]
        assert "series_slug" in step_text, (
            "skills/new-book/SKILL.md's project-creation step never passes "
            "series_slug to create_book_structure() — a book meant for a "
            "series is scaffolded as a standalone book instead (Issue #633)."
        )
