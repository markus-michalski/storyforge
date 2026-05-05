"""Tests for ``tools.state.loaders.pov_state`` — Issue #160.

Covers:
- All 4 categories × all 3 extraction methods (frontmatter / timeline_regex /
  draft_heuristic) + the 'none' fallback
- Partial coverage (categories can use different methods independently)
- Outline-aware warnings (warning only when outline references the missing cat)
- as_of tracks the most-recent contributing chapter
- Brief integration: pov_character_state key present and JSON-serializable
"""

from __future__ import annotations

import json as _json
from pathlib import Path

from tools.state.loaders.pov_state import extract_pov_state


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _book(tmp: Path) -> Path:
    root = tmp / "my-book"
    (root / "chapters").mkdir(parents=True)
    (root / "characters").mkdir()
    return root


def _char(root: Path, slug: str, **fields) -> Path:
    """Write a character file with frontmatter fields."""
    fm_lines = "\n".join(
        f"{k}:\n" + "\n".join(f"- {v}" for v in vals)
        for k, vals in fields.items()
        if isinstance(vals, list)
    )
    path = root / "characters" / f"{slug}.md"
    path.write_text(f"---\nname: {slug}\n{fm_lines}\n---\nBody.\n", encoding="utf-8")
    return path


def _chapter(root: Path, slug: str, *, number: int, status: str = "Review", timeline: str = "", draft: str = "") -> Path:
    ch = root / "chapters" / slug
    ch.mkdir(parents=True, exist_ok=True)
    readme = (
        f"---\nnumber: {number}\nstatus: {status!r}\n---\n"
        f"## Chapter Timeline\n\n{timeline}\n"
    )
    (ch / "README.md").write_text(readme, encoding="utf-8")
    if draft:
        (ch / "draft.md").write_text(f"---\n---\n{draft}", encoding="utf-8")
    return ch


# ---------------------------------------------------------------------------
# Schema / contract
# ---------------------------------------------------------------------------


class TestPovStateSchema:
    def test_returns_all_required_keys(self, tmp_path: Path):
        root = _book(tmp_path)
        _chapter(root, "01-intro", number=1)
        result = extract_pov_state(root, "Theo", "01-intro")
        for key in ("clothing", "injuries", "altered_states", "environmental_limiters",
                    "as_of", "extraction_methods", "warnings"):
            assert key in result, f"missing key: {key}"

    def test_all_categories_present_in_extraction_methods(self, tmp_path: Path):
        root = _book(tmp_path)
        _chapter(root, "01-intro", number=1)
        methods = extract_pov_state(root, "Theo", "01-intro")["extraction_methods"]
        for cat in ("clothing", "injuries", "altered_states", "environmental_limiters"):
            assert cat in methods

    def test_category_items_are_dicts_with_item_and_source(self, tmp_path: Path):
        root = _book(tmp_path)
        _chapter(root, "01-intro", number=1, timeline="- ~14:00 clothing: tactical boots, mission jacket.")
        _char(root, "theo")
        result = extract_pov_state(root, "Theo", "01-intro")
        for item in result["clothing"]:
            assert "item" in item and "source" in item

    def test_result_is_json_serializable(self, tmp_path: Path):
        root = _book(tmp_path)
        _chapter(root, "01-intro", number=1, timeline="- ~12:00 clothing: boots.")
        result = extract_pov_state(root, "Theo", "01-intro")
        _json.dumps(result)


# ---------------------------------------------------------------------------
# Frontmatter extraction (per category)
# ---------------------------------------------------------------------------


class TestFrontmatterExtraction:
    def test_clothing_from_frontmatter(self, tmp_path: Path):
        root = _book(tmp_path)
        _chapter(root, "01-intro", number=1)
        _char(root, "theo", current_clothing=["tactical boots", "mission jacket"])

        result = extract_pov_state(root, "Theo", "01-intro")

        assert result["extraction_methods"]["clothing"] == "frontmatter"
        items = [i["item"] for i in result["clothing"]]
        assert "tactical boots" in items
        assert "mission jacket" in items

    def test_injuries_from_frontmatter(self, tmp_path: Path):
        root = _book(tmp_path)
        _chapter(root, "01-intro", number=1)
        _char(root, "theo", current_injuries=["bandaged left hand"])

        result = extract_pov_state(root, "Theo", "01-intro")

        assert result["extraction_methods"]["injuries"] == "frontmatter"
        assert result["injuries"][0]["item"] == "bandaged left hand"

    def test_altered_states_from_frontmatter(self, tmp_path: Path):
        root = _book(tmp_path)
        _chapter(root, "01-intro", number=1)
        _char(root, "theo", altered_states=["running on 3 hours sleep"])

        result = extract_pov_state(root, "Theo", "01-intro")

        assert result["extraction_methods"]["altered_states"] == "frontmatter"
        assert result["altered_states"][0]["item"] == "running on 3 hours sleep"

    def test_environmental_limiters_from_frontmatter(self, tmp_path: Path):
        root = _book(tmp_path)
        _chapter(root, "01-intro", number=1)
        _char(root, "theo", environmental_limiters=["headlamp on", "hearing dampened by helmet"])

        result = extract_pov_state(root, "Theo", "01-intro")

        assert result["extraction_methods"]["environmental_limiters"] == "frontmatter"
        assert len(result["environmental_limiters"]) == 2

    def test_frontmatter_source_pointer_includes_field_name(self, tmp_path: Path):
        root = _book(tmp_path)
        _chapter(root, "01-intro", number=1)
        _char(root, "theo", current_clothing=["boots"])

        result = extract_pov_state(root, "Theo", "01-intro")

        source = result["clothing"][0]["source"]
        assert "frontmatter" in source
        assert "current_clothing" in source


# ---------------------------------------------------------------------------
# Timeline regex extraction (per category)
# ---------------------------------------------------------------------------


class TestTimelineRegexExtraction:
    def test_clothing_from_timeline(self, tmp_path: Path):
        root = _book(tmp_path)
        _chapter(root, "01-intro", number=1, timeline="- ~14:00 clothing: tactical boots, mission jacket.")
        _char(root, "theo")

        result = extract_pov_state(root, "Theo", "01-intro")

        assert result["extraction_methods"]["clothing"] == "timeline_regex"
        items = [i["item"] for i in result["clothing"]]
        assert "tactical boots" in items

    def test_wearing_keyword_triggers_clothing(self, tmp_path: Path):
        root = _book(tmp_path)
        _chapter(root, "01-intro", number=1, timeline="- ~10:00 wearing: winter coat, gloves.")

        result = extract_pov_state(root, "Theo", "01-intro")

        assert result["extraction_methods"]["clothing"] == "timeline_regex"

    def test_injuries_from_timeline(self, tmp_path: Path):
        root = _book(tmp_path)
        _chapter(root, "01-intro", number=1, timeline="- ~21:30 injury: bandaged left hand from fight.")
        _char(root, "theo")

        result = extract_pov_state(root, "Theo", "01-intro")

        assert result["extraction_methods"]["injuries"] == "timeline_regex"
        assert result["injuries"][0]["item"] == "bandaged left hand from fight"

    def test_wound_keyword_triggers_injuries(self, tmp_path: Path):
        root = _book(tmp_path)
        _chapter(root, "01-intro", number=1, timeline="- ~15:00 wound: deep cut on forearm.")

        result = extract_pov_state(root, "Theo", "01-intro")

        assert result["extraction_methods"]["injuries"] == "timeline_regex"

    def test_altered_states_from_timeline(self, tmp_path: Path):
        root = _book(tmp_path)
        _chapter(root, "01-intro", number=1, timeline="- ~08:00 fatigue: running on 3 hours sleep.")

        result = extract_pov_state(root, "Theo", "01-intro")

        assert result["extraction_methods"]["altered_states"] == "timeline_regex"
        assert "3 hours sleep" in result["altered_states"][0]["item"]

    def test_state_keyword_triggers_altered_states(self, tmp_path: Path):
        root = _book(tmp_path)
        _chapter(root, "01-intro", number=1, timeline="- ~09:00 state: adrenaline crash, hands shaking.")

        result = extract_pov_state(root, "Theo", "01-intro")

        assert result["extraction_methods"]["altered_states"] == "timeline_regex"

    def test_environmental_limiter_from_timeline(self, tmp_path: Path):
        root = _book(tmp_path)
        _chapter(root, "01-intro", number=1, timeline="- ~14:30 limiter: headlamp on, hearing dampened by helmet.")

        result = extract_pov_state(root, "Theo", "01-intro")

        assert result["extraction_methods"]["environmental_limiters"] == "timeline_regex"

    def test_masked_keyword_triggers_limiter(self, tmp_path: Path):
        root = _book(tmp_path)
        _chapter(root, "01-intro", number=1, timeline="- ~14:30 masked: respirator on.")

        result = extract_pov_state(root, "Theo", "01-intro")

        assert result["extraction_methods"]["environmental_limiters"] == "timeline_regex"

    def test_timeline_source_includes_time_anchor(self, tmp_path: Path):
        root = _book(tmp_path)
        _chapter(root, "01-intro", number=1, timeline="- ~21:30 injury: bandaged hand.")

        result = extract_pov_state(root, "Theo", "01-intro")

        assert "~21:30" in result["injuries"][0]["source"]

    def test_latest_timeline_beat_wins(self, tmp_path: Path):
        root = _book(tmp_path)
        _chapter(
            root, "01-intro", number=1,
            timeline=(
                "- ~10:00 clothing: old coat.\n"
                "- ~15:00 clothing: new jacket, boots.\n"
            ),
        )

        result = extract_pov_state(root, "Theo", "01-intro")

        items = [i["item"] for i in result["clothing"]]
        assert "new jacket" in items
        assert "old coat" not in items


# ---------------------------------------------------------------------------
# Draft heuristic extraction (per category)
# ---------------------------------------------------------------------------


class TestDraftHeuristicExtraction:
    def test_wore_triggers_clothing_heuristic(self, tmp_path: Path):
        root = _book(tmp_path)
        _chapter(root, "01-intro", number=1, draft="He wore a heavy tactical jacket that morning.")

        result = extract_pov_state(root, "Theo", "01-intro")

        assert result["extraction_methods"]["clothing"] == "draft_heuristic"

    def test_limped_triggers_injury_heuristic(self, tmp_path: Path):
        root = _book(tmp_path)
        _chapter(root, "01-intro", number=1, draft="She limped down the corridor, favouring her right leg.")

        result = extract_pov_state(root, "Theo", "01-intro")

        assert result["extraction_methods"]["injuries"] == "draft_heuristic"

    def test_exhausted_triggers_altered_state_heuristic(self, tmp_path: Path):
        root = _book(tmp_path)
        _chapter(root, "01-intro", number=1, draft="He was exhausted, barely keeping his eyes open.")

        result = extract_pov_state(root, "Theo", "01-intro")

        assert result["extraction_methods"]["altered_states"] == "draft_heuristic"

    def test_mask_on_triggers_limiter_heuristic(self, tmp_path: Path):
        root = _book(tmp_path)
        _chapter(root, "01-intro", number=1, draft="She kept the mask on as she moved through the smoke.")

        result = extract_pov_state(root, "Theo", "01-intro")

        assert result["extraction_methods"]["environmental_limiters"] == "draft_heuristic"

    def test_draft_source_pointer_contains_chapter_and_draft(self, tmp_path: Path):
        root = _book(tmp_path)
        _chapter(root, "01-intro", number=1, draft="He wore the mission jacket.")

        result = extract_pov_state(root, "Theo", "01-intro")

        source = result["clothing"][0]["source"]
        assert "01-intro" in source
        assert "draft" in source


# ---------------------------------------------------------------------------
# None fallback
# ---------------------------------------------------------------------------


class TestNoneFallback:
    def test_no_source_yields_none_method(self, tmp_path: Path):
        root = _book(tmp_path)
        _chapter(root, "01-intro", number=1)

        result = extract_pov_state(root, "Theo", "01-intro")

        for cat in ("clothing", "injuries", "altered_states", "environmental_limiters"):
            assert result["extraction_methods"][cat] == "none"
            assert result[cat] == []

    def test_no_warning_when_outline_silent(self, tmp_path: Path):
        root = _book(tmp_path)
        _chapter(root, "01-intro", number=1)

        result = extract_pov_state(root, "Theo", "01-intro", outline_text="Theo walks into the room.")

        assert result["warnings"] == []

    def test_warning_when_outline_mentions_injury_but_no_source(self, tmp_path: Path):
        root = _book(tmp_path)
        _chapter(root, "01-intro", number=1)

        result = extract_pov_state(
            root, "Theo", "01-intro",
            outline_text="She stumbled and grabbed her ribs, clearly hurt.",
        )

        assert any("injuries" in w for w in result["warnings"])

    def test_warning_when_outline_mentions_clothing_but_no_source(self, tmp_path: Path):
        root = _book(tmp_path)
        _chapter(root, "01-intro", number=1)

        result = extract_pov_state(
            root, "Theo", "01-intro",
            outline_text="He notices his boots are soaking wet.",
        )

        assert any("clothing" in w for w in result["warnings"])

    def test_no_warning_when_outline_mentions_injury_and_source_exists(self, tmp_path: Path):
        root = _book(tmp_path)
        _chapter(root, "01-intro", number=1, timeline="- ~21:30 injury: bruised ribs.")

        result = extract_pov_state(
            root, "Theo", "01-intro",
            outline_text="She grabbed her ribs.",
        )

        assert not any("injuries" in w for w in result["warnings"])


# ---------------------------------------------------------------------------
# Partial coverage — categories use different methods independently
# ---------------------------------------------------------------------------


class TestPartialCoverage:
    def test_clothing_frontmatter_injuries_timeline_others_none(self, tmp_path: Path):
        root = _book(tmp_path)
        _chapter(root, "01-intro", number=1, timeline="- ~21:30 injury: bruised ribs.")
        _char(root, "theo", current_clothing=["tactical boots"])

        result = extract_pov_state(root, "Theo", "01-intro")

        assert result["extraction_methods"]["clothing"] == "frontmatter"
        assert result["extraction_methods"]["injuries"] == "timeline_regex"
        assert result["extraction_methods"]["altered_states"] == "none"
        assert result["extraction_methods"]["environmental_limiters"] == "none"

    def test_each_category_carries_its_own_source_pointer(self, tmp_path: Path):
        root = _book(tmp_path)
        _chapter(root, "01-intro", number=1, timeline="- ~21:30 injury: bruised ribs.")
        _char(root, "theo", current_clothing=["boots"])

        result = extract_pov_state(root, "Theo", "01-intro")

        assert "frontmatter" in result["clothing"][0]["source"]
        assert "timeline" in result["injuries"][0]["source"]

    def test_brief_still_ships_with_partial_data(self, tmp_path: Path):
        root = _book(tmp_path)
        _chapter(root, "01-intro", number=1, timeline="- ~10:00 clothing: jacket.")

        result = extract_pov_state(root, "Theo", "01-intro")

        assert isinstance(result["clothing"], list)
        assert len(result["clothing"]) > 0
        assert result["injuries"] == []


# ---------------------------------------------------------------------------
# as_of tracking
# ---------------------------------------------------------------------------


class TestAsOf:
    def test_as_of_none_when_all_frontmatter(self, tmp_path: Path):
        root = _book(tmp_path)
        _chapter(root, "01-intro", number=1)
        _char(root, "theo", current_clothing=["boots"], current_injuries=["bruised ribs"])

        result = extract_pov_state(root, "Theo", "01-intro")

        assert result["as_of"] is None

    def test_as_of_set_when_chapter_data_used(self, tmp_path: Path):
        root = _book(tmp_path)
        _chapter(root, "27-the-meet", number=27, timeline="- ~14:30 limiter: helmet on.")

        result = extract_pov_state(root, "Theo", "27-the-meet")

        assert result["as_of"] == "27-the-meet"

    def test_as_of_none_when_all_none(self, tmp_path: Path):
        root = _book(tmp_path)
        _chapter(root, "01-intro", number=1)

        result = extract_pov_state(root, "Theo", "01-intro")

        assert result["as_of"] is None


# ---------------------------------------------------------------------------
# Prior chapter scan
# ---------------------------------------------------------------------------


class TestPriorChapterScan:
    def _make_reviewed(self, root: Path, slug: str, number: int, timeline: str = "") -> Path:
        return _chapter(root, slug, number=number, status="Review", timeline=timeline)

    def test_falls_back_to_prior_reviewed_chapter(self, tmp_path: Path):
        root = _book(tmp_path)
        self._make_reviewed(root, "26-the-basement", 26, timeline="- ~12:55 injury: bruised ribs.")
        _chapter(root, "27-the-meet", number=27)

        result = extract_pov_state(root, "Theo", "27-the-meet")

        assert result["extraction_methods"]["injuries"] == "timeline_regex"
        assert "26-the-basement" in result["injuries"][0]["source"]

    def test_current_chapter_beats_prior(self, tmp_path: Path):
        root = _book(tmp_path)
        self._make_reviewed(root, "26-the-basement", 26, timeline="- ~12:55 injury: old wound.")
        _chapter(root, "27-the-meet", number=27, timeline="- ~14:00 injury: new bruise.")

        result = extract_pov_state(root, "Theo", "27-the-meet")

        assert "27-the-meet" in result["injuries"][0]["source"]
        assert "new bruise" in result["injuries"][0]["item"]

    def test_draft_chapters_not_included_in_prior_scan(self, tmp_path: Path):
        root = _book(tmp_path)
        _chapter(root, "26-in-draft", number=26, status="Draft", timeline="- ~12:55 injury: bruised ribs.")
        _chapter(root, "27-the-meet", number=27)

        result = extract_pov_state(root, "Theo", "27-the-meet")

        assert result["extraction_methods"]["injuries"] == "none"


# ---------------------------------------------------------------------------
# Brief integration
# ---------------------------------------------------------------------------


class TestBriefIntegration:
    def test_brief_includes_pov_character_state_key(self, tmp_path: Path):
        from tests.state.test_chapter_writing_brief import _setup_book, _make_chapter, _add_character
        from tools.state.chapter_writing_brief import build_chapter_writing_brief

        book, plugin_root = _setup_book(tmp_path)
        _make_chapter(book, "01-intro", number=1, title="Intro", pov="Theo")
        _add_character(book, "theo", name="Theo")

        brief = build_chapter_writing_brief(
            book_root=book,
            book_slug="test-book",
            chapter_slug="01-intro",
            plugin_root=plugin_root,
        )

        assert "pov_character_state" in brief

    def test_brief_state_schema_has_required_keys(self, tmp_path: Path):
        from tests.state.test_chapter_writing_brief import _setup_book, _make_chapter, _add_character
        from tools.state.chapter_writing_brief import build_chapter_writing_brief

        book, plugin_root = _setup_book(tmp_path)
        _make_chapter(book, "01-intro", number=1, title="Intro", pov="Theo")
        _add_character(book, "theo", name="Theo")

        brief = build_chapter_writing_brief(
            book_root=book,
            book_slug="test-book",
            chapter_slug="01-intro",
            plugin_root=plugin_root,
        )
        state = brief["pov_character_state"]
        for key in ("clothing", "injuries", "altered_states", "environmental_limiters",
                    "as_of", "extraction_methods", "warnings"):
            assert key in state

    def test_brief_state_is_json_serializable(self, tmp_path: Path):
        from tests.state.test_chapter_writing_brief import _setup_book, _make_chapter, _add_character
        from tools.state.chapter_writing_brief import build_chapter_writing_brief

        book, plugin_root = _setup_book(tmp_path)
        _make_chapter(
            book, "01-intro", number=1, title="Intro", pov="Theo",
            body="## Chapter Timeline\n\n- ~14:00 clothing: tactical boots.\n",
        )
        _add_character(book, "theo", name="Theo")

        brief = build_chapter_writing_brief(
            book_root=book,
            book_slug="test-book",
            chapter_slug="01-intro",
            plugin_root=plugin_root,
        )
        _json.dumps(brief["pov_character_state"])

    def test_brief_state_placed_after_inventory(self, tmp_path: Path):
        """pov_character_state appears directly after pov_character_inventory in the dict."""
        from tests.state.test_chapter_writing_brief import _setup_book, _make_chapter, _add_character
        from tools.state.chapter_writing_brief import build_chapter_writing_brief

        book, plugin_root = _setup_book(tmp_path)
        _make_chapter(book, "01-intro", number=1, title="Intro", pov="Theo")
        _add_character(book, "theo", name="Theo")

        brief = build_chapter_writing_brief(
            book_root=book,
            book_slug="test-book",
            chapter_slug="01-intro",
            plugin_root=plugin_root,
        )
        keys = list(brief.keys())
        inv_idx = keys.index("pov_character_inventory")
        state_idx = keys.index("pov_character_state")
        assert state_idx == inv_idx + 1, "pov_character_state must immediately follow pov_character_inventory"
