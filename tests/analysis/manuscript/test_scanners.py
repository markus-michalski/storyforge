"""Unit tests for tools.analysis.manuscript.scanners."""

from __future__ import annotations

from pathlib import Path

from tools.analysis.manuscript.scanners import (
    _scan_question_as_statement,
    _scan_sentence_repetitions,
)


def _write_book(tmp_path: Path, chapters: dict[str, str], claudemd: str = "# Test Book\n") -> Path:
    book = tmp_path / "book"
    book.mkdir()
    (book / "CLAUDE.md").write_text(claudemd, encoding="utf-8")
    chapters_dir = book / "chapters"
    chapters_dir.mkdir()
    for slug, content in chapters.items():
        d = chapters_dir / slug
        d.mkdir()
        (d / "draft.md").write_text(content, encoding="utf-8")
    return book


class TestScanQuestionAsStatement:
    def test_flags_genuine_question_punctuated_as_statement(self, tmp_path: Path) -> None:
        book = _write_book(tmp_path, {"01-open": '"What are you doing here." he said.\n'})
        findings = _scan_question_as_statement(book)
        assert len(findings) == 1
        assert findings[0].count == 1

    def test_multi_sentence_dialogue_does_not_flag_correctly_punctuated_question(
        self, tmp_path: Path
    ) -> None:
        """Issue #611, evidence case 1: a single quoted dialogue span can
        contain more than one sentence. The interrogative sentence here
        already ends in '?' — only a later, unrelated declarative
        fragment ends in '.'. The whole-span first-token/last-char check
        used to flag this as a Q-word-ending-in-period violation even
        though the actual question is correctly punctuated."""
        book = _write_book(
            tmp_path,
            {
                "01-open": (
                    '"When was the last time you did something outside? '
                    'Actual outside." she asked.\n'
                )
            },
        )
        findings = _scan_question_as_statement(book)
        assert findings == []

    def test_free_relative_clause_not_flagged(self, tmp_path: Path) -> None:
        """Code review H-3: splitting a multi-sentence dialogue span into
        per-sentence checks (#611) made every non-initial sentence a
        candidate, which surfaces free relative / subordinate clauses
        opening on a wh-word ("What he does next is his problem.") as
        false positives — these are declarative, not questions, since
        there's no subject-aux inversion after the wh-word."""
        book = _write_book(
            tmp_path,
            {
                "01-open": (
                    '"I told him no. What he does next is his problem." she said.\n'
                    '"It went badly. How it ended is nobody\'s business." he muttered.\n'
                    '"Fine. Whatever you say. What a mess this is." she snapped.\n'
                )
            },
        )
        findings = _scan_question_as_statement(book)
        assert findings == []

    def test_multi_sentence_dialogue_still_flags_its_own_bad_sentence(self, tmp_path: Path) -> None:
        """A genuinely mis-punctuated question inside a multi-sentence
        quote must still be caught once sentences are split."""
        book = _write_book(
            tmp_path,
            {
                "01-open": (
                    '"I already told you that. What is wrong with you." he snapped.\n'
                )
            },
        )
        findings = _scan_question_as_statement(book)
        assert len(findings) == 1


class TestScanSentenceRepetitions:
    def test_duplicated_sentence_collapses_to_one_finding(self, tmp_path: Path) -> None:
        """Issue #613: a single verbatim-duplicated sentence must not
        explode into one finding per overlapping n-gram window/length —
        only the longest/most-specific window per duplicate cluster
        should survive."""
        sentence = (
            "you're a grown man with a job and a dead plant and a lot of "
            "information about dns caches"
        )
        book = _write_book(
            tmp_path,
            {
                "01-open": f"Marcus said {sentence} once more.\n",
                "02-later": f"Sarah remembered {sentence} from before.\n",
            },
        )
        findings = _scan_sentence_repetitions(book, min_length=8, max_length=15, min_occurrences=2)
        # Every finding must share the exact same 2 occurrence locations —
        # if collapsing worked, there is exactly one of them.
        location_sets = {frozenset((o.chapter, o.line) for o in f.occurrences) for f in findings}
        assert len(findings) == 1
        assert len(location_sets) == 1

    def test_two_independent_duplicates_both_survive(self, tmp_path: Path) -> None:
        """Collapsing must be scoped to overlapping windows of the *same*
        duplicate — two unrelated repeated sentences (each its own
        paragraph, so their occurrence sites never coincide) must both
        still be reported."""
        sentence_a = "the long cold hallway smelled like rain and old paper today"
        sentence_b = "nobody wanted to admit how much the silence actually hurt"
        book = _write_book(
            tmp_path,
            {
                "01-open": f"{sentence_a}.\n\n{sentence_b}.\n",
                "02-later": f"{sentence_a}.\n\n{sentence_b}.\n",
            },
        )
        findings = _scan_sentence_repetitions(book, min_length=8, max_length=15, min_occurrences=2)
        location_sets = {frozenset((o.chapter, o.line) for o in f.occurrences) for f in findings}
        assert len(location_sets) == 2
