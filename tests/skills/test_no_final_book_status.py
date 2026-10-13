"""Regression guard for Issue #631: `harvest-character-evolution/SKILL.md`
and `bootstrap-book-from-series/SKILL.md` named the book status `Final` as
an accepted value for their status gate. No such book status exists —
`Final` is a valid *chapter* status (`tools/state/parsers.py`'s
`_CHAPTER_STATUS_MAP`) and a valid *character* status, but
`_BOOK_STATUS_MAP` has no `Final` entry. A book whose chapters are all
`Final` derives to `Proofread` (`derive_book_status`), which these skills'
own warn tier already covers — and the fixed skill text now says so,
legitimately using `` `Final` `` to name that chapter status. So this guard
checks for the specific buggy status-gate phrasing, not a blanket "no
`Final` anywhere in the file" — that would also flag the fix's own
explanation of what `Final` actually means at the chapter level.
"""

from __future__ import annotations

from pathlib import Path

from tools.state.parsers import _BOOK_STATUS_MAP

PLUGIN_ROOT = Path(__file__).resolve().parent.parent.parent
HARVEST_SKILL = PLUGIN_ROOT / "skills" / "harvest-character-evolution" / "SKILL.md"
BOOTSTRAP_SKILL = PLUGIN_ROOT / "skills" / "bootstrap-book-from-series" / "SKILL.md"


class TestNoFinalBookStatus:
    def test_final_is_not_a_valid_book_status(self) -> None:
        """Ground the regression in the actual status model: if `Final` is
        ever added to `_BOOK_STATUS_MAP`, this whole test module is moot and
        should be deleted along with Issue #631's fix, not left green by
        accident.
        """
        assert "Final" not in _BOOK_STATUS_MAP.values()

    @staticmethod
    def _assert_no_final_as_book_status_alternative(text: str, skill_md_path: Path) -> None:
        # The buggy pattern always listed Final alongside Export Ready/
        # Published as interchangeable book-status alternatives, joined by
        # "/" or ", or" — exactly the shape a book-status gate uses to list
        # its accepted values.
        buggy_patterns = [
            "`Final` / `Export Ready` / `Published`",
            "`Final`, `Export Ready`, or `Published`",
            "`Final` / `Export Ready`",
        ]
        for pattern in buggy_patterns:
            assert pattern not in text, (
                f"{skill_md_path.relative_to(PLUGIN_ROOT)} still lists `Final` "
                f"as a book-status alternative ({pattern!r}) — no such book "
                f"status exists (Issue #631)."
            )

    def test_harvest_character_evolution_has_no_final_book_status_reference(self) -> None:
        text = HARVEST_SKILL.read_text(encoding="utf-8")
        self._assert_no_final_as_book_status_alternative(text, HARVEST_SKILL)

    def test_bootstrap_book_from_series_has_no_final_book_status_reference(self) -> None:
        text = BOOTSTRAP_SKILL.read_text(encoding="utf-8")
        self._assert_no_final_as_book_status_alternative(text, BOOTSTRAP_SKILL)
