"""Cover-image import — Issue #551.

import_cover_image(): copy an externally-generated cover image (Midjourney,
DALL-E, etc. — StoryForge only generates the prompts via cover-artist, never
the image itself) into the book project and record whether it's a draft or
the final version, so a future export step can find the right file.
"""

from __future__ import annotations
from mcp.types import ToolAnnotations

import filecmp
import json
import shutil
from pathlib import Path

import tools.db.connection as _db_conn
from tools.db.cover_images import upsert_cover_image
from tools.shared.paths import catch_slug_value_error, resolve_project_path

from . import _app
from ._app import mcp

_ALLOWED_IMAGE_EXTENSIONS = (".png", ".jpg", ".jpeg", ".gif", ".webp")
_MAX_COVER_VARIANTS = 100


@mcp.tool(annotations=ToolAnnotations(idempotent_hint=True))
@catch_slug_value_error
def import_cover_image(book_slug: str, source_path: str, is_final: bool = False) -> str:
    """Copy an externally-generated cover image into the book project.

    Copies ``source_path`` into ``{project}/cover/art/`` (already scaffolded
    by ``create_book_structure()``) and records the import in the book's
    SQLite DB together with an ``is_final`` flag. Re-importing the exact
    same source file is idempotent — no duplicate copy is made, only the
    recorded flag/timestamp is updated. Marking a new import as final
    clears the flag on every other cover image previously recorded for the
    same book, so at most one file is ever "the" final version.

    Args:
        book_slug: Book identifier.
        source_path: Absolute path to the generated image file. Must exist,
            resolve to a location outside ``content_root`` (refuses to
            copy a file that's already part of a book project), and have
            an allowed image extension.
        is_final: True records this as the version an export step should
            use; False (default) records it as a draft (e.g. an
            image-without-text preview).
    """
    if "\x00" in source_path:
        return json.dumps({"error": "Invalid source_path: embedded null byte"})

    config = _app.load_config()
    book_root = resolve_project_path(config, book_slug)
    if not book_root.is_dir():
        return json.dumps({"error": f"Book '{book_slug}' not found"})

    try:
        src = Path(source_path).resolve()
    except (OSError, RuntimeError, ValueError) as exc:
        return json.dumps({"error": f"Invalid source_path: {exc}"})

    if not src.is_file():
        return json.dumps({"error": f"source_path not found: {source_path}"})

    if src.suffix.lower() not in _ALLOWED_IMAGE_EXTENSIONS:
        allowed = ", ".join(_ALLOWED_IMAGE_EXTENSIONS)
        return json.dumps({"error": f"Unsupported image extension '{src.suffix}'. Allowed: {allowed}"})

    content_root = Path(config["paths"]["content_root"]).resolve()
    if src.is_relative_to(content_root):
        return json.dumps(
            {
                "error": "source_path must be outside content_root — refusing to copy a file already inside a book project"
            }
        )

    dest_dir = book_root / "cover" / "art"
    try:
        dest_dir.mkdir(parents=True, exist_ok=True)
        dest, needs_copy = _resolve_dest_path(dest_dir, src)
    except OSError as exc:
        return json.dumps({"error": f"Failed to prepare cover/art directory: {exc}"})
    except RuntimeError as exc:
        # _resolve_dest_path's _MAX_COVER_VARIANTS safety cap.
        return json.dumps({"error": str(exc)})

    # Resolve the DB before touching the filesystem: get_db_slug_for_book()
    # reads the series slug from README frontmatter and can raise
    # SlugValidationError (caught by @catch_slug_value_error) on a
    # hand-edited, malformed value. Doing this first means that failure
    # never leaves a copied file with no matching DB record.
    db_slug = _db_conn.get_db_slug_for_book(book_root)
    book_num = _db_conn.get_book_num(book_root)
    conn = _db_conn.open_canon_db(db_slug)
    try:
        if needs_copy:
            try:
                shutil.copyfile(src, dest)
            except OSError as exc:
                return json.dumps({"error": f"Failed to copy cover image: {exc}"})
        upsert_cover_image(conn, book_num=book_num, filename=dest.name, is_final=is_final)
    finally:
        conn.close()

    return json.dumps(
        {
            "success": True,
            "book_slug": book_slug,
            "cover_image_path": str(dest),
            "filename": dest.name,
            "is_final": is_final,
        }
    )


def _resolve_dest_path(dest_dir: Path, src: Path) -> tuple[Path, bool]:
    """Pick the destination path inside dest_dir for a copy of src.

    Returns ``(path, needs_copy)``. Preserves src's own filename when
    possible:
    - name free -> use it as-is, ``needs_copy=True``.
    - name taken, byte-identical to src -> reuse that file,
      ``needs_copy=False``. Checked at every numbered candidate, not just
      the first, so re-importing a file that previously collided (and was
      stored as e.g. ``cover-2.png``) is idempotent instead of growing a
      new copy on every call.
    - name taken, different content -> append a numeric suffix (``-2``,
      ``-3``, ...) so distinct drafts sharing a source filename coexist.
    """
    stem, suffix = src.stem, src.suffix
    candidate = dest_dir / src.name
    for counter in range(2, _MAX_COVER_VARIANTS + 1):
        if not candidate.exists():
            return candidate, True
        if filecmp.cmp(candidate, src, shallow=False):
            return candidate, False
        candidate = dest_dir / f"{stem}-{counter}{suffix}"
    raise RuntimeError(f"Too many cover image variants named '{stem}{suffix}' in {dest_dir}")
