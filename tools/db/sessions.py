"""DB-backed session storage — Issue #280.

Replaces session.json / state-cache session with a proper SQLite row.
The `notes` column stores extra fields as JSON so the schema stays stable
while the session dict can carry arbitrary keys.
"""

from __future__ import annotations

import json
import sqlite3

_COLUMN_MAP = {
    "last_book": "current_book_slug",
    "last_chapter": "current_chapter",
    "last_phase": "next_beat",
}
_EXTRA_FIELDS = {"active_author"}


def update_session_in_db(
    conn: sqlite3.Connection,
    user_id: str,
    *,
    last_book: str = "",
    last_chapter: str = "",
    last_phase: str = "",
    active_author: str = "",
) -> None:
    """Upsert session fields for user_id.

    Only non-empty values are written; existing values for omitted fields
    are preserved by merging with the existing row.
    """
    existing = get_session_from_db(conn, user_id)

    if last_book:
        existing["last_book"] = last_book
    if last_chapter:
        existing["last_chapter"] = last_chapter
    if last_phase:
        existing["last_phase"] = last_phase
    if active_author:
        existing["active_author"] = active_author

    notes_dict = {k: v for k, v in existing.items() if k in _EXTRA_FIELDS}

    conn.execute(
        """
        INSERT INTO sessions (user_id, current_book_slug, current_chapter, next_beat, notes, last_updated)
        VALUES (?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
        ON CONFLICT(user_id) DO UPDATE SET
            current_book_slug = excluded.current_book_slug,
            current_chapter   = excluded.current_chapter,
            next_beat         = excluded.next_beat,
            notes             = excluded.notes,
            last_updated      = CURRENT_TIMESTAMP
        """,
        (
            user_id,
            existing.get("last_book", ""),
            existing.get("last_chapter", ""),
            existing.get("last_phase", ""),
            json.dumps(notes_dict),
        ),
    )
    conn.commit()


def get_session_from_db(conn: sqlite3.Connection, user_id: str) -> dict:
    """Return session dict for user_id.

    Falls back to the legacy state.json session block if no DB row exists yet
    (H2 fix: prevents silent data-loss on first upgrade from file-based session).
    """
    row = conn.execute(
        "SELECT current_book_slug, current_chapter, next_beat, notes FROM sessions WHERE user_id = ?",
        (user_id,),
    ).fetchone()
    if not row:
        return _read_legacy_session()

    session: dict = {}
    if row["current_book_slug"]:
        session["last_book"] = row["current_book_slug"]
    if row["current_chapter"]:
        session["last_chapter"] = row["current_chapter"]
    if row["next_beat"]:
        session["last_phase"] = row["next_beat"]

    try:
        extra = json.loads(row["notes"] or "{}")
        session.update(extra)
    except (json.JSONDecodeError, TypeError):
        pass

    return session


def _read_legacy_session() -> dict:
    """Read session from the legacy ~/.storyforge/cache/state.json (H2 fallback)."""
    try:
        from tools.shared.config import STATE_PATH
        if not STATE_PATH.exists():
            return {}
        data = json.loads(STATE_PATH.read_text(encoding="utf-8"))
        return data.get("session", {})
    except (OSError, json.JSONDecodeError):
        return {}
