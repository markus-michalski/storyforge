"""Tests for the series_evolution enrichment in chapter_writing_brief
(Issue #205, D-3 of Epic #195).

Covers the integration: when a book is part of a series, every
``characters_present`` entry gets a ``series_evolution`` payload (or
``None`` for graceful degrade).
"""

from __future__ import annotations

from pathlib import Path

import pytest

from tools.state.chapter_writing_brief import build_chapter_writing_brief


def _write(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


@pytest.fixture
def content_root(tmp_path: Path) -> Path:
    return tmp_path / "content"


def _make_book(
    content_root: Path,
    book_slug: str,
    *,
    series: str = "",
    series_number: int = 0,
    book_category: str = "fiction",
) -> Path:
    book_root = content_root / "projects" / book_slug
    series_line = f"series: {series}\n" if series else ""
    series_n_line = f"series_number: {series_number}\n" if series_number else ""
    _write(
        book_root / "README.md",
        f"---\ntitle: {book_slug}\nbook_category: {book_category}\n{series_line}{series_n_line}---\n\nBook body.\n",
    )
    return book_root


def _make_chapter(
    book_root: Path,
    chapter_slug: str,
    *,
    pov: str = "",
    outline: str = "",
) -> None:
    pov_line = f"pov: {pov}\n" if pov else ""
    _write(
        book_root / "chapters" / chapter_slug / "README.md",
        f"---\nslug: {chapter_slug}\n{pov_line}---\n\n## Outline\n\n" + outline + "\n",
    )


def _make_character(
    book_root: Path,
    slug: str,
    *,
    name: str | None = None,
    role: str = "supporting",
) -> Path:
    char = book_root / "characters" / f"{slug}.md"
    _write(
        char,
        f"---\nname: {name or slug}\nslug: {slug}\nrole: {role}\n---\n\n# Profile\n",
    )
    return char


def _make_tracker(
    content_root: Path,
    series: str,
    slug: str,
    *,
    book_slug: str | None = None,
    recurs_in: list[str] | None = None,
    body: str = "",
) -> Path:
    chars_dir = content_root / "series" / series / "characters"
    chars_dir.mkdir(parents=True, exist_ok=True)
    book_slug_line = f"book_slug: {book_slug}\n" if book_slug else ""
    fm = (
        "---\n"
        f"name: {slug.title()}\n"
        f"slug: {slug}\n"
        f"{book_slug_line}"
        "role: supporting\n"
        "status: Profile\n"
        f"recurs_in: {recurs_in or ['B1', 'B2']}\n"
        "tracker_type: thin\n"
        "---\n\n"
    )
    path = chars_dir / f"{slug}.md"
    path.write_text(fm + body, encoding="utf-8")
    return path


class TestBriefSeriesEvolutionEnrichment:
    def test_enriches_when_book_in_series(self, content_root: Path):
        book_root = _make_book(
            content_root,
            "blood-and-binary-firelight",
            series="blood-and-binary",
            series_number=1,
        )
        _make_character(book_root, "kael", name="Kael", role="deuteragonist")
        _make_chapter(
            book_root,
            "01-opening",
            pov="kael",
            outline="Kael walks in. Caelan watches.",
        )
        _make_tracker(
            content_root,
            "blood-and-binary",
            "kael",
            recurs_in=["B1", "B2"],
            body=(
                "## Evolution per Band\n\n"
                "### B1 Firelight\n"
                "- **Start:** Cabin-Einsiedler.\n"
                "- **Ende:** Mit Theo zusammen.\n\n"
                "## Beziehungen ueber die Bande\n\n"
                "- **Theo:** Liebe.\n"
            ),
        )

        brief = build_chapter_writing_brief(
            book_root=book_root,
            book_slug="blood-and-binary-firelight",
            chapter_slug="01-opening",
            plugin_root=Path("/tmp"),
        )
        chars = {c["slug"]: c for c in brief["characters_present"]}
        assert "kael" in chars
        evo = chars["kael"]["series_evolution"]
        assert evo is not None
        assert evo["tracker_slug"] == "kael"
        assert "Mit Theo zusammen" in evo["current_book_plan"]
        assert "**Theo:**" in evo["relationships_evolution"]
        # B1 has no prev — empty string.
        assert evo["previous_book_end"] == ""

    def test_b2_chapter_gets_prev_book_end(self, content_root: Path):
        book_root = _make_book(
            content_root,
            "blood-and-binary-moonrise",
            series="blood-and-binary",
            series_number=2,
        )
        _make_character(book_root, "kael", role="deuteragonist")
        _make_chapter(book_root, "01-opening", pov="kael", outline="Kael grieves.")
        _make_tracker(
            content_root,
            "blood-and-binary",
            "kael",
            recurs_in=["B1", "B2"],
            body=(
                "## Evolution per Band\n\n"
                "### B1 Firelight\n"
                "- **Ende:** Mit Theo zusammen, Sera tot.\n\n"
                "### B2 Moonrise (geplant)\n"
                "- Trauernder Bruder.\n"
                "- Macht-Asymmetrie kippt.\n"
            ),
        )
        brief = build_chapter_writing_brief(
            book_root=book_root,
            book_slug="blood-and-binary-moonrise",
            chapter_slug="01-opening",
            plugin_root=Path("/tmp"),
        )
        evo = brief["characters_present"][0]["series_evolution"]
        assert evo is not None
        assert "Mit Theo zusammen" in evo["previous_book_end"]
        assert "Trauernder Bruder" in evo["current_book_plan"]
        assert evo["current_book_phase"] == "B2 Moonrise (geplant)"

    def test_resolves_via_book_slug_field(self, content_root: Path):
        # Book file is caelan.md, tracker is king-caelan.md with book_slug.
        book_root = _make_book(
            content_root,
            "blood-and-binary-firelight",
            series="blood-and-binary",
            series_number=1,
        )
        _make_character(book_root, "caelan", name="Caelan", role="supporting")
        _make_chapter(book_root, "01-opening", pov="caelan", outline="Caelan rules.")
        _make_tracker(
            content_root,
            "blood-and-binary",
            "king-caelan",
            book_slug="caelan",
            recurs_in=["B1", "B2"],
            body=("## Evolution per Band\n\n### B1\n- **Ende:** Caelan trauert.\n"),
        )
        brief = build_chapter_writing_brief(
            book_root=book_root,
            book_slug="blood-and-binary-firelight",
            chapter_slug="01-opening",
            plugin_root=Path("/tmp"),
        )
        evo = brief["characters_present"][0]["series_evolution"]
        assert evo is not None
        assert evo["tracker_slug"] == "king-caelan"
        assert "Caelan trauert" in evo["current_book_plan"]


class TestBriefSeriesEvolutionGracefulDegrade:
    def test_none_when_book_not_in_series(self, content_root: Path):
        book_root = _make_book(content_root, "standalone-novel")
        _make_character(book_root, "alice")
        _make_chapter(book_root, "01-start", pov="alice", outline="Alice walks.")

        brief = build_chapter_writing_brief(
            book_root=book_root,
            book_slug="standalone-novel",
            chapter_slug="01-start",
            plugin_root=Path("/tmp"),
        )
        assert brief["characters_present"][0]["series_evolution"] is None

    def test_none_when_no_tracker_for_char(self, content_root: Path):
        book_root = _make_book(
            content_root,
            "blood-and-binary-firelight",
            series="blood-and-binary",
            series_number=1,
        )
        _make_character(book_root, "kael", role="deuteragonist")
        _make_chapter(book_root, "01-opening", pov="kael", outline="Kael walks.")
        # Tracker for someone else, not kael.
        _make_tracker(
            content_root,
            "blood-and-binary",
            "tristan",
            recurs_in=["B1", "B2"],
            body="## Evolution per Band\n\n### B1\n- **Ende:** End.\n",
        )
        brief = build_chapter_writing_brief(
            book_root=book_root,
            book_slug="blood-and-binary-firelight",
            chapter_slug="01-opening",
            plugin_root=Path("/tmp"),
        )
        # Kael has no matching tracker — None.
        assert brief["characters_present"][0]["series_evolution"] is None

    def test_none_when_series_dir_missing(self, content_root: Path):
        # Book declares series but the series dir doesn't exist.
        book_root = _make_book(
            content_root,
            "ghost-book",
            series="ghost-series",
            series_number=1,
        )
        _make_character(book_root, "ghost")
        _make_chapter(book_root, "01-start", pov="ghost", outline="Ghost walks.")
        brief = build_chapter_writing_brief(
            book_root=book_root,
            book_slug="ghost-book",
            chapter_slug="01-start",
            plugin_root=Path("/tmp"),
        )
        assert brief["characters_present"][0]["series_evolution"] is None

    def test_field_always_present_on_each_char(self, content_root: Path):
        # Even when no series, every char dict has the key — downstream
        # consumers can rely on its presence.
        book_root = _make_book(content_root, "standalone")
        _make_character(book_root, "alice")
        _make_character(book_root, "bob")
        _make_chapter(book_root, "01-start", pov="alice", outline="Alice meets Bob.")
        brief = build_chapter_writing_brief(
            book_root=book_root,
            book_slug="standalone",
            chapter_slug="01-start",
            plugin_root=Path("/tmp"),
        )
        for char in brief["characters_present"]:
            assert "series_evolution" in char
            assert char["series_evolution"] is None
