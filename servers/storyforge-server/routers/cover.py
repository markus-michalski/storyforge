"""Cover-image import — Issue #551.

import_cover_image(): copy an externally-generated cover image (Midjourney,
DALL-E, etc. — StoryForge only generates the prompts via cover-artist, never
the image itself) into the book project and record whether it's a draft or
the final version, so a future export step can find the right file.
"""

from __future__ import annotations
from mcp.types import ToolAnnotations

import json
from pathlib import Path

import tools.db.connection as _db_conn
from tools.db.cover_images import upsert_cover_image
from tools.shared.paths import catch_slug_value_error, resolve_project_path

from . import _app
from ._app import mcp

_ALLOWED_IMAGE_EXTENSIONS = (".png", ".jpg", ".jpeg", ".gif", ".webp")
_MAX_COVER_VARIANTS = 100
_MAX_COVER_IMAGE_BYTES = 50 * 1024 * 1024  # 50 MB — #555 M-5

# Magic-byte signatures per allowed extension — #555 M-5. WebP isn't listed
# here: RIFF is a generic container header shared with other formats (e.g.
# WAV), so it needs a second check at offset 8 for the "WEBP" marker,
# handled entirely as a special case in _looks_like_declared_image_type()
# rather than as a single-signature entry that would silently degrade to
# "any RIFF file" if that special case were ever removed.
_MAGIC_BYTES: dict[str, tuple[bytes, ...]] = {
    ".png": (b"\x89PNG\r\n\x1a\n",),
    ".jpg": (b"\xff\xd8\xff",),
    ".jpeg": (b"\xff\xd8\xff",),
    ".gif": (b"GIF87a", b"GIF89a"),
}


def _looks_like_declared_image_type(path: Path, suffix: str) -> bool:
    """Check src's actual bytes match what its extension claims (#555 M-5).

    The extension allowlist alone is just a suffix string — it doesn't
    verify the file is actually an image, and this copy is later embedded
    into exported EPUBs. Reads only the first 16 bytes, no full decode.
    """
    try:
        with path.open("rb") as f:
            header = f.read(16)
    except OSError:
        return False
    if suffix == ".webp":
        return header[:4] == b"RIFF" and header[8:12] == b"WEBP"
    return any(header.startswith(magic) for magic in _MAGIC_BYTES.get(suffix, ()))


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
            be a non-empty file no larger than 50 MB whose content actually
            matches its extension (magic-byte checked), resolve to a
            location outside both ``content_root`` and ``authors_root``
            (refuses to copy a file that's already part of a book project
            or an author profile), and have an allowed image extension.
        is_final: True records this as the version an export step should
            use; False (default) records it as a draft (e.g. an
            image-without-text preview).
    """
    if "\x00" in source_path:
        return json.dumps({"error": "Invalid source_path: embedded null byte"})

    # #555 L-5: the docstring has always said "Absolute path", but nothing
    # enforced it — a relative path silently resolved against the MCP
    # server process's unpredictable CWD rather than any well-defined root.
    if not Path(source_path).is_absolute():
        return json.dumps(
            {"error": "source_path must be an absolute path (on Windows, include the drive, e.g. C:\\...)"}
        )

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

    # #555 M-5: non-empty + size cap, before the magic-byte read.
    try:
        size = src.stat().st_size
    except OSError as exc:
        return json.dumps({"error": f"Failed to stat source_path: {exc}"})
    if size == 0:
        return json.dumps({"error": "source_path is an empty file"})
    if size > _MAX_COVER_IMAGE_BYTES:
        max_mb = _MAX_COVER_IMAGE_BYTES // (1024 * 1024)
        return json.dumps({"error": f"source_path exceeds the {max_mb} MB size cap ({size} bytes)"})

    suffix = src.suffix.lower()
    if not _looks_like_declared_image_type(src, suffix):
        return json.dumps(
            {"error": f"source_path does not look like a valid {suffix} file (magic-byte check failed)"}
        )

    content_root = Path(config["paths"]["content_root"]).resolve()
    authors_root = Path(config["paths"]["authors_root"]).resolve()
    if src.is_relative_to(content_root) or src.is_relative_to(authors_root):
        return json.dumps(
            {
                "error": (
                    "source_path must be outside content_root and authors_root — refusing to copy "
                    "a file that's already part of a book project or an author profile"
                )
            }
        )

    # #555 M-1: book_root itself comes from resolve_project_path(), not
    # attacker input, but dest_dir was previously built from the
    # *unresolved* book_root while content_root above is always .resolve()d
    # — re-resolve and assert containment the same way update_field() does
    # for file_path (routers/state.py, Audit H1 #115), rather than relying
    # on the two being resolved consistently by construction.
    book_root = book_root.resolve()
    if not book_root.is_relative_to(content_root):
        return json.dumps({"error": f"Resolved book path escapes content_root: {book_root}"})

    # The containment check above covers book_root, but dest_dir adds two
    # more path components ("cover"/"art") that are never re-resolved before
    # this fix — if either is a symlink (POSIX) or a junction (Windows)
    # pointing outside content_root, mkdir()/the copy would follow it right
    # out of the managed tree while the book_root check above passed clean.
    # Resolve dest_dir itself and re-check before creating or writing
    # anything under it.
    dest_dir = book_root / "cover" / "art"
    try:
        resolved_dest_dir = dest_dir.resolve()
    except (OSError, RuntimeError, ValueError) as exc:
        return json.dumps({"error": f"Invalid cover art path: {exc}"})
    if not resolved_dest_dir.is_relative_to(content_root):
        return json.dumps({"error": f"Resolved cover art path escapes content_root: {resolved_dest_dir}"})

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
                dest = _copy_exclusive_with_retry(dest_dir, src, dest)
            except OSError as exc:
                return json.dumps({"error": f"Failed to copy cover image: {exc}"})
            except RuntimeError as exc:
                return json.dumps({"error": str(exc)})
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


def _files_identical(a: Path, b: Path) -> bool:
    """Byte-for-byte comparison, deliberately not using filecmp (#556 L-4).

    ``filecmp.cmp(..., shallow=False)`` still consults ``filecmp._cache``,
    a process-global cache keyed on ``(path1, path2, sig1, sig2)`` where the
    signature is ``(mode, size, mtime)``. On a filesystem with coarse mtime
    resolution (FAT32: 2s, some network mounts: 1s), a regenerated file
    written to the same path with the same size within that window can hit
    a stale cache entry from an earlier, different version of that file —
    reporting "identical" for content that actually changed. Comparing
    directly, chunk by chunk, has no such cache to go stale.
    """
    if not (a.is_file() and b.is_file()):
        return False
    try:
        if a.stat().st_size != b.stat().st_size:
            return False
    except OSError:
        return False
    chunk_size = 1024 * 1024
    with a.open("rb") as fa, b.open("rb") as fb:
        while True:
            chunk_a = fa.read(chunk_size)
            chunk_b = fb.read(chunk_size)
            if chunk_a != chunk_b:
                return False
            if not chunk_a:
                return True


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

    This is a plan, not a commitment — the actual write happens later via
    ``_copy_exclusive_with_retry()``, which re-validates the chosen name
    atomically to close the TOCTOU window between this check and that
    write (#555 L-6).
    """
    stem, suffix = src.stem, src.suffix
    candidate = dest_dir / src.name
    for counter in range(2, _MAX_COVER_VARIANTS + 1):
        if not candidate.exists():
            return candidate, True
        if _files_identical(candidate, src):
            return candidate, False
        candidate = dest_dir / f"{stem}-{counter}{suffix}"
    raise RuntimeError(f"Too many cover image variants named '{stem}{suffix}' in {dest_dir}")


_COPY_CHUNK_BYTES = 1024 * 1024  # 1 MB


def _copy_exclusive_with_retry(dest_dir: Path, src: Path, dest: Path) -> Path:
    """Copy src to dest using exclusive creation, retrying on a race.

    ``_resolve_dest_path()`` decides ``dest`` from a plain ``.exists()``
    check, which leaves a TOCTOU window between that check and the actual
    write — two concurrent ``import_cover_image()`` calls could both decide
    the same name is free, and whichever wrote second would silently
    clobber the other's copy while both write ``cover_images`` rows
    (#555 L-6). Exclusive creation (``"xb"`` -> ``O_CREAT | O_EXCL``) closes
    that clobber window: a losing writer gets ``FileExistsError`` instead of
    overwriting (and, as a side effect, refuses to follow a symlink already
    sitting at ``dest`` — ``shutil.copyfile`` would have written straight
    through one), and retries against the next numbered candidate the same
    way ``_resolve_dest_path()``'s own loop does. A concurrent import of the
    exact same source file is a best-effort convergence, not a guarantee —
    the ``_files_identical()`` check below can race against a writer
    that's still mid-copy and see a false "different" verdict, growing a
    harmless extra copy rather than corrupting anything.

    Copies in chunks with a running byte count against
    ``_MAX_COVER_IMAGE_BYTES`` rather than trusting the caller's earlier
    ``stat()``-based size check (#555 M-5): that check reads ``src`` at a
    different instant than this write does, so it's a fast-fail UX
    convenience, not a real bound on what lands on disk. This loop is the
    actual bound — a source that grows past the cap between the two reads
    aborts here and the partial file is removed rather than kept.
    """
    stem, suffix = src.stem, src.suffix
    counter = 2
    while True:
        try:
            with dest.open("xb") as fdst:
                try:
                    with src.open("rb") as fsrc:
                        written = 0
                        while True:
                            chunk = fsrc.read(_COPY_CHUNK_BYTES)
                            if not chunk:
                                break
                            written += len(chunk)
                            if written > _MAX_COVER_IMAGE_BYTES:
                                raise OSError(
                                    f"source_path grew past the {_MAX_COVER_IMAGE_BYTES // (1024 * 1024)} "
                                    "MB size cap during copy"
                                )
                            fdst.write(chunk)
                except BaseException:
                    # #555 M-2: O_EXCL guarantees we — and only we — created
                    # this file, so it's always safe to remove it on any
                    # failure partway through the copy. Without this, a
                    # source read error or a disk-full mid-copy leaves a
                    # truncated file with no matching cover_images row,
                    # which then permanently blocks re-importing the same
                    # name (every retry sees it as an existing, different
                    # file and gets shunted to a numbered suffix instead).
                    fdst.close()
                    dest.unlink(missing_ok=True)
                    raise
            return dest
        except FileExistsError:
            if _files_identical(dest, src):
                return dest
            if counter > _MAX_COVER_VARIANTS:
                raise RuntimeError(f"Too many cover image variants named '{stem}{suffix}' in {dest_dir}")
            dest = dest_dir / f"{stem}-{counter}{suffix}"
            counter += 1
