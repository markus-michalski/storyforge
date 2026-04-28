"""Memoir ethics checker — consent and real-people risk scanner (Issue #65).

Reads person profiles from a memoir book's ``people/`` directory and
classifies each person as PASS / WARN / FAIL based on their
``consent_status`` and ``person_category`` fields.

Verdict logic
-------------
FAIL  — ``refused``: person explicitly declined consent.
WARN  — ``pending``: consent not yet sought.
       ``not-asking``: deliberate choice not to ask.
       Missing, empty, or unrecognised ``consent_status``.
       Missing or unrecognised ``person_category`` (incomplete profile).
PASS  — ``confirmed-consent``: person has agreed.
       ``not-required``: public figure on public matters, deceased, or
       fully anonymised composite.

Overall verdict: FAIL beats WARN beats PASS.

The checker is memoir-only.  Calling it on a fiction book raises
``ValueError``.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

from tools.state.parsers import parse_person_file

# ---------------------------------------------------------------------------
# Constants (mirrored from parsers.py to avoid importing private names)
# ---------------------------------------------------------------------------

_PASS_STATUSES = frozenset({"confirmed-consent", "not-required"})
_FAIL_STATUSES = frozenset({"refused"})
_WARN_STATUSES = frozenset({"pending", "not-asking"})

_VALID_PERSON_CATEGORIES = frozenset(
    {"public-figure", "private-living-person", "deceased", "anonymized-or-composite"}
)

_FRONTMATTER_RE = re.compile(r"^---\s*\n(.*?)\n---\s*\n", re.DOTALL)
_BOOK_CATEGORY_RE = re.compile(r"^\s*book_category:\s*['\"]?(\w[\w-]*)['\"]?\s*$", re.MULTILINE)
_BOOK_SLUG_RE = re.compile(r"^\s*slug:\s*['\"]?([^'\"\n]+?)['\"]?\s*$", re.MULTILINE)


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _read_book_meta(book_path: Path) -> tuple[str, str]:
    """Return (book_category, book_slug) from book README frontmatter."""
    readme = book_path / "README.md"
    if not readme.is_file():
        raise FileNotFoundError(f"No README.md found at {book_path}")
    text = readme.read_text(encoding="utf-8")
    fm = _FRONTMATTER_RE.match(text)
    if not fm:
        return "fiction", book_path.name
    body = fm.group(1)
    cat_m = _BOOK_CATEGORY_RE.search(body)
    category = cat_m.group(1).strip() if cat_m else "fiction"
    slug_m = _BOOK_SLUG_RE.search(body)
    slug = slug_m.group(1).strip() if slug_m else book_path.name
    return category, slug


def _classify_person(person: dict[str, Any]) -> tuple[str, str]:
    """Return (verdict, reason) for a single person dict."""
    consent = (person.get("consent_status") or "").strip()
    category = (person.get("person_category") or "").strip()

    # FAIL gate — hard stop
    if consent in _FAIL_STATUSES:
        return "FAIL", (
            f"consent_status is '{consent}' — this person has explicitly refused. "
            "Do not publish their portrayal without legal review."
        )

    # Incomplete profile — always at least WARN
    missing_category = category not in _VALID_PERSON_CATEGORIES

    if consent in _PASS_STATUSES:
        if missing_category:
            return "WARN", (
                f"consent_status is '{consent}' but person_category is "
                f"'{category or '(empty)'}' — fill in the four-category field "
                "before export."
            )
        return "PASS", f"consent_status '{consent}' with category '{category}'."

    if consent in _WARN_STATUSES:
        if missing_category:
            return "WARN", (
                f"consent_status is '{consent}' and person_category is "
                f"'{category or '(empty)'}' — both need attention before publication."
            )
        return "WARN", (
            f"consent_status is '{consent}' — resolve before publication."
        )

    # Unknown / empty consent_status
    reason_parts = [
        f"consent_status is '{consent or '(empty)'}' — unrecognised value."
    ]
    if missing_category:
        reason_parts.append(
            f"person_category is '{category or '(empty)'}' — unrecognised value."
        )
    return "WARN", " ".join(reason_parts)


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def read_people_for_ethics(book_path: Path) -> list[dict[str, Any]]:
    """Read all person profiles from ``people/`` and return structured list.

    Returns an empty list when the directory is absent.  INDEX.md is skipped.
    """
    people_dir = book_path / "people"
    if not people_dir.is_dir():
        return []
    result = []
    for md in sorted(people_dir.glob("*.md")):
        if md.name.upper() == "INDEX.MD":
            continue
        result.append(parse_person_file(md))
    return result


def check_consent(book_path: Path) -> dict[str, Any]:
    """Run the ethics check for a memoir book.

    Returns a dict with keys:
        book_slug    — slug string from README
        overall      — "PASS" | "WARN" | "FAIL"
        people       — list of per-person result dicts
        pass_count   — int
        warn_count   — int
        fail_count   — int

    Each person dict adds ``verdict`` and ``reason`` to the parsed fields.

    Raises
    ------
    ValueError
        When the book is not a memoir (``book_category != "memoir"``).
    FileNotFoundError
        When no README.md is found.
    """
    category, slug = _read_book_meta(book_path)
    if category != "memoir":
        raise ValueError(
            f"memoir-ethics-checker only runs on memoir books; "
            f"this book has book_category='{category}'."
        )

    people_raw = read_people_for_ethics(book_path)
    people_out: list[dict[str, Any]] = []
    pass_count = warn_count = fail_count = 0

    for person in people_raw:
        verdict, reason = _classify_person(person)
        people_out.append({**person, "verdict": verdict, "reason": reason})
        if verdict == "PASS":
            pass_count += 1
        elif verdict == "WARN":
            warn_count += 1
        else:
            fail_count += 1

    if fail_count:
        overall = "FAIL"
    elif warn_count:
        overall = "WARN"
    else:
        overall = "PASS"

    return {
        "book_slug": slug,
        "overall": overall,
        "people": people_out,
        "pass_count": pass_count,
        "warn_count": warn_count,
        "fail_count": fail_count,
    }
