"""Regression tests for the ``update_field`` MCP tool.

Issue: update_field treated chapter.yaml as a markdown file and wrapped the
existing plain-YAML content in frontmatter delimiters (``---``), producing a
multi-document YAML stream. yaml.safe_load then threw ComposerError, so
parse_chapter_readme fell back to an empty dict and defaulted the chapter
status to "Outline" — making chapters appear undrafted even after review.
"""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import patch

import pytest
import yaml


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def content_root(tmp_path: Path) -> Path:
    root = tmp_path / "content"
    root.mkdir()
    return root


@pytest.fixture
def mock_config(content_root: Path):
    fake_config = {
        "paths": {
            "content_root": str(content_root),
            "authors_root": str(content_root / "authors"),
        },
        "defaults": {"language": "en", "book_type": "novel"},
    }

    import routers._app as server_mod
    from tools.state import indexer as indexer_mod

    fake_state_path = content_root / "_cache" / "state.json"

    with (
        patch.object(server_mod, "load_config", return_value=fake_config),
        patch.object(server_mod, "get_content_root", return_value=content_root),
        patch.object(indexer_mod, "load_config", return_value=fake_config),
        patch.object(indexer_mod, "STATE_PATH", fake_state_path),
        patch.object(indexer_mod, "CACHE_DIR", fake_state_path.parent),
    ):
        server_mod._cache.invalidate()
        yield fake_config


@pytest.fixture
def server_module(mock_config):  # noqa: F811
    import server as server_mod

    return server_mod


# ---------------------------------------------------------------------------
# update_field — YAML files
# ---------------------------------------------------------------------------


class TestUpdateFieldYaml:
    def test_updates_plain_yaml_without_frontmatter_markers(self, server_module, content_root: Path):
        """update_field on a .yaml file must NOT wrap content in --- delimiters."""
        chapter_yaml = content_root / "chapter.yaml"
        chapter_yaml.write_text("status: Draft\ntitle: Test Chapter\n", encoding="utf-8")

        result = json.loads(server_module.update_field(str(chapter_yaml), "status", "Review"))

        assert result["success"] is True
        content = chapter_yaml.read_text(encoding="utf-8")
        # Must be parseable as plain YAML — no ComposerError
        meta = yaml.safe_load(content)
        assert isinstance(meta, dict), "chapter.yaml must remain a valid plain-YAML dict"
        assert meta["status"] == "Review"
        assert "---" not in content, "chapter.yaml must never contain frontmatter markers"

    def test_preserves_existing_fields_in_yaml(self, server_module, content_root: Path):
        chapter_yaml = content_root / "chapter.yaml"
        chapter_yaml.write_text("status: Draft\ntitle: Bruises\nnumber: 20\n", encoding="utf-8")

        server_module.update_field(str(chapter_yaml), "status", "Review")

        meta = yaml.safe_load(chapter_yaml.read_text(encoding="utf-8"))
        assert meta["title"] == "Bruises"
        assert meta["number"] == 20
        assert meta["status"] == "Review"

    def test_regression_broken_double_frontmatter(self, server_module, content_root: Path):
        """Regression: the exact broken file shape from the bug report.

        Before the fix, update_field on a plain-YAML chapter.yaml produced:
            ---
            status: Review
            ---
            status: Draft

        yaml.safe_load raises ComposerError on this, causing parse_chapter_readme
        to return status "Outline" even though the chapter is reviewed.
        """
        chapter_yaml = content_root / "chapter.yaml"
        # Simulate the broken state written by the old code path
        chapter_yaml.write_text("---\nstatus: Review\n---\nstatus: Draft\n", encoding="utf-8")

        # A subsequent update must heal the file, not make it worse
        result = json.loads(server_module.update_field(str(chapter_yaml), "status", "Review"))

        assert result["success"] is True
        meta = yaml.safe_load(chapter_yaml.read_text(encoding="utf-8"))
        assert isinstance(meta, dict)
        assert meta["status"] == "Review"

    def test_start_chapter_draft_then_update_field_roundtrip(self, server_module, content_root: Path):
        """Full workflow: start_chapter_draft writes plain YAML, update_field
        transitions status forward — parse_chapter_readme must read correctly."""
        from tools.state.parsers import parse_chapter_readme

        book_dir = content_root / "projects" / "test-book"
        ch_dir = book_dir / "chapters" / "20-bruises"
        ch_dir.mkdir(parents=True)
        (book_dir / "README.md").write_text('---\ntitle: "Test"\nstatus: "Drafting"\n---\n', encoding="utf-8")
        (ch_dir / "README.md").write_text("# Bruises\n\nOutline.\n", encoding="utf-8")
        (ch_dir / "chapter.yaml").write_text('title: "Bruises"\nnumber: 20\nstatus: "Outline"\n', encoding="utf-8")

        # Step 1 — chapter-writer calls start_chapter_draft
        server_module.start_chapter_draft("test-book", "20-bruises")
        meta_after_draft = yaml.safe_load((ch_dir / "chapter.yaml").read_text(encoding="utf-8"))
        assert meta_after_draft["status"] == "Draft"

        # Step 2 — chapter-reviewer calls update_field to advance to Review
        chapter_yaml_path = str(ch_dir / "chapter.yaml")
        server_module.update_field(chapter_yaml_path, "status", "Review")

        # parse_chapter_readme must reflect the new status — not fall back to Outline
        parsed = parse_chapter_readme(ch_dir / "README.md")
        assert parsed["status"] == "Review", (
            "parse_chapter_readme must read 'Review' from chapter.yaml after "
            "update_field — ComposerError would silently return 'Outline'"
        )


# ---------------------------------------------------------------------------
# update_field — Markdown files (existing behaviour must be unchanged)
# ---------------------------------------------------------------------------


class TestUpdateFieldMarkdown:
    def test_updates_existing_frontmatter_field(self, server_module, content_root: Path):
        md = content_root / "README.md"
        md.write_text("---\nstatus: Draft\ntitle: Test\n---\n\nBody text.\n", encoding="utf-8")

        result = json.loads(server_module.update_field(str(md), "status", "Review"))

        assert result["success"] is True
        content = md.read_text(encoding="utf-8")
        assert "status: Review" in content
        assert "Body text." in content

    def test_adds_field_when_absent_in_frontmatter(self, server_module, content_root: Path):
        md = content_root / "README.md"
        md.write_text("---\ntitle: Test\n---\n\nBody.\n", encoding="utf-8")

        server_module.update_field(str(md), "status", "Revision")

        content = md.read_text(encoding="utf-8")
        assert "status: Revision" in content

    def test_creates_frontmatter_when_none_exists(self, server_module, content_root: Path):
        md = content_root / "README.md"
        md.write_text("Just a body without frontmatter.\n", encoding="utf-8")

        server_module.update_field(str(md), "status", "Draft")

        content = md.read_text(encoding="utf-8")
        assert "---" in content
        assert "status: Draft" in content


# ---------------------------------------------------------------------------
# Issue #372 — update_field must patch surgically, not rewrite the whole
# frontmatter block. Regression fixture mirrors create_book_structure's
# README template: double-quoted strings, flow-style genres list.
# ---------------------------------------------------------------------------

_BOOK_README_TEMPLATE = (
    '---\n'
    'title: "Test Memoir"\n'
    'slug: "zz-sandbox-book-memoir"\n'
    'author: "Jane Doe"\n'
    'genres: ["drama"]\n'
    'book_type: "novel"\n'
    'book_category: "memoir"\n'
    'status: "Idea"\n'
    'language: "en"\n'
    'target_word_count: 75000\n'
    'series: ""\n'
    'series_number: 0\n'
    'description: ""\n'
    'created: "2026-04-01"\n'
    'updated: "2026-04-01"\n'
    '---\n'
    '\n'
    '# Test Memoir\n'
)


class TestUpdateFieldMinimalDiff:
    def test_only_touched_field_line_changes(self, server_module, content_root: Path):
        """A single-field update must change exactly one line of the file —
        not reorder or reformat every other field (Issue #372)."""
        md = content_root / "README.md"
        md.write_text(_BOOK_README_TEMPLATE, encoding="utf-8")

        server_module.update_field(str(md), "status", "Concept")

        new_lines = md.read_text(encoding="utf-8").splitlines()
        old_lines = _BOOK_README_TEMPLATE.splitlines()
        assert len(new_lines) == len(old_lines), "line count must not change"
        changed = [i for i, (a, b) in enumerate(zip(old_lines, new_lines)) if a != b]
        assert changed == [old_lines.index('status: "Idea"')]
        assert new_lines[changed[0]] == "status: Concept"

    def test_key_order_preserved(self, server_module, content_root: Path):
        """Regression: the old code piped the whole dict through yaml.dump(),
        which defaults to sort_keys=True and alphabetized every field."""
        md = content_root / "README.md"
        md.write_text(_BOOK_README_TEMPLATE, encoding="utf-8")

        server_module.update_field(str(md), "status", "Concept")

        from tools.state.parsers import parse_frontmatter

        meta, _ = parse_frontmatter(md.read_text(encoding="utf-8"))
        assert list(meta.keys()) == [
            "title",
            "slug",
            "author",
            "genres",
            "book_type",
            "book_category",
            "status",
            "language",
            "target_word_count",
            "series",
            "series_number",
            "description",
            "created",
            "updated",
        ]

    def test_quote_and_flow_style_of_untouched_fields_preserved(self, server_module, content_root: Path):
        """Regression: the old code re-rendered every value through
        yaml.dump()'s own quoting/flow-style heuristics, turning
        genres: ["drama"] into a block-style list and dropping quotes from
        plain-string fields, even though only `status` was updated."""
        md = content_root / "README.md"
        md.write_text(_BOOK_README_TEMPLATE, encoding="utf-8")

        server_module.update_field(str(md), "status", "Concept")

        content = md.read_text(encoding="utf-8")
        assert 'genres: ["drama"]' in content
        assert 'title: "Test Memoir"' in content
        assert 'created: "2026-04-01"' in content

    def test_new_field_appended_without_touching_existing_lines(self, server_module, content_root: Path):
        md = content_root / "README.md"
        md.write_text(_BOOK_README_TEMPLATE, encoding="utf-8")

        server_module.update_field(str(md), "ticket", "#372")

        expected = _BOOK_README_TEMPLATE.replace(
            'updated: "2026-04-01"\n---\n',
            'updated: "2026-04-01"\nticket: \'#372\'\n---\n',
        )
        assert md.read_text(encoding="utf-8") == expected

    def test_falls_back_to_full_reserialize_for_block_scalar(self, server_module, content_root: Path):
        """A field whose value is a YAML block scalar can't be single-line
        patched — must fall back to the full round-trip instead of
        corrupting the block."""
        md = content_root / "README.md"
        md.write_text(
            '---\ntitle: "X"\nsummary: |\n  Line one\n  Line two\nstatus: "Draft"\n---\n\nBody.\n',
            encoding="utf-8",
        )

        result = json.loads(server_module.update_field(str(md), "status", "Final"))

        assert result["success"] is True
        from tools.state.parsers import parse_frontmatter

        meta, _ = parse_frontmatter(md.read_text(encoding="utf-8"))
        assert meta["status"] == "Final"

    def test_falls_back_to_full_reserialize_for_indented_nested_mapping(self, server_module, content_root: Path):
        """A field whose value is a nested mapping (indented continuation
        lines) can't be single-line patched — must fall back."""
        md = content_root / "README.md"
        md.write_text(
            '---\ntitle: "X"\nmeta:\n  a: 1\n  b: 2\nstatus: "Draft"\n---\n\nBody.\n',
            encoding="utf-8",
        )

        result = json.loads(server_module.update_field(str(md), "status", "Final"))

        assert result["success"] is True
        from tools.state.parsers import parse_frontmatter

        meta, _ = parse_frontmatter(md.read_text(encoding="utf-8"))
        assert meta["status"] == "Final"
        assert meta["meta"] == {"a": 1, "b": 2}

    def test_zero_indent_block_sequence_does_not_corrupt_file(self, server_module, content_root: Path):
        """Regression (Issue #372 review finding): a block-style list at the
        SAME indentation as its key (`genres:\\n- drama\\n- horror`) — the
        exact shape the full-reserialize fallback itself produces — must not
        be corrupted by a surgical patch on that field. Before the fix, the
        guard only checked for *indented* continuation lines and missed this
        zero-indent case, silently producing invalid YAML
        (`genres: mystery\\n- drama\\n- horror`)."""
        md = content_root / "README.md"
        md.write_text(
            '---\ntitle: "X"\ngenres:\n- drama\n- horror\nstatus: "Draft"\n---\n\nBody.\n',
            encoding="utf-8",
        )

        result = json.loads(server_module.update_field(str(md), "genres", "mystery"))

        assert result["success"] is True
        from tools.state.parsers import parse_frontmatter

        content = md.read_text(encoding="utf-8")
        meta, _ = parse_frontmatter(content)  # must not raise — file must stay parseable
        assert meta["genres"] == "mystery"
        assert meta["title"] == "X"

    def test_type_coercion_prone_values_round_trip_quoted(self, server_module, content_root: Path):
        """Values that look like other YAML types (int, bool, date) must be
        quoted so a later read doesn't silently coerce them — same guarantee
        the old full-dict yaml.dump() round-trip already provided."""
        md = content_root / "README.md"
        md.write_text(_BOOK_README_TEMPLATE, encoding="utf-8")

        for value in ("123", "true", "2026-01-01", "null"):
            server_module.update_field(str(md), "status", value)
            from tools.state.parsers import parse_frontmatter

            meta, _ = parse_frontmatter(md.read_text(encoding="utf-8"))
            assert meta["status"] == value, f"value {value!r} must round-trip as a string, got {meta['status']!r}"


# ---------------------------------------------------------------------------
# Audit H1 — update_field path containment
#
# update_field must reject any file_path that resolves outside
# content_root or authors_root. Without this check, a poisoned prompt could
# rewrite arbitrary user files (e.g. ~/.bashrc, ~/.ssh/authorized_keys)
# as YAML.
# ---------------------------------------------------------------------------


class TestUpdateFieldPathContainment:
    def test_rejects_path_outside_allowed_roots(self, server_module, content_root: Path, tmp_path: Path):
        outside = tmp_path / "outside.md"
        outside.write_text("---\nstatus: Draft\n---\n", encoding="utf-8")

        result = json.loads(server_module.update_field(str(outside), "status", "PWNED"))

        assert "error" in result, "update_field must refuse paths outside roots"
        # File must remain untouched
        assert outside.read_text(encoding="utf-8") == "---\nstatus: Draft\n---\n"

    def test_rejects_traversal_through_content_root(self, server_module, content_root: Path, tmp_path: Path):
        """Path uses '..' to escape from inside content_root upward."""
        target = tmp_path / "evil.md"
        target.write_text("---\nstatus: Draft\n---\n", encoding="utf-8")

        traversal = content_root / "projects" / ".." / ".." / "evil.md"

        result = json.loads(server_module.update_field(str(traversal), "status", "PWNED"))

        assert "error" in result
        # File still has original content
        assert target.read_text(encoding="utf-8") == "---\nstatus: Draft\n---\n"

    def test_rejects_absolute_path_to_user_dotfile(self, server_module, content_root: Path, tmp_path: Path):
        """The exact attack from the audit: rewrite a dotfile via update_field."""
        evil_target = tmp_path / ".bashrc"
        original = "alias ll='ls -la'\n"
        evil_target.write_text(original, encoding="utf-8")

        result = json.loads(server_module.update_field(str(evil_target), "alias", "rm -rf /"))

        assert "error" in result
        assert evil_target.read_text(encoding="utf-8") == original

    def test_allows_path_inside_content_root(self, server_module, content_root: Path):
        """Control: legitimate paths within content_root still work."""
        target = content_root / "projects" / "my-book" / "README.md"
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text("---\nstatus: Draft\ntitle: My Book\n---\n", encoding="utf-8")

        result = json.loads(server_module.update_field(str(target), "status", "Revision"))

        assert result.get("success") is True
        assert "status: Revision" in target.read_text(encoding="utf-8")

    def test_allows_path_inside_authors_root(self, server_module, mock_config):
        """Author profiles must remain writable — they live under authors_root."""
        authors_root = Path(mock_config["paths"]["authors_root"])
        target = authors_root / "test-author" / "profile.md"
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text("---\nname: Test Author\n---\n", encoding="utf-8")

        result = json.loads(server_module.update_field(str(target), "name", "Updated Name"))

        assert result.get("success") is True
        assert "Updated Name" in target.read_text(encoding="utf-8")


# ---------------------------------------------------------------------------
# Audit H2 — resolve_path containment
# ---------------------------------------------------------------------------


class TestResolvePathContainment:
    def test_rejects_traversal_via_sub_path(self, server_module, content_root: Path):
        """`sub_path` must not allow escaping content_root via '..'."""
        # Enough '..' to walk past content_root + the temp dir prefix.
        result = json.loads(server_module.resolve_path("my-book", "chapters", "../../../../../../../../../etc/passwd"))
        assert "error" in result, "resolve_path must refuse traversal via sub_path"

    def test_rejects_absolute_sub_path(self, server_module, content_root: Path):
        """Absolute sub_path overrides the join — must be rejected."""
        result = json.loads(server_module.resolve_path("my-book", "chapters", "/etc/passwd"))
        assert "error" in result

    def test_rejects_traversal_via_component(self, server_module, content_root: Path):
        """`component` is user-controlled too — block '..' there as well."""
        result = json.loads(server_module.resolve_path("my-book", "../../../../../../../../../etc", "passwd"))
        assert "error" in result

    def test_rejects_unsafe_book_slug(self, server_module, content_root: Path):
        """Slug validation in resolve_project_path raises — caller must
        return a structured error, not let the exception escape."""
        # The slug validator raises ValueError; resolve_path bubbles it up
        # via the mcp framework. We verify the validator catches it.
        from tools.shared.paths import resolve_project_path

        config = {"paths": {"content_root": str(content_root)}}
        import pytest

        with pytest.raises(ValueError):
            resolve_project_path(config, "../escape")

    def test_allows_legitimate_path(self, server_module, content_root: Path):
        """Control: legitimate slug + component + sub_path resolves cleanly."""
        result = json.loads(server_module.resolve_path("my-book", "chapters", "01-intro"))
        assert "error" not in result
        parts = Path(result["path"]).parts
        assert parts[-3:] == ("my-book", "chapters", "01-intro")
