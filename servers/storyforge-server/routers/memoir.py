"""Memoir-only tools: create_person, set_memoir_structure_type.

Both tools enforce ``book_category == "memoir"`` before writing — the
fiction counterparts (``create_character``, plot-architect) live elsewhere
and refuse memoir books.
"""

from __future__ import annotations

import json

from tools.shared.paths import (
    resolve_person_path,
    resolve_project_path,
    slugify,
)
from tools.state.parsers import (
    _ALLOWED_ANONYMIZATION_LEVELS,
    _ALLOWED_CONSENT_STATUSES,
    _ALLOWED_MEMOIR_STRUCTURE_TYPES,
    _ALLOWED_PERSON_CATEGORIES,
    is_valid_anonymization,
    is_valid_consent_status,
    is_valid_memoir_structure_type,
    is_valid_person_category,
    parse_frontmatter,
)

from . import _app
from ._app import _cache, mcp


@mcp.tool()
def create_person(
    book_slug: str,
    name: str,
    relationship: str,
    person_category: str,
    consent_status: str = "pending",
    anonymization: str = "none",
    real_name: str = "",
    description: str = "",
) -> str:
    """Create a real-person profile in a memoir book project (Path E #59).

    Memoir-mode counterpart to ``create_character``. Writes to
    ``people/{slug}.md`` with the four-category ethics schema documented
    in ``book_categories/memoir/craft/real-people-ethics.md``.

    Args:
        book_slug: Book project slug. The book must exist and carry
            ``book_category: memoir`` — fiction books reject this call.
        name: How the person appears in the manuscript (real or pseudonym).
        relationship: Free-text relationship to the memoirist
            (e.g. "sister", "former boss", "third-grade teacher").
        person_category: One of the four ethics categories — public-figure,
            private-living-person, deceased, anonymized-or-composite.
        consent_status: One of confirmed-consent, pending, not-required,
            refused, not-asking. Defaults to ``pending``.
        anonymization: One of none, partial, pseudonym, composite.
            Defaults to ``none``.
        real_name: Real name when ``anonymization != "none"``. Stored in
            frontmatter so the memoirist retains the mapping; never
            rendered into prose by downstream skills.
        description: Brief description / notes.
    """
    # Required field — memoir person profiles without a relationship are
    # ambiguous (is this the protagonist? a stranger? a public figure?).
    if not relationship.strip():
        return json.dumps({
            "error": "relationship is required for memoir person profiles"
        })

    if not is_valid_person_category(person_category):
        allowed = ", ".join(_ALLOWED_PERSON_CATEGORIES)
        return json.dumps({
            "error": (
                f"Invalid person_category '{person_category}'. "
                f"Allowed values: {allowed}."
            )
        })

    if not is_valid_consent_status(consent_status):
        allowed = ", ".join(_ALLOWED_CONSENT_STATUSES)
        return json.dumps({
            "error": (
                f"Invalid consent_status '{consent_status}'. "
                f"Allowed values: {allowed}."
            )
        })

    if not is_valid_anonymization(anonymization):
        allowed = ", ".join(_ALLOWED_ANONYMIZATION_LEVELS)
        return json.dumps({
            "error": (
                f"Invalid anonymization '{anonymization}'. "
                f"Allowed values: {allowed}."
            )
        })

    # Verify book exists and is memoir. Reading from cache; if the book
    # was just created this session, fall back to disk lookup so the
    # cache miss does not produce a misleading "not found".
    state = _cache.get()
    book = state.get("books", {}).get(book_slug)
    if not book:
        # Cache may be stale for a freshly scaffolded book; rebuild once.
        _cache.invalidate()
        state = _cache.get()
        book = state.get("books", {}).get(book_slug)
    if not book:
        return json.dumps({"error": f"Book '{book_slug}' not found"})
    if book.get("book_category") != "memoir":
        return json.dumps({
            "error": (
                f"Book '{book_slug}' is not a memoir "
                f"(book_category: {book.get('book_category', 'fiction')}). "
                "Use create_character for fiction books."
            )
        })

    config = _app.load_config()
    slug = slugify(name)
    person_path = resolve_person_path(config, book_slug, slug, "memoir")

    if person_path.exists():
        return json.dumps({"error": f"Person '{slug}' already exists"})

    person_path.parent.mkdir(parents=True, exist_ok=True)

    # YAML frontmatter quoting: pass user-supplied strings through json.dumps
    # so embedded quotes do not break the block.
    person_file = f"""---
name: {json.dumps(name)}
relationship: {json.dumps(relationship)}
person_category: "{person_category}"
consent_status: "{consent_status}"
anonymization: "{anonymization}"
real_name: {json.dumps(real_name)}
status: "Concept"
description: {json.dumps(description)}
---

# {name}

## Relationship

*{relationship}*

## Why this person is in the memoir

*What role do they play in the story you are telling? What would the memoir lose without them on the page?*

## Consent and ethics notes

- **Category:** {person_category}
- **Consent status:** {consent_status}
- **Anonymization:** {anonymization}

*If consent is `pending` or `not-asking`, document the reasoning here. If `refused`, note the path forward (cut / anonymize / re-frame). See `book_categories/memoir/craft/real-people-ethics.md`.*

## Memory anchors

*Specific scenes, conversations, gestures, or sensory details that fix this person on the page. Avoid reflective summary — anchor in moments.*

## Notes for the memoirist

*Private notes — never rendered into the manuscript. Background on real-life context, what you know vs. remember vs. infer, ethical questions still open.*
"""
    person_path.write_text(person_file, encoding="utf-8")

    _cache.invalidate()
    return json.dumps({
        "success": True,
        "slug": slug,
        "path": str(person_path),
        "message": f"Person '{name}' created",
    })


@mcp.tool()
def set_memoir_structure_type(book_slug: str, structure_type: str) -> str:
    """Persist the memoir's chosen structure type (Path E #58).

    Validates against the four allowed types from
    ``book_categories/memoir/craft/memoir-structure-types.md``:
    chronological / thematic / braided / vignette.

    Writes to ``plot/structure.md`` frontmatter so downstream skills
    (``chapter-writer`` in memoir mode #57, ``rolling-planner``) can read
    the choice without parsing the body. The body of the file is
    preserved if it already exists; missing frontmatter is prepended.

    Memoir-only — fiction books are rejected. Use ``plot-architect``
    Step 2's standard structure catalog for fiction.

    Args:
        book_slug: Book project slug.
        structure_type: One of chronological, thematic, braided, vignette.
    """
    if not is_valid_memoir_structure_type(structure_type):
        allowed = ", ".join(_ALLOWED_MEMOIR_STRUCTURE_TYPES)
        return json.dumps({
            "error": (
                f"Invalid structure_type '{structure_type}'. "
                f"Allowed values: {allowed}."
            )
        })

    # Memoir-only gate — same pattern as create_person.
    state = _cache.get()
    book = state.get("books", {}).get(book_slug)
    if not book:
        _cache.invalidate()
        state = _cache.get()
        book = state.get("books", {}).get(book_slug)
    if not book:
        return json.dumps({"error": f"Book '{book_slug}' not found"})
    if book.get("book_category") != "memoir":
        return json.dumps({
            "error": (
                f"Book '{book_slug}' is not a memoir "
                f"(book_category: {book.get('book_category', 'fiction')}). "
                "Memoir structure types only apply to book_category: memoir."
            )
        })

    config = _app.load_config()
    project_dir = resolve_project_path(config, book_slug)
    structure_path = project_dir / "plot" / "structure.md"

    # If the file does not exist (legacy memoir scaffolded before #63),
    # create it with frontmatter + a stub body. Otherwise, parse and
    # preserve the body — only the frontmatter is rewritten.
    if structure_path.exists():
        existing = structure_path.read_text(encoding="utf-8")
        meta, body = parse_frontmatter(existing)
        meta["structure_type"] = structure_type
        # YAML round-trip via inline strings so the file stays diff-friendly
        # for the user's editor.
        fm = "\n".join(f'{k}: "{v}"' if isinstance(v, str) else f"{k}: {v}"
                       for k, v in meta.items())
        new_text = f"---\n{fm}\n---\n{body if body else ''}"
        if not body:
            # Existing file had no frontmatter and no body — write a stub.
            new_text = (
                f'---\nstructure_type: "{structure_type}"\n---\n\n'
                f"# {book.get('title', book_slug)} — Memoir Structure\n\n"
                f"*Structure type: {structure_type}. "
                "See `book_categories/memoir/craft/memoir-structure-types.md`.*\n"
            )
    else:
        structure_path.parent.mkdir(parents=True, exist_ok=True)
        new_text = (
            f'---\nstructure_type: "{structure_type}"\n---\n\n'
            f"# {book.get('title', book_slug)} — Memoir Structure\n\n"
            f"*Structure type: {structure_type}. "
            "See `book_categories/memoir/craft/memoir-structure-types.md`.*\n"
        )

    structure_path.write_text(new_text, encoding="utf-8")
    _cache.invalidate()

    return json.dumps({
        "success": True,
        "book_slug": book_slug,
        "structure_type": structure_type,
        "path": str(structure_path),
    })
