"""Character / real-people loader for the chapter-writing brief (Issue #121).

Branches by ``book_category``:

- Fiction books read ``characters/{slug}.md`` — full payload includes
  knowledge taxonomy and tactical frontmatter when present.
- Memoir books read ``people/{slug}.md`` — payload includes
  ``person_category``, ``consent_status`` and ``anonymization``;
  ``real_name`` is intentionally excluded so it never enters the brief.

Also surfaces the consent-status warning list for memoir scenes.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from tools.analysis.pov_boundary_checker import parse_character_knowledge
from tools.state.parsers import parse_frontmatter


def character_payload(path: Path) -> dict[str, Any]:
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


def person_payload(path: Path) -> dict[str, Any]:
    """Full real-person payload for memoir mode.

    ``real_name`` is intentionally excluded — it stays private to the
    people file and never enters the writing brief.
    """
    text = path.read_text(encoding="utf-8")
    meta, _body = parse_frontmatter(text)
    return {
        "slug": path.stem,
        "name": str(meta.get("name", path.stem)),
        "relationship": str(meta.get("relationship", "")),
        "person_category": str(meta.get("person_category", "")),
        "consent_status": str(meta.get("consent_status", "")),
        "anonymization": str(meta.get("anonymization", "none")),
        "description": str(meta.get("description", "")),
    }


def scan_for_named_characters(text: str, characters_dir: Path) -> list[str]:
    """Find character/person slugs whose ``name:`` appears in ``text``.

    Lightweight heuristic — reads each character file's frontmatter
    ``name`` and checks for substring presence in the outline text.
    Avoids pulling in characters that aren't in this chapter.
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


def consent_status_warnings(
    people: list[dict[str, Any]],
) -> list[dict[str, str]]:
    """Surface consent issues for memoir scenes (Path E #57).

    Three warning tiers:
      - ``missing`` — no consent_status set; user must decide before drafting
      - ``pending`` — consent intended but not yet asked; flag if scene
        is sensitive
      - ``refused`` — consent was refused; the person should be cut,
        anonymized, or re-framed before this scene drafts

    Confirmed-consent / not-required / not-asking statuses produce no
    warning. An empty list means the chapter passes the consent gate.
    """
    warnings: list[dict[str, str]] = []
    for person in people:
        status = str(person.get("consent_status", "")).strip()
        if not status:
            warnings.append({
                "person": person.get("name", person.get("slug", "")),
                "tier": "missing",
                "message": (
                    "consent_status is unset — decide before drafting any "
                    "scene with this person on the page."
                ),
            })
        elif status == "pending":
            warnings.append({
                "person": person.get("name", person.get("slug", "")),
                "tier": "pending",
                "message": (
                    "consent_status is pending — drafting is allowed, "
                    "but the request must happen before publication."
                ),
            })
        elif status == "refused":
            warnings.append({
                "person": person.get("name", person.get("slug", "")),
                "tier": "refused",
                "message": (
                    "consent_status is refused — cut the scene, "
                    "anonymize the portrayal, or re-frame from a different "
                    "angle before drafting."
                ),
            })
    return warnings


__all__ = [
    "character_payload",
    "consent_status_warnings",
    "person_payload",
    "scan_for_named_characters",
]
