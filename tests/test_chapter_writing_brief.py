"""Tests for ``tools.state.chapter_writing_brief`` — Issue #78.

Architectural keystone for Sprint 2: assembles a single structured
JSON brief from all the prereq-data sources that ``chapter-writer``
used to load by hand. Replaces 16 prose prereq-loads with one tool
call.
"""

from __future__ import annotations

import json
from pathlib import Path

from tools.state.chapter_writing_brief import build_chapter_writing_brief


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _setup_book(tmp_path: Path) -> tuple[Path, Path]:
    """Create a minimal book scaffold and return (book_root, plugin_root).

    plugin_root points to the real storyforge repo so reference/craft
    files (knowledge-domains, anti-ai-patterns) resolve naturally.
    """
    book = tmp_path / "test-book"
    (book / "chapters").mkdir(parents=True)
    (book / "characters").mkdir()
    (book / "plot").mkdir()
    (book / "world").mkdir()
    (book / "README.md").write_text(
        '---\ntitle: "Test Book"\nauthor: ""\n---\n\n# Test Book\n',
        encoding="utf-8",
    )
    return book, Path(__file__).resolve().parent.parent


def _make_chapter(
    book: Path,
    slug: str,
    *,
    number: int,
    title: str,
    status: str = "Draft",
    pov: str = "",
    body: str = "",
) -> Path:
    chapter = book / "chapters" / slug
    chapter.mkdir(parents=True)
    pov_line = f'pov_character: "{pov}"\n' if pov else ""
    readme = (
        "---\n"
        f'title: "{title}"\n'
        f"number: {number}\n"
        f'status: "{status}"\n'
        f"{pov_line}"
        "---\n\n"
        "# " + title + "\n\n"
        + body
    )
    (chapter / "README.md").write_text(readme, encoding="utf-8")
    return chapter


def _add_character(
    book: Path,
    slug: str,
    *,
    name: str,
    role: str = "protagonist",
    knowledge: dict | None = None,
) -> Path:
    body = "---\n" f'name: "{name}"\n' f'role: "{role}"\n'
    if knowledge:
        body += "knowledge:\n"
        for tier, terms in knowledge.items():
            body += f"  {tier}: {terms}\n"
    body += "---\n\n# " + name + "\n"
    path = book / "characters" / f"{slug}.md"
    path.write_text(body, encoding="utf-8")
    return path


def _add_claudemd(
    book: Path, *, rules: list[str] | None = None, callbacks: list[str] | None = None,
) -> Path:
    rules_block = "\n".join(f"- {r}" for r in (rules or []))
    callbacks_block = "\n".join(f"- {c}" for c in (callbacks or []))
    body = (
        "# Test Book\n\n"
        "## Rules\n\n"
        "<!-- RULES:START -->\n"
        f"{rules_block}\n"
        "<!-- RULES:END -->\n\n"
        "## Callback Register\n\n"
        "<!-- CALLBACKS:START -->\n"
        f"{callbacks_block}\n"
        "<!-- CALLBACKS:END -->\n"
    )
    path = book / "CLAUDE.md"
    path.write_text(body, encoding="utf-8")
    return path


# ---------------------------------------------------------------------------
# Minimal happy-path: fully populated book
# ---------------------------------------------------------------------------


class TestBriefAssemblyMinimal:
    def test_returns_dict_with_top_level_keys(self, tmp_path):
        book, plugin_root = _setup_book(tmp_path)
        _make_chapter(book, "01-intro", number=1, title="Intro", pov="Theo")
        _add_character(book, "theo", name="Theo")

        brief = build_chapter_writing_brief(
            book_root=book, book_slug="test-book",
            chapter_slug="01-intro", plugin_root=plugin_root,
        )

        assert isinstance(brief, dict)
        for key in (
            "book_slug", "chapter_slug", "chapter", "pov_character",
            "story_anchor", "recent_chapter_timelines",
            "recent_chapter_endings", "characters_present",
            "rules_to_honor", "callbacks_in_register",
            "banned_phrases", "recent_simile_count_per_chapter",
            "tone_litmus_questions", "review_handle",
            "tactical_constraints", "errors",
        ):
            assert key in brief, f"missing key: {key}"

    def test_chapter_metadata_populated(self, tmp_path):
        book, plugin_root = _setup_book(tmp_path)
        _make_chapter(
            book, "05-the-bet", number=5, title="The Bet",
            status="Draft", pov="Theo Wilkons",
        )
        _add_character(book, "theo-wilkons", name="Theo Wilkons")

        brief = build_chapter_writing_brief(
            book_root=book, book_slug="test-book",
            chapter_slug="05-the-bet", plugin_root=plugin_root,
        )

        assert brief["chapter"]["number"] == 5
        assert brief["chapter"]["title"] == "The Bet"
        assert brief["pov_character"] == "Theo Wilkons"

    def test_characters_present_includes_pov_profile(self, tmp_path):
        book, plugin_root = _setup_book(tmp_path)
        _make_chapter(
            book, "01-intro", number=1, title="Intro", pov="Theo Wilkons",
        )
        _add_character(
            book, "theo-wilkons", name="Theo Wilkons", role="protagonist",
            knowledge={
                "expert": ["it"], "competent": [], "layperson": [],
                "none": ["forensics"],
            },
        )

        brief = build_chapter_writing_brief(
            book_root=book, book_slug="test-book",
            chapter_slug="01-intro", plugin_root=plugin_root,
        )
        chars = brief["characters_present"]
        assert any(c["slug"] == "theo-wilkons" for c in chars)
        theo = next(c for c in chars if c["slug"] == "theo-wilkons")
        assert theo["name"] == "Theo Wilkons"
        # Knowledge profile is surfaced for POV-boundary awareness.
        assert "knowledge" in theo
        assert "forensics" in theo["knowledge"]["none"]

    def test_rules_and_callbacks_from_claudemd(self, tmp_path):
        book, plugin_root = _setup_book(tmp_path)
        _make_chapter(book, "01-intro", number=1, title="Intro", pov="Theo")
        _add_character(book, "theo", name="Theo")
        _add_claudemd(
            book,
            rules=[
                "Avoid passive voice",
                'Banned phrase: `the kind of X that Y` — max 2 per chapter',
            ],
            callbacks=[
                "Gary the cat — last seen Ch 9, weave back in",
                "Jace's apartment plant — Theo never mentions",
            ],
        )

        brief = build_chapter_writing_brief(
            book_root=book, book_slug="test-book",
            chapter_slug="01-intro", plugin_root=plugin_root,
        )

        rules = brief["rules_to_honor"]
        assert any("passive voice" in r["text"].lower() for r in rules)
        callbacks = brief["callbacks_in_register"]
        assert any("Gary the cat" in c for c in callbacks)

    def test_recent_chapter_endings_extracts_last_paragraph(self, tmp_path):
        book, plugin_root = _setup_book(tmp_path)
        # Three review-status chapters with drafts.
        _make_chapter(book, "01-a", number=1, title="A", status="review", pov="Theo")
        _make_chapter(book, "02-b", number=2, title="B", status="review", pov="Theo")
        _make_chapter(book, "03-c", number=3, title="C", status="review", pov="Theo")
        _make_chapter(book, "04-current", number=4, title="Current", pov="Theo")
        _add_character(book, "theo", name="Theo")

        for slug, last_paragraph in (
            ("01-a", "He closed the door behind him."),
            ("02-b", "The kettle whistled into silence."),
            ("03-c", "She did not look back."),
        ):
            draft = book / "chapters" / slug / "draft.md"
            draft.write_text(
                f"# Chapter\n\nFirst para.\n\nMiddle para.\n\n{last_paragraph}\n",
                encoding="utf-8",
            )

        brief = build_chapter_writing_brief(
            book_root=book, book_slug="test-book",
            chapter_slug="04-current", plugin_root=plugin_root,
        )
        endings = brief["recent_chapter_endings"]
        assert len(endings) == 3
        ending_texts = [e["last_paragraph"] for e in endings]
        assert "He closed the door behind him." in ending_texts
        assert "She did not look back." in ending_texts

    def test_simile_count_extracts_per_chapter(self, tmp_path):
        book, plugin_root = _setup_book(tmp_path)
        _make_chapter(book, "01-a", number=1, title="A", status="review", pov="Theo")
        _make_chapter(book, "02-current", number=2, title="Current", pov="Theo")
        _add_character(book, "theo", name="Theo")

        draft = book / "chapters" / "01-a" / "draft.md"
        draft.write_text(
            "# A\n\n"
            "It rose like a slow tide.\n"
            "He felt as if he were drowning.\n"
            "She was as quiet as a stone.\n"
            "Nothing happened.\n",
            encoding="utf-8",
        )

        brief = build_chapter_writing_brief(
            book_root=book, book_slug="test-book",
            chapter_slug="02-current", plugin_root=plugin_root,
        )
        counts = brief["recent_simile_count_per_chapter"]
        # "like a", "as if", "as ___ as" — three similes detected.
        assert counts.get("01-a") == 3

    def test_tone_litmus_questions_extracted_from_tone_md(self, tmp_path):
        book, plugin_root = _setup_book(tmp_path)
        _make_chapter(book, "01-intro", number=1, title="Intro", pov="Theo")
        _add_character(book, "theo", name="Theo")
        tone = book / "plot" / "tone.md"
        tone.write_text(
            "# Tonal Document\n\n"
            "## Litmus Test\n\n"
            "1. Is the violence consequential?\n"
            "2. Does the humor land in the dialog?\n"
            "3. Is the protagonist actively choosing?\n",
            encoding="utf-8",
        )

        brief = build_chapter_writing_brief(
            book_root=book, book_slug="test-book",
            chapter_slug="01-intro", plugin_root=plugin_root,
        )
        questions = brief["tone_litmus_questions"]
        assert len(questions) == 3
        assert any("violence consequential" in q.lower() for q in questions)


# ---------------------------------------------------------------------------
# Graceful degrade: missing files / sections do not crash the brief
# ---------------------------------------------------------------------------


class TestBriefGracefulDegrade:
    def test_missing_claudemd_returns_empty_rules_and_callbacks(self, tmp_path):
        book, plugin_root = _setup_book(tmp_path)
        _make_chapter(book, "01-intro", number=1, title="Intro", pov="Theo")
        _add_character(book, "theo", name="Theo")

        brief = build_chapter_writing_brief(
            book_root=book, book_slug="test-book",
            chapter_slug="01-intro", plugin_root=plugin_root,
        )
        assert brief["rules_to_honor"] == []
        assert brief["callbacks_in_register"] == []

    def test_missing_tone_md_returns_empty_litmus(self, tmp_path):
        book, plugin_root = _setup_book(tmp_path)
        _make_chapter(book, "01-intro", number=1, title="Intro", pov="Theo")
        _add_character(book, "theo", name="Theo")

        brief = build_chapter_writing_brief(
            book_root=book, book_slug="test-book",
            chapter_slug="01-intro", plugin_root=plugin_root,
        )
        assert brief["tone_litmus_questions"] == []

    def test_no_recent_chapters_returns_empty_endings_and_simile_counts(self, tmp_path):
        book, plugin_root = _setup_book(tmp_path)
        _make_chapter(book, "01-current", number=1, title="Current", pov="Theo")
        _add_character(book, "theo", name="Theo")

        brief = build_chapter_writing_brief(
            book_root=book, book_slug="test-book",
            chapter_slug="01-current", plugin_root=plugin_root,
        )
        assert brief["recent_chapter_endings"] == []
        assert brief["recent_simile_count_per_chapter"] == {}

    def test_missing_pov_character_file_does_not_crash(self, tmp_path):
        book, plugin_root = _setup_book(tmp_path)
        # POV references a character that doesn't exist on disk.
        _make_chapter(book, "01-intro", number=1, title="Intro", pov="Ghost")

        brief = build_chapter_writing_brief(
            book_root=book, book_slug="test-book",
            chapter_slug="01-intro", plugin_root=plugin_root,
        )
        # Brief still returns; the missing-character is captured in errors
        # OR characters_present is just empty for that name.
        assert brief["pov_character"] == "Ghost"
        # No exception should have propagated.

    def test_missing_chapter_returns_error_not_crash(self, tmp_path):
        book, plugin_root = _setup_book(tmp_path)
        # No chapter dir created.
        brief = build_chapter_writing_brief(
            book_root=book, book_slug="test-book",
            chapter_slug="99-ghost", plugin_root=plugin_root,
        )
        # Brief returns with an error rather than raising.
        assert isinstance(brief, dict)
        assert any(
            e["component"] == "chapter" for e in brief["errors"]
        )


# ---------------------------------------------------------------------------
# Determinism + serialization
# ---------------------------------------------------------------------------


class TestBriefDeterminism:
    def test_brief_round_trips_through_json(self, tmp_path):
        book, plugin_root = _setup_book(tmp_path)
        _make_chapter(book, "01-intro", number=1, title="Intro", pov="Theo")
        _add_character(book, "theo", name="Theo")
        _add_claudemd(book, rules=["Be terse"], callbacks=["Gary the cat"])

        brief = build_chapter_writing_brief(
            book_root=book, book_slug="test-book",
            chapter_slug="01-intro", plugin_root=plugin_root,
        )
        # No datetime, Path, or non-JSON values may leak into the brief.
        json.dumps(brief)

    def test_brief_is_deterministic_across_calls(self, tmp_path):
        book, plugin_root = _setup_book(tmp_path)
        _make_chapter(book, "01-intro", number=1, title="Intro", pov="Theo")
        _add_character(book, "theo", name="Theo")
        _add_claudemd(book, rules=["Be terse"], callbacks=["Gary"])

        brief_a = build_chapter_writing_brief(
            book_root=book, book_slug="test-book",
            chapter_slug="01-intro", plugin_root=plugin_root,
        )
        brief_b = build_chapter_writing_brief(
            book_root=book, book_slug="test-book",
            chapter_slug="01-intro", plugin_root=plugin_root,
        )
        # `errors` list ordering must also be stable between calls.
        assert brief_a == brief_b


# ---------------------------------------------------------------------------
# Tactical-constraints field: only populated when scene outline triggers
# combat/travel detection
# ---------------------------------------------------------------------------


class TestTacticalConstraints:
    def test_no_outline_yields_null_tactical_constraints(self, tmp_path):
        book, plugin_root = _setup_book(tmp_path)
        _make_chapter(book, "01-intro", number=1, title="Intro", pov="Theo")
        _add_character(book, "theo", name="Theo")

        brief = build_chapter_writing_brief(
            book_root=book, book_slug="test-book",
            chapter_slug="01-intro", plugin_root=plugin_root,
        )
        assert brief["tactical_constraints"] is None

    def test_combat_outline_populates_tactical_constraints(self, tmp_path):
        book, plugin_root = _setup_book(tmp_path)
        _make_chapter(
            book, "01-fight", number=1, title="Fight", pov="Theo",
            body=(
                "## Outline\n\n"
                "Theo, Kael, and Viktor walk into the warehouse "
                "and attack the team waiting inside.\n"
            ),
        )
        _add_character(book, "theo", name="Theo")

        brief = build_chapter_writing_brief(
            book_root=book, book_slug="test-book",
            chapter_slug="01-fight", plugin_root=plugin_root,
        )
        assert brief["tactical_constraints"] is not None
        assert "questions_for_writer" in brief["tactical_constraints"]
