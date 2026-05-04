"""Tests for ``tools.state.loaders.pov_inventory`` — Issue #157.

Deterministic extraction of the POV character's physical inventory at
the start of a chapter. Priority: frontmatter > timeline_regex >
draft_heuristic > none. Surfaces structured items with source pointers
so the chapter-writer can verify rather than invent.
"""

from __future__ import annotations

from pathlib import Path

from tools.state.loaders.pov_inventory import extract_pov_inventory


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_book(tmp_path: Path) -> Path:
    book = tmp_path / "test-book"
    (book / "chapters").mkdir(parents=True)
    (book / "characters").mkdir()
    (book / "README.md").write_text(
        '---\ntitle: "Test Book"\n---\n\n# Test Book\n',
        encoding="utf-8",
    )
    return book


def _add_character(
    book: Path,
    slug: str,
    *,
    name: str,
    current_inventory: list[str] | None = None,
) -> Path:
    body = f'---\nname: "{name}"\nrole: "protagonist"\n'
    if current_inventory is not None:
        body += "current_inventory:\n"
        for item in current_inventory:
            body += f"  - {item}\n"
    body += "---\n\n# " + name + "\n"
    path = book / "characters" / f"{slug}.md"
    path.write_text(body, encoding="utf-8")
    return path


def _add_chapter(
    book: Path,
    slug: str,
    *,
    number: int,
    title: str,
    status: str = "Draft",
    body: str = "",
    draft_body: str | None = None,
) -> Path:
    chapter = book / "chapters" / slug
    chapter.mkdir(parents=True)
    readme = (
        f'---\ntitle: "{title}"\nnumber: {number}\nstatus: "{status}"\n'
        f"---\n\n# {title}\n\n{body}"
    )
    (chapter / "README.md").write_text(readme, encoding="utf-8")
    if draft_body is not None:
        (chapter / "draft.md").write_text(draft_body, encoding="utf-8")
    return chapter


# ---------------------------------------------------------------------------
# Frontmatter source
# ---------------------------------------------------------------------------


class TestFrontmatterSource:
    def test_reads_current_inventory_list(self, tmp_path: Path) -> None:
        book = _make_book(tmp_path)
        _add_character(
            book,
            "theo",
            name="Theo",
            current_inventory=["compass", "silver knife", "no-signal phone"],
        )
        _add_chapter(book, "27-the-meet", number=27, title="The Meet")

        result = extract_pov_inventory(book, "Theo", "27-the-meet")

        assert result["extraction_method"] == "frontmatter"
        items = [i["item"] for i in result["items"]]
        assert "compass" in items
        assert "silver knife" in items
        assert "no-signal phone" in items
        # Source pointer is character-scoped for frontmatter.
        for entry in result["items"]:
            assert entry["source"].startswith("character:theo:frontmatter")
        # as_of is None for frontmatter — it's not chapter-tied.
        assert result["as_of"] is None
        assert result["warnings"] == []

    def test_frontmatter_beats_timeline(self, tmp_path: Path) -> None:
        """Frontmatter is the most explicit source — it wins even when a
        more-recent timeline beat exists."""
        book = _make_book(tmp_path)
        _add_character(
            book,
            "theo",
            name="Theo",
            current_inventory=["mission jacket", "compass"],
        )
        # Timeline beat in current chapter would otherwise be picked up.
        _add_chapter(
            book,
            "27-the-meet",
            number=27,
            title="The Meet",
            body=(
                "## Chapter Timeline\n\n"
                "- ~12:55 Tactical inventory: knife, rope, headlamp.\n"
            ),
        )

        result = extract_pov_inventory(book, "Theo", "27-the-meet")

        assert result["extraction_method"] == "frontmatter"
        items = [i["item"] for i in result["items"]]
        assert "mission jacket" in items
        assert "knife" not in items  # timeline was not consulted

    def test_empty_frontmatter_list_falls_through(self, tmp_path: Path) -> None:
        """An explicit empty list signals 'no frontmatter data', not
        'character carries nothing' — the loader should fall through to
        the next source."""
        book = _make_book(tmp_path)
        _add_character(book, "theo", name="Theo", current_inventory=[])
        _add_chapter(
            book,
            "27-the-meet",
            number=27,
            title="The Meet",
            body=(
                "## Chapter Timeline\n\n"
                "- ~12:55 inventory: compass, knife.\n"
            ),
        )

        result = extract_pov_inventory(book, "Theo", "27-the-meet")

        assert result["extraction_method"] == "timeline_regex"


# ---------------------------------------------------------------------------
# Timeline regex source
# ---------------------------------------------------------------------------


class TestTimelineRegexSource:
    def test_extracts_inventory_from_current_chapter_readme(
        self, tmp_path: Path
    ) -> None:
        book = _make_book(tmp_path)
        _add_character(book, "theo", name="Theo")
        _add_chapter(
            book,
            "27-the-meet",
            number=27,
            title="The Meet",
            body=(
                "## Chapter Timeline\n\n"
                "- ~12:55 Tactical inventory: compass, silver knife, no-signal phone, half a power bar.\n"
            ),
        )

        result = extract_pov_inventory(book, "Theo", "27-the-meet")

        assert result["extraction_method"] == "timeline_regex"
        items = [i["item"] for i in result["items"]]
        assert "compass" in items
        assert "silver knife" in items
        assert "no-signal phone" in items
        assert "half a power bar" in items
        assert result["as_of"] == "27-the-meet"
        # Source pointer carries the time anchor when present.
        assert all(
            entry["source"].startswith("chapter:27-the-meet:timeline:")
            for entry in result["items"]
        )

    def test_falls_back_to_prior_review_chapter(self, tmp_path: Path) -> None:
        book = _make_book(tmp_path)
        _add_character(book, "theo", name="Theo")
        _add_chapter(
            book,
            "26-the-basement",
            number=26,
            title="The Basement",
            status="review",
            body=(
                "## Chapter Timeline\n\n"
                "- ~12:55 Tactical inventory: compass, silver knife, no-signal phone.\n"
            ),
        )
        # Current chapter has no inventory beat.
        _add_chapter(book, "27-the-meet", number=27, title="The Meet")

        result = extract_pov_inventory(book, "Theo", "27-the-meet")

        assert result["extraction_method"] == "timeline_regex"
        assert result["as_of"] == "26-the-basement"
        items = [i["item"] for i in result["items"]]
        assert "compass" in items

    def test_recognizes_alternate_keywords(self, tmp_path: Path) -> None:
        """`gear:`, `loadout:`, `carrying:` are all valid inventory beats."""
        book = _make_book(tmp_path)
        _add_character(book, "theo", name="Theo")
        _add_chapter(
            book,
            "27-the-meet",
            number=27,
            title="The Meet",
            body=(
                "## Chapter Timeline\n\n"
                "- ~12:55 Gear: backpack, headlamp, water bottle.\n"
            ),
        )

        result = extract_pov_inventory(book, "Theo", "27-the-meet")

        assert result["extraction_method"] == "timeline_regex"
        items = [i["item"] for i in result["items"]]
        assert "backpack" in items
        assert "headlamp" in items
        assert "water bottle" in items

    def test_picks_most_recent_inventory_when_multiple_in_chapter(
        self, tmp_path: Path
    ) -> None:
        """Two inventory beats in the same chapter — the later one wins."""
        book = _make_book(tmp_path)
        _add_character(book, "theo", name="Theo")
        _add_chapter(
            book,
            "27-the-meet",
            number=27,
            title="The Meet",
            body=(
                "## Chapter Timeline\n\n"
                "- ~10:00 inventory: compass, knife.\n"
                "- ~14:30 inventory: compass, knife, headlamp, water.\n"
            ),
        )

        result = extract_pov_inventory(book, "Theo", "27-the-meet")

        assert result["extraction_method"] == "timeline_regex"
        items = [i["item"] for i in result["items"]]
        assert "headlamp" in items
        assert "water" in items

    def test_only_review_or_later_chapters_are_scanned_for_priors(
        self, tmp_path: Path
    ) -> None:
        """Outline / Draft chapters before the current one are NOT scanned —
        the brief only trusts review-or-later state for priors. The current
        chapter itself is always scanned regardless of status."""
        book = _make_book(tmp_path)
        _add_character(book, "theo", name="Theo")
        # Prior chapter at Draft status — should NOT contribute.
        _add_chapter(
            book,
            "25-the-cellar",
            number=25,
            title="The Cellar",
            status="Draft",
            body=(
                "## Chapter Timeline\n\n"
                "- ~09:00 inventory: nothing-relevant.\n"
            ),
        )
        # Prior chapter at review — SHOULD contribute.
        _add_chapter(
            book,
            "26-the-basement",
            number=26,
            title="The Basement",
            status="review",
            body=(
                "## Chapter Timeline\n\n"
                "- ~12:55 inventory: compass, silver knife.\n"
            ),
        )
        _add_chapter(book, "27-the-meet", number=27, title="The Meet")

        result = extract_pov_inventory(book, "Theo", "27-the-meet")

        assert result["extraction_method"] == "timeline_regex"
        assert result["as_of"] == "26-the-basement"
        items = [i["item"] for i in result["items"]]
        assert "nothing-relevant" not in items
        assert "compass" in items


# ---------------------------------------------------------------------------
# Draft heuristic source
# ---------------------------------------------------------------------------


class TestDraftHeuristicSource:
    def test_extracts_carried_items_from_last_review_draft(
        self, tmp_path: Path
    ) -> None:
        """When neither frontmatter nor structured timeline beat is
        available, scan the most recent draft for `carried` / `had X in
        his pocket` patterns."""
        book = _make_book(tmp_path)
        _add_character(book, "theo", name="Theo")
        _add_chapter(
            book,
            "26-the-basement",
            number=26,
            title="The Basement",
            status="review",
            draft_body=(
                "# The Basement\n\n"
                "Theo carried a compass and a silver knife. "
                "He had a no-signal phone in his pocket.\n"
            ),
        )
        _add_chapter(book, "27-the-meet", number=27, title="The Meet")

        result = extract_pov_inventory(book, "Theo", "27-the-meet")

        assert result["extraction_method"] == "draft_heuristic"
        assert result["as_of"] == "26-the-basement"
        # Items list is non-empty and source points at the draft.
        assert len(result["items"]) >= 1
        for entry in result["items"]:
            assert entry["source"] == "chapter:26-the-basement:draft"


# ---------------------------------------------------------------------------
# None / no data
# ---------------------------------------------------------------------------


class TestNoDataFound:
    def test_no_inventory_anywhere_returns_method_none_with_warning(
        self, tmp_path: Path
    ) -> None:
        book = _make_book(tmp_path)
        _add_character(book, "theo", name="Theo")
        _add_chapter(book, "27-the-meet", number=27, title="The Meet")

        result = extract_pov_inventory(book, "Theo", "27-the-meet")

        assert result["extraction_method"] == "none"
        assert result["items"] == []
        assert result["as_of"] is None
        assert result["warnings"]
        assert "no inventory beat found" in result["warnings"][0].lower()

    def test_missing_pov_character_file_returns_method_none(
        self, tmp_path: Path
    ) -> None:
        """POV character has no profile on disk — the extractor still
        scans timelines but no frontmatter source is available."""
        book = _make_book(tmp_path)
        # No character file added.
        _add_chapter(book, "27-the-meet", number=27, title="The Meet")

        result = extract_pov_inventory(book, "Ghost", "27-the-meet")

        assert result["extraction_method"] == "none"
        assert result["items"] == []

    def test_empty_pov_character_string_returns_method_none(
        self, tmp_path: Path
    ) -> None:
        book = _make_book(tmp_path)
        _add_chapter(book, "27-the-meet", number=27, title="The Meet")

        result = extract_pov_inventory(book, "", "27-the-meet")

        assert result["extraction_method"] == "none"
        assert result["items"] == []


# ---------------------------------------------------------------------------
# Schema invariants
# ---------------------------------------------------------------------------


class TestSchemaInvariants:
    def test_result_has_required_keys(self, tmp_path: Path) -> None:
        book = _make_book(tmp_path)
        _add_chapter(book, "27-the-meet", number=27, title="The Meet")

        result = extract_pov_inventory(book, "Theo", "27-the-meet")

        for key in ("items", "as_of", "extraction_method", "warnings"):
            assert key in result

    def test_extraction_method_is_one_of_four_values(
        self, tmp_path: Path
    ) -> None:
        book = _make_book(tmp_path)
        _add_chapter(book, "27-the-meet", number=27, title="The Meet")

        result = extract_pov_inventory(book, "Theo", "27-the-meet")
        assert result["extraction_method"] in (
            "frontmatter",
            "timeline_regex",
            "draft_heuristic",
            "none",
        )

    def test_each_item_has_item_and_source_keys(self, tmp_path: Path) -> None:
        book = _make_book(tmp_path)
        _add_character(
            book,
            "theo",
            name="Theo",
            current_inventory=["compass"],
        )
        _add_chapter(book, "27-the-meet", number=27, title="The Meet")

        result = extract_pov_inventory(book, "Theo", "27-the-meet")
        for entry in result["items"]:
            assert "item" in entry
            assert "source" in entry
            assert isinstance(entry["item"], str)
            assert isinstance(entry["source"], str)
