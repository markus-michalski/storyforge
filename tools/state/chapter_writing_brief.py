"""Chapter-writing brief assembler — Issue #78 (Sprint 2 keystone).

Replaces the 16 prose prereq-loads in ``chapter-writer`` with a single
structured JSON brief. The brief gathers data from every Sprint 1/2
sub-tool (story anchor, recent timelines, banlist, tactical setup,
POV knowledge boundary) plus the older book-context sources (book
CLAUDE.md rules + callbacks, tone litmus questions, character
profiles) into one deterministic payload.

Design principles:

* Each sub-component is wrapped in try/except. A single failure
  records itself in the ``errors`` list and the brief still ships.
* Output is plain dicts/lists/strings — JSON-serializable without
  custom encoders.
* No I/O outside the book root and the plugin root. Skill prompts
  consume the brief directly; nothing in the brief points back at
  on-disk paths the writer would need to re-resolve.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from tools.analysis.pov_boundary_checker import parse_character_knowledge
from tools.analysis.tactical_checker import (
    is_tactical_scene,
    load_tactical_profiles,
    analyze_tactical_setup,
)
from tools.shared.paths import slugify
from tools.state.chapter_timeline_parser import get_recent_chapter_timelines
from tools.state.parsers import parse_chapter_readme, parse_frontmatter
from tools.timeline_anchor import get_story_anchor


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


@dataclass
class _Recorder:
    """Collects sub-tool errors so the brief can ship with partial data."""

    errors: list[dict[str, str]]

    def run(self, component: str, fn, default):
        try:
            return fn()
        except Exception as exc:  # pylint: disable=broad-except
            self.errors.append({
                "component": component,
                "error": f"{type(exc).__name__}: {exc}",
            })
            return default


# Fallback parser for Blood & Binary-style Overview tables. Older
# chapter READMEs encode metadata in a markdown table under
# ``## Overview`` instead of YAML frontmatter. Honor both.
_OVERVIEW_CELL_RE = re.compile(
    r"^\|\s*(?P<key>[A-Za-z][A-Za-z ]+?)\s*\|\s*(?P<value>[^|]+?)\s*\|\s*$",
    re.MULTILINE,
)


def _parse_overview_table(readme_text: str) -> dict[str, str]:
    """Pull key/value pairs from a chapter README's ``## Overview`` table.

    Returns an empty dict when the table is absent. Header rows (the
    ``Field/Value`` and the dashes line) are filtered out by the
    caller's key whitelist.
    """
    cells: dict[str, str] = {}
    for match in _OVERVIEW_CELL_RE.finditer(readme_text):
        key = match.group("key").strip().lower()
        value = match.group("value").strip()
        if not value or value.startswith("-"):
            continue
        cells[key] = value
    return cells


_RULES_SECTION_RE = re.compile(
    r"^##\s+Rules\s*$(.*?)^##\s+",
    re.MULTILINE | re.DOTALL,
)
_CALLBACKS_SECTION_RE = re.compile(
    r"^##\s+Callback Register\s*$(.*?)(?=^---\s*$|\Z)",
    re.MULTILINE | re.DOTALL,
)
_LITMUS_SECTION_RE = re.compile(
    r"^##\s+Litmus Test\s*$(.*?)(?=^##\s+|\Z)",
    re.MULTILINE | re.DOTALL,
)
_BULLET_RE = re.compile(r"^\s*[-*]\s+(?P<body>.+?)\s*$", re.MULTILINE)
_NUMBERED_RE = re.compile(r"^\s*\d+[.)]\s+(?P<body>.+?)\s*$", re.MULTILINE)
_COMMENT_RE = re.compile(r"<!--.*?-->", re.DOTALL)


def _section_bullets(text: str, regex: re.Pattern[str]) -> list[str]:
    match = regex.search(text)
    if not match:
        return []
    body = _COMMENT_RE.sub("", match.group(1))
    items: list[str] = []
    for m in _BULLET_RE.finditer(body):
        item = re.sub(r"\s+", " ", m.group("body")).strip()
        if item:
            items.append(item)
    return items


def _litmus_questions(text: str) -> list[str]:
    """Litmus tests are typically numbered, sometimes bulleted."""
    match = _LITMUS_SECTION_RE.search(text)
    if not match:
        return []
    body = match.group(1)
    items: list[str] = []
    for regex in (_NUMBERED_RE, _BULLET_RE):
        for m in regex.finditer(body):
            item = re.sub(r"\s+", " ", m.group("body")).strip()
            if item and item not in items:
                items.append(item)
    return items


# ---------------------------------------------------------------------------
# Rule severity classifier
# ---------------------------------------------------------------------------

# Same heuristic as the hook: a rule that looks like a banned-phrase
# declaration is block-severity, everything else is advisory.
_BAN_CUE_RE = re.compile(
    r"\b(banned|ban|avoid|never|don[’']?t\s+use|do\s+not\s+use|"
    r"limit|stop\s+using)\b",
    re.IGNORECASE,
)


def _classify_rule(rule: str) -> str:
    if "`" in rule and _BAN_CUE_RE.search(rule):
        return "block"
    return "advisory"


# ---------------------------------------------------------------------------
# Simile counter (regex-only — same heuristic as manuscript-checker)
# ---------------------------------------------------------------------------

_SIMILE_RE = re.compile(
    r"\b(?:like\s+a|like\s+the|as\s+if|as\s+though|"
    r"as\s+\w+\s+as)\b",
    re.IGNORECASE,
)


def _count_similes(draft_path: Path) -> int:
    if not draft_path.is_file():
        return 0
    try:
        text = draft_path.read_text(encoding="utf-8")
    except OSError:
        return 0
    # Strip frontmatter to avoid counting metadata.
    _, body = parse_frontmatter(text)
    return len(_SIMILE_RE.findall(body))


# ---------------------------------------------------------------------------
# Last-paragraph extractor for recent_chapter_endings
# ---------------------------------------------------------------------------


def _last_paragraph(draft_path: Path) -> str:
    if not draft_path.is_file():
        return ""
    try:
        text = draft_path.read_text(encoding="utf-8")
    except OSError:
        return ""
    _, body = parse_frontmatter(text)
    paragraphs = [p.strip() for p in re.split(r"\n\s*\n", body) if p.strip()]
    if not paragraphs:
        return ""
    last = paragraphs[-1]
    # Cap to a reasonable preview size; the writer only needs the
    # closing beat, not the whole paragraph.
    if len(last) > 600:
        last = last[:600].rstrip() + " ..."
    return last


# ---------------------------------------------------------------------------
# Character roster derivation
# ---------------------------------------------------------------------------


def _scan_for_named_characters(text: str, characters_dir: Path) -> list[str]:
    """Find character slugs whose ``name:`` appears in the chapter outline.

    Lightweight heuristic — reads each character's frontmatter ``name``
    and checks for substring presence in the outline text. Avoids
    pulling in characters that aren't in this chapter.
    """
    if not characters_dir.is_dir():
        return []
    found: list[str] = []
    for path in sorted(characters_dir.iterdir()):
        if path.suffix.lower() != ".md" or path.name.upper() == "INDEX.MD":
            continue
        try:
            char_text = path.read_text(encoding="utf-8")
        except OSError:
            continue
        meta, _body = parse_frontmatter(char_text)
        name = str(meta.get("name", path.stem))
        if name and name in text:
            found.append(path.stem)
    return found


def _character_payload(path: Path) -> dict[str, Any]:
    """Full character payload: frontmatter + knowledge + tactical (if present)."""
    text = path.read_text(encoding="utf-8")
    meta, _body = parse_frontmatter(text)
    payload: dict[str, Any] = {
        "slug": path.stem,
        "name": str(meta.get("name", path.stem)),
        "role": str(meta.get("role", "supporting")),
        "description": str(meta.get("description", "")),
    }
    knowledge = parse_character_knowledge(path)
    if knowledge is not None and knowledge.has_knowledge_data:
        payload["knowledge"] = {
            "expert": list(knowledge.expert),
            "competent": list(knowledge.competent),
            "layperson": list(knowledge.layperson),
            "none": list(knowledge.none),
        }
    tactical = meta.get("tactical")
    if isinstance(tactical, dict) and tactical:
        payload["tactical"] = tactical
    return payload


# ---------------------------------------------------------------------------
# Public assembler
# ---------------------------------------------------------------------------


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

    # ----- chapter metadata -------------------------------------------------
    chapter_meta: dict[str, Any] = {}
    if chapter_readme.is_file():
        chapter_meta = recorder.run(
            "chapter",
            lambda: parse_chapter_readme(chapter_readme),
            {},
        )
    else:
        recorder.errors.append({
            "component": "chapter",
            "error": f"chapter README missing: {chapter_readme}",
        })

    pov_character = str(chapter_meta.get("pov_character", "")).strip()

    # Fallback for older Blood & Binary chapters whose POV / title
    # live in a markdown ``## Overview`` table rather than YAML
    # frontmatter. Only consulted when the frontmatter path was empty.
    overview: dict[str, str] = {}
    title_from_meta = str(chapter_meta.get("title", "")).strip()
    title_is_default = title_from_meta == chapter_slug
    if chapter_readme.is_file():
        try:
            overview = _parse_overview_table(
                chapter_readme.read_text(encoding="utf-8")
            )
        except OSError:
            overview = {}
        if not pov_character:
            pov_character = overview.get("pov", "").strip()
        if (not title_from_meta or title_is_default) and overview.get("title"):
            chapter_meta["title"] = overview["title"]
        if not chapter_meta.get("number") and overview.get("chapter"):
            try:
                chapter_meta["number"] = int(re.sub(r"\D", "", overview["chapter"]) or 0)
            except ValueError:
                pass

    # ----- characters present ---------------------------------------------
    characters: list[dict[str, Any]] = []
    chars_dir = book_root / "characters"
    pov_added = False

    if pov_character:
        pov_slug = slugify(pov_character)
        pov_path = chars_dir / f"{pov_slug}.md"
        if pov_path.is_file():
            payload = recorder.run(
                "characters.pov",
                lambda: _character_payload(pov_path),
                None,
            )
            if payload:
                characters.append(payload)
                pov_added = True

    # Best-effort: surface any other named characters appearing in the
    # chapter outline / summary (chapter README body).
    outline_text = ""
    if chapter_readme.is_file():
        try:
            outline_text = chapter_readme.read_text(encoding="utf-8")
        except OSError:
            outline_text = ""

    other_slugs = recorder.run(
        "characters.scan",
        lambda: _scan_for_named_characters(outline_text, chars_dir),
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
            lambda p=path: _character_payload(p),
            None,
        )
        if payload:
            characters.append(payload)

    # ----- story anchor ---------------------------------------------------
    story_anchor = recorder.run(
        "story_anchor",
        lambda: get_story_anchor(book_root, chapter_slug).to_dict(),
        None,
    )

    # ----- recent chapter timelines ---------------------------------------
    recent_timelines = recorder.run(
        "recent_chapter_timelines",
        lambda: [g.to_dict() for g in get_recent_chapter_timelines(book_root, n=3)],
        [],
    )

    # ----- recent chapter endings + simile counts -------------------------
    recent_endings: list[dict[str, Any]] = []
    simile_counts: dict[str, int] = {}
    chapters_dir = book_root / "chapters"
    if chapters_dir.is_dir():
        all_chapters: list[tuple[int, Path]] = []
        current_number: int | None = None
        for entry in chapters_dir.iterdir():
            if not entry.is_dir():
                continue
            m = re.match(r"^(\d{1,3})-", entry.name)
            if not m:
                continue
            num = int(m.group(1))
            all_chapters.append((num, entry))
            if entry.name == chapter_slug:
                current_number = num
        all_chapters.sort()
        # Last 3 chapters strictly before the current one (chronologically).
        if current_number is not None:
            prior = [ch for num, ch in all_chapters if num < current_number][-3:]
        else:
            # New chapter not yet on disk — take the last 3 we have.
            prior = [ch for _, ch in all_chapters][-3:]
        for ch in prior:
            draft = ch / "draft.md"
            if not draft.is_file():
                continue
            ending = recorder.run(
                f"endings.{ch.name}",
                lambda d=draft: _last_paragraph(d),
                "",
            )
            if ending:
                recent_endings.append({
                    "chapter": ch.name,
                    "last_paragraph": ending,
                })
            count = recorder.run(
                f"similes.{ch.name}",
                lambda d=draft: _count_similes(d),
                0,
            )
            simile_counts[ch.name] = count

    # ----- rules + callbacks from book CLAUDE.md --------------------------
    rules_to_honor: list[dict[str, str]] = []
    callbacks_in_register: list[str] = []
    claudemd_path = book_root / "CLAUDE.md"
    if claudemd_path.is_file():
        claudemd_text = recorder.run(
            "claudemd.read",
            lambda: claudemd_path.read_text(encoding="utf-8"),
            "",
        )
        if claudemd_text:
            for rule_text in _section_bullets(claudemd_text, _RULES_SECTION_RE):
                rules_to_honor.append({
                    "text": rule_text,
                    "severity": _classify_rule(rule_text),
                })
            callbacks_in_register = _section_bullets(
                claudemd_text, _CALLBACKS_SECTION_RE,
            )

    # ----- banned phrases -------------------------------------------------
    banned_phrases: list[dict[str, str]] = []
    banned_phrases = recorder.run(
        "banned_phrases",
        lambda: _collect_banned_phrases(book_root, plugin_root),
        [],
    )

    # ----- tone litmus questions ------------------------------------------
    tone_questions: list[str] = []
    tone_path = book_root / "plot" / "tone.md"
    if tone_path.is_file():
        tone_text = recorder.run(
            "tone.read",
            lambda: tone_path.read_text(encoding="utf-8"),
            "",
        )
        if tone_text:
            tone_questions = _litmus_questions(tone_text)

    # ----- tactical constraints (only if outline triggers detection) ------
    tactical: dict[str, Any] | None = None
    if outline_text and is_tactical_scene(outline_text):
        present_slugs = [c["slug"] for c in characters]
        if present_slugs:
            profiles = recorder.run(
                "tactical.load_profiles",
                lambda: load_tactical_profiles(book_root, present_slugs),
                [],
            )
            tactical = recorder.run(
                "tactical.analyze",
                lambda: analyze_tactical_setup(outline_text, profiles).to_dict(),
                None,
            )

    return {
        "book_slug": book_slug,
        "chapter_slug": chapter_slug,
        "chapter": _serialize_chapter_meta(chapter_meta),
        "pov_character": pov_character,
        "story_anchor": story_anchor,
        "recent_chapter_timelines": recent_timelines,
        "recent_chapter_endings": recent_endings,
        "characters_present": characters,
        "rules_to_honor": rules_to_honor,
        "callbacks_in_register": callbacks_in_register,
        "banned_phrases": banned_phrases,
        "recent_simile_count_per_chapter": simile_counts,
        "tone_litmus_questions": tone_questions,
        "tactical_constraints": tactical,
        "review_handle": review_handle,
        "errors": list(recorder.errors),
    }


def _serialize_chapter_meta(meta: dict[str, Any]) -> dict[str, Any]:
    """Trim chapter meta to JSON-safe keys."""
    if not meta:
        return {}
    out: dict[str, Any] = {}
    for key in ("slug", "title", "number", "status", "pov_character",
                "summary", "word_count_target"):
        if key in meta:
            value = meta[key]
            if isinstance(value, (str, int, float, bool)) or value is None:
                out[key] = value
            else:
                out[key] = str(value)
    return out


def _collect_banned_phrases(
    book_root: Path, plugin_root: Path,
) -> list[dict[str, str]]:
    """Surface a deduplicated banned-phrase summary for the brief.

    Pulls from three sources, in order: book CLAUDE.md ## Rules with
    backticked phrases (block-severity), author vocabulary.md
    (block-severity), and the global anti-AI tells (warn-severity).
    Returns up to ~50 entries — anything past that is noise the writer
    won't read.
    """
    from tools.analysis.manuscript_checker import (
        _read_book_rules, _extract_patterns_from_rule,
    )
    from tools.banlist_loader import (
        author_slug_from_book, load_author_vocab, load_global_ai_tells,
    )

    seen: set[str] = set()
    out: list[dict[str, str]] = []

    for rule in _read_book_rules(book_root):
        for label, _pattern in _extract_patterns_from_rule(rule):
            key = label.lower()
            if key in seen:
                continue
            seen.add(key)
            out.append({
                "phrase": label,
                "source": "book CLAUDE.md ## Rules",
                "severity": "block",
            })

    author_slug = author_slug_from_book(book_root)
    if author_slug:
        # load_author_vocab takes home-dir override so tests can
        # patch it; in production it reads ~/.storyforge/...
        try:
            patterns = load_author_vocab(author_slug)
        except Exception:  # pylint: disable=broad-except
            patterns = []
        for p in patterns:
            key = p.label.lower()
            if key in seen:
                continue
            seen.add(key)
            out.append({
                "phrase": p.label,
                "source": "author vocabulary.md",
                "severity": p.severity,
            })

    try:
        global_tells = load_global_ai_tells(plugin_root)
    except Exception:  # pylint: disable=broad-except
        global_tells = []
    for p in global_tells:
        key = p.label.lower()
        if key in seen:
            continue
        seen.add(key)
        out.append({
            "phrase": p.label,
            "source": "anti-ai-patterns.md",
            "severity": p.severity,
        })
        if len(out) >= 50:
            break
    return out
