"""Chapter-writing brief assembler — orchestrator (Issue #78, refactored #121).

Replaces the 16 prose prereq-loads in ``chapter-writer`` with a single
structured JSON brief. The brief gathers data from every Sprint 1/2
sub-tool (story anchor, recent timelines, banlist, tactical setup,
POV knowledge boundary) plus the older book-context sources (book
CLAUDE.md rules + callbacks, tone litmus questions, character
profiles) into one deterministic payload.

This file is a thin orchestrator (#121). Each sub-source lives in its
own loader under ``tools/state/loaders/`` and is independently
testable. The orchestrator wraps every loader call in a recorder so a
single failure records itself in ``errors`` and the brief still ships
with partial data.

Output is plain dicts/lists/strings — JSON-serializable without
custom encoders.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from tools.analysis.tactical_checker import (
    is_tactical_scene,
    load_tactical_profiles,
    analyze_tactical_setup,
)
from tools.shared.paths import resolve_people_dir, slugify
from tools.state.chapter_timeline_parser import get_recent_chapter_timelines
from tools.state.loaders.banlist import collect_banned_phrases
from tools.state.loaders.chapter_meta import (
    load_book_category,
    load_chapter_meta,
    serialize_chapter_meta,
)
from tools.state.loaders.claudemd_sections import (
    callback_register_bullets,
    classify_rule,
    litmus_questions,
    rule_bullets,
)
from tools.state.loaders.people import (
    character_payload,
    consent_status_warnings,
    person_payload,
    scan_for_named_characters,
)
from tools.state.loaders.canon_brief import build_canon_brief
from tools.state.loaders.pov_inventory import extract_pov_inventory
from tools.state.loaders.pov_state import extract_pov_state
from tools.state.loaders.recent_chapters import (
    collect_recent_chapters,
    count_similes,
    last_paragraph,
)
from tools.timeline_anchor import get_story_anchor


@dataclass
class _Recorder:
    """Collects sub-loader errors so the brief can ship with partial data."""

    errors: list[dict[str, str]]

    def run(self, component: str, fn, default):
        try:
            return fn()
        except Exception as exc:  # pylint: disable=broad-except
            self.errors.append(
                {
                    "component": component,
                    "error": f"{type(exc).__name__}: {exc}",
                }
            )
            return default


def _gather_characters(
    book_root: Path,
    chapter_readme: Path,
    pov_character: str,
    *,
    is_memoir: bool,
    recorder: _Recorder,
) -> list[dict[str, Any]]:
    """POV first, then any other named characters mentioned in the outline."""
    chars_dir = resolve_people_dir(book_root, "memoir") if is_memoir else book_root / "characters"
    payload_loader = person_payload if is_memoir else character_payload
    characters: list[dict[str, Any]] = []
    pov_added = False

    if pov_character:
        pov_slug = slugify(pov_character)
        pov_path = chars_dir / f"{pov_slug}.md"
        if pov_path.is_file():
            payload = recorder.run(
                "characters.pov",
                lambda: payload_loader(pov_path),
                None,
            )
            if payload:
                characters.append(payload)
                pov_added = True

    outline_text = ""
    if chapter_readme.is_file():
        try:
            outline_text = chapter_readme.read_text(encoding="utf-8")
        except OSError:
            outline_text = ""

    other_slugs = recorder.run(
        "characters.scan",
        lambda: scan_for_named_characters(outline_text, chars_dir),
        [],
    )
    for slug in other_slugs:
        if pov_added and slug == slugify(pov_character):
            continue
        path = chars_dir / f"{slug}.md"
        if not path.is_file():
            continue
        payload = recorder.run(
            f"characters.{slug}",
            lambda p=path: payload_loader(p),
            None,
        )
        if payload:
            characters.append(payload)
    return characters


def _gather_recent(
    book_root: Path,
    chapter_slug: str,
    *,
    recorder: _Recorder,
) -> tuple[list[dict[str, Any]], dict[str, int]]:
    """Last-paragraph + simile-count for the three chapters before this one."""
    recent_endings: list[dict[str, Any]] = []
    simile_counts: dict[str, int] = {}
    chapters_dir = book_root / "chapters"
    for ch in collect_recent_chapters(chapters_dir, chapter_slug, n=3):
        draft = ch / "draft.md"
        if not draft.is_file():
            continue
        ending = recorder.run(
            f"endings.{ch.name}",
            lambda d=draft: last_paragraph(d),
            "",
        )
        if ending:
            recent_endings.append(
                {
                    "chapter": ch.name,
                    "last_paragraph": ending,
                }
            )
        count = recorder.run(
            f"similes.{ch.name}",
            lambda d=draft: count_similes(d),
            0,
        )
        simile_counts[ch.name] = count
    return recent_endings, simile_counts


def _gather_claudemd(
    book_root: Path,
    *,
    recorder: _Recorder,
) -> tuple[list[dict[str, str]], list[str]]:
    """Rules (with severity) and callbacks from the book CLAUDE.md."""
    rules_to_honor: list[dict[str, str]] = []
    callbacks_in_register: list[str] = []
    claudemd_path = book_root / "CLAUDE.md"
    if not claudemd_path.is_file():
        return rules_to_honor, callbacks_in_register

    claudemd_text = recorder.run(
        "claudemd.read",
        lambda: claudemd_path.read_text(encoding="utf-8"),
        "",
    )
    if not claudemd_text:
        return rules_to_honor, callbacks_in_register

    for rule_text in rule_bullets(claudemd_text):
        rules_to_honor.append(
            {
                "text": rule_text,
                "severity": classify_rule(rule_text),
            }
        )
    callbacks_in_register = callback_register_bullets(claudemd_text)
    return rules_to_honor, callbacks_in_register


def _gather_tone(
    book_root: Path,
    *,
    recorder: _Recorder,
) -> list[str]:
    tone_path = book_root / "plot" / "tone.md"
    if not tone_path.is_file():
        return []
    tone_text = recorder.run(
        "tone.read",
        lambda: tone_path.read_text(encoding="utf-8"),
        "",
    )
    return litmus_questions(tone_text) if tone_text else []


def _gather_tactical(
    book_root: Path,
    outline_text: str,
    characters: list[dict[str, Any]],
    *,
    recorder: _Recorder,
) -> dict[str, Any] | None:
    if not outline_text or not is_tactical_scene(outline_text):
        return None
    present_slugs = [c["slug"] for c in characters]
    if not present_slugs:
        return None
    profiles = recorder.run(
        "tactical.load_profiles",
        lambda: load_tactical_profiles(book_root, present_slugs),
        [],
    )
    return recorder.run(
        "tactical.analyze",
        lambda: analyze_tactical_setup(outline_text, profiles).to_dict(),
        None,
    )


def build_chapter_writing_brief(
    *,
    book_root: Path,
    book_slug: str,
    chapter_slug: str,
    plugin_root: Path,
    review_handle: str = "Markus",
) -> dict[str, Any]:
    """Assemble the chapter-writing brief.

    The brief is a single dict that ``chapter-writer`` can consume in
    one tool call instead of running 16 separate prereq-loads.
    """
    recorder = _Recorder(errors=[])
    chapter_dir = book_root / "chapters" / chapter_slug
    chapter_readme = chapter_dir / "README.md"

    chapter_meta, pov_character, _overview = recorder.run(
        "chapter",
        lambda: load_chapter_meta(chapter_readme, chapter_slug),
        ({}, "", {}),
    )
    if not chapter_readme.is_file():
        recorder.errors.append(
            {
                "component": "chapter",
                "error": f"chapter README missing: {chapter_readme}",
            }
        )

    book_category = recorder.run(
        "book.read",
        lambda: load_book_category(book_root),
        "fiction",
    )
    is_memoir = book_category == "memoir"

    characters = _gather_characters(
        book_root,
        chapter_readme,
        pov_character,
        is_memoir=is_memoir,
        recorder=recorder,
    )

    consent_warnings: list[dict[str, str]] = []
    if is_memoir:
        consent_warnings = recorder.run(
            "consent_status_warnings",
            lambda: consent_status_warnings(characters),
            [],
        )

    chars_dir = resolve_people_dir(book_root, "memoir") if is_memoir else book_root / "characters"
    pov_character_inventory = recorder.run(
        "pov_character_inventory",
        lambda: extract_pov_inventory(
            book_root,
            pov_character,
            chapter_slug,
            chars_dir=chars_dir,
        ),
        {
            "items": [],
            "as_of": None,
            "extraction_method": "none",
            "warnings": ["pov_character_inventory loader failed — see errors"],
        },
    )

    story_anchor = recorder.run(
        "story_anchor",
        lambda: get_story_anchor(book_root, chapter_slug).to_dict(),
        None,
    )

    recent_timelines = recorder.run(
        "recent_chapter_timelines",
        lambda: [g.to_dict() for g in get_recent_chapter_timelines(book_root, n=3)],
        [],
    )

    recent_endings, simile_counts = _gather_recent(
        book_root,
        chapter_slug,
        recorder=recorder,
    )

    rules_to_honor, callbacks_in_register = _gather_claudemd(
        book_root,
        recorder=recorder,
    )

    banned_phrases = recorder.run(
        "banned_phrases",
        lambda: collect_banned_phrases(book_root, plugin_root),
        [],
    )

    tone_questions = _gather_tone(book_root, recorder=recorder)

    outline_text = ""
    if chapter_readme.is_file():
        try:
            outline_text = chapter_readme.read_text(encoding="utf-8")
        except OSError:
            outline_text = ""

    pov_character_state = recorder.run(
        "pov_character_state",
        lambda: extract_pov_state(
            book_root,
            pov_character,
            chapter_slug,
            chars_dir=chars_dir,
            outline_text=outline_text,
        ),
        {
            "clothing": [],
            "injuries": [],
            "altered_states": [],
            "environmental_limiters": [],
            "as_of": None,
            "extraction_methods": {
                "clothing": "none",
                "injuries": "none",
                "altered_states": "none",
                "environmental_limiters": "none",
            },
            "warnings": ["pov_character_state loader failed — see errors"],
        },
    )

    canon_brief = recorder.run(
        "canon_brief",
        lambda: build_canon_brief(
            book_root,
            chapter_slug,
            pov_character,
            book_category=book_category,
        ),
        {
            "current_facts": [],
            "changed_facts": [],
            "pov_relevant_facts": [],
            "scanned_chapters": [],
            "as_of": None,
            "extraction_method": "none",
            "warnings": ["canon_brief loader failed — see errors"],
        },
    )

    tactical = _gather_tactical(
        book_root,
        outline_text,
        characters,
        recorder=recorder,
    )

    return {
        "book_slug": book_slug,
        "book_category": book_category,
        "chapter_slug": chapter_slug,
        "chapter": serialize_chapter_meta(chapter_meta),
        "pov_character": pov_character,
        "story_anchor": story_anchor,
        "recent_chapter_timelines": recent_timelines,
        "recent_chapter_endings": recent_endings,
        "characters_present": characters,
        "pov_character_inventory": pov_character_inventory,
        "pov_character_state": pov_character_state,
        "canon_brief": canon_brief,
        "consent_status_warnings": consent_warnings,
        "rules_to_honor": rules_to_honor,
        "callbacks_in_register": callbacks_in_register,
        "banned_phrases": banned_phrases,
        "recent_simile_count_per_chapter": simile_counts,
        "tone_litmus_questions": tone_questions,
        "tactical_constraints": tactical,
        "review_handle": review_handle,
        "errors": list(recorder.errors),
    }


__all__ = ["build_chapter_writing_brief"]
