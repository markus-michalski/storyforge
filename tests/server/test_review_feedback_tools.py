"""Tests for the review-feedback MCP tools — Epic #663 / Issue #665."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

import routers._app as _app
from routers.feedback import (
    discard_feedback,
    get_voice_candidates,
    list_pending_feedback,
    log_review_feedback,
    mark_feedback_harvested,
    set_feedback_classification,
)
from tools.db.connection import open_authors_db
from tools.db.review_feedback import get_feedback, list_feedback

BOOKS = {
    "firelight": {
        "author": "ethan-cole",
        "genres": ["dark-fantasy", "lgbtq"],
        "book_category": "fiction",
        "chapters_data": {"01-arrival": {"number": 1}, "02-fire": {"number": 2}},
        "people": {},
    },
    "second-light": {
        "author": "other-author",
        "genres": ["thriller"],
        "book_category": "fiction",
        "chapters_data": {"01-start": {"number": 1}},
        "people": {},
    },
    "my-life": {
        "author": "ethan-cole",
        "genres": [],
        "book_category": "memoir",
        "chapters_data": {"01-home": {"number": 1}},
        "people": {
            "anna": {"slug": "anna", "name": "Anna Berger", "real_name": "Anna Mueller"},
            "mom": {"slug": "mom", "name": "Mom", "real_name": ""},
            "wei": {"slug": "li-wei", "name": "Li Wei", "real_name": ""},
            "schmidt": {"slug": "karl-schmidt", "name": "Pseudonym", "real_name": ""},
        },
    },
    "other-life": {
        "author": "ethan-cole",
        "genres": [],
        "book_category": "memoir",
        "chapters_data": {"01-x": {"number": 1}},
        "people": {"bob": {"slug": "bob", "name": "Robert Hale", "real_name": ""}},
    },
    "mixed-up": {
        "author": "ethan-cole",
        "genres": ["drama"],
        "book_category": "fiction",
        "chapters_data": {"01-x": {"number": 1}},
        "people": {"zoe": {"slug": "zoe", "name": "Zoe Park", "real_name": ""}},
    },
    "spaced": {
        "author": "  ethan-cole ",
        "genres": ["drama"],
        "book_category": "fiction",
        "chapters_data": {"01-x": {"number": 1}},
        "people": {},
    },
}


@pytest.fixture
def env(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    import tools.db.connection as conn_mod

    db_dir = tmp_path / "db"
    db_dir.mkdir()
    monkeypatch.setattr(conn_mod, "DB_DIR", db_dir)
    monkeypatch.setattr(_app._cache, "get", lambda: {"books": BOOKS, "authors": {}})
    return tmp_path


def _log(**kw) -> dict:
    args = dict(
        book_slug="firelight", chapter_slug="01-arrival", source_skill="reviewer",
        decision="accepted", comment_text="zu verschwurbelt",
        before_text="The silence held the room.", after_text="Nobody spoke.",
    )
    args.update(kw)
    return json.loads(log_review_feedback(**args))


def _rows(author="ethan-cole", **kw):
    conn = open_authors_db()
    try:
        return list_feedback(conn, author, **kw)
    finally:
        conn.close()


class TestLogReviewFeedback:
    def test_resolves_author_genres_and_category_from_the_book(self, env):
        result = _log()
        assert result["logged"] is True
        row = _rows()[0]
        assert row["author_slug"] == "ethan-cole"
        assert row["genres"] == "dark-fantasy,lgbtq"
        assert row["book_category"] == "fiction"
        assert row["status"] == "pending"

    def test_duplicate_is_reported_not_errored(self, env):
        _log()
        again = _log()
        assert again["logged"] is False
        assert again["duplicate"] is True
        assert len(_rows()) == 1

    def test_unknown_book_is_an_actionable_error(self, env):
        result = _log(book_slug="ghost")
        assert "error" in result and "ghost" in result["error"]

    def test_unknown_chapter_is_an_actionable_error(self, env):
        result = _log(chapter_slug="99-nope")
        assert "error" in result and "99-nope" in result["error"]
        assert _rows() == []

    def test_book_without_author_is_an_error(self, env, monkeypatch):
        books = {"orphan": {**BOOKS["firelight"], "author": ""}}
        monkeypatch.setattr(_app._cache, "get", lambda: {"books": books})
        assert "error" in _log(book_slug="orphan")

    @pytest.mark.parametrize("field,value", [
        ("source_skill", "nobody"), ("decision", "maybe"),
    ])
    def test_invalid_enums_return_error_listing_allowed(self, env, field, value):
        result = _log(**{field: value})
        assert field in result["error"]

    def test_classification_is_validated_against_the_vocabulary(self, env):
        ok = _log(dimension="sentence_rhythm", direction="shorter",
                  normalized_rule="Prefer shorter sentences.")
        assert ok["logged"] is True and ok["status"] == "classified"
        bad = _log(comment_text="anders", dimension="sentence_length_ish",
                   direction="shorter", normalized_rule="x")
        assert "error" in bad and "sentence_rhythm" in bad["error"]

    def test_partial_classification_is_an_error(self, env):
        assert "error" in _log(dimension="sentence_rhythm")

    def test_memoir_dimension_rejected_for_fiction(self, env):
        result = _log(dimension="looking_back_hinge", direction="less",
                      normalized_rule="No hinges.")
        assert "error" in result and "memoir" in result["error"]

    def test_normalized_rule_must_be_a_short_single_line(self, env):
        long = _log(dimension="sentence_rhythm", direction="shorter",
                    normalized_rule="x" * 400)
        assert "error" in long
        multi = _log(comment_text="zwei", dimension="sentence_rhythm", direction="shorter",
                     normalized_rule="a\nb")
        assert "error" in multi

    def test_classification_requires_a_rule_text(self, env):
        result = _log(dimension="sentence_rhythm", direction="shorter", normalized_rule="  ")
        assert "error" in result


class TestMemoirPrivacy:
    def test_memoir_requires_classification(self, env):
        result = _log(book_slug="my-life", chapter_slug="01-home")
        assert "error" in result and "classif" in result["error"]
        assert _rows() == []

    def test_memoir_raw_text_is_not_persisted(self, env):
        result = _log(
            book_slug="my-life", chapter_slug="01-home",
            comment_text="Anna würde das nie sagen.",
            before_text="Anna sagte, sie gehe.", after_text="Anna ging.",
            dimension="reflective_platitude", direction="less",
            normalized_rule="Cut explanatory commentary after an image.",
        )
        assert result["logged"] is True
        row = _rows()[0]
        for field in ("comment_text", "before_text", "after_text", "proposal_text"):
            assert row[field] == ""
        assert row["genres"] == ""
        assert row["book_category"] == "memoir"

    @pytest.mark.parametrize("rule", [
        "Anna would not say this.",
        "Make it sound less like Anna Mueller.",
        "anna berger talks plainer",
    ])
    def test_memoir_rule_must_not_contain_person_names(self, env, rule):
        result = _log(
            book_slug="my-life", chapter_slug="01-home",
            dimension="word_register", direction="plainer", normalized_rule=rule,
        )
        assert "error" in result and "name" in result["error"].lower()
        assert _rows() == []

    def test_other_words_are_not_mistaken_for_names(self, env):
        result = _log(
            book_slug="my-life", chapter_slug="01-home",
            dimension="word_register", direction="plainer",
            normalized_rule="Plainer wording in narration, annals of detail cut.",
        )
        assert result["logged"] is True


class TestListPendingFeedback:
    def test_lists_open_entries_for_the_books_author(self, env):
        _log()
        _log(chapter_slug="02-fire", comment_text="zweites")
        result = json.loads(list_pending_feedback("firelight"))
        assert result["count"] == 2
        assert {e["chapter_slug"] for e in result["entries"]} == {"01-arrival", "02-fire"}

    def test_chapter_filter_marks_carry_over(self, env):
        _log()
        _log(chapter_slug="02-fire", comment_text="zweites")
        result = json.loads(list_pending_feedback("firelight", "02-fire"))
        by_chapter = {e["chapter_slug"]: e for e in result["entries"]}
        assert by_chapter["02-fire"]["carried_over"] is False
        assert by_chapter["01-arrival"]["carried_over"] is True

    def test_other_authors_entries_are_not_listed(self, env):
        _log()
        _log(book_slug="second-light", chapter_slug="01-start", comment_text="fremd")
        result = json.loads(list_pending_feedback("firelight"))
        assert result["count"] == 1

    def test_closed_entries_are_not_listed(self, env):
        _log()
        row = _rows()[0]
        json.loads(mark_feedback_harvested("firelight", [row["id"]]))
        assert json.loads(list_pending_feedback("firelight"))["count"] == 0

    def test_unknown_book_is_an_error(self, env):
        assert "error" in json.loads(list_pending_feedback("ghost"))

    def test_unknown_chapter_filter_is_an_error(self, env):
        assert "error" in json.loads(list_pending_feedback("firelight", "99-nope"))


class TestSetFeedbackClassification:
    def test_classifies_a_pending_entry(self, env):
        _log()
        row_id = _rows()[0]["id"]
        result = json.loads(set_feedback_classification(
            "firelight", row_id, "simile_density", "fewer", "Fewer similes.",
        ))
        assert result["updated"] is True
        row = _rows()[0]
        assert (row["dimension"], row["direction"], row["status"]) == (
            "simile_density", "fewer", "classified")

    def test_validates_against_the_rows_own_category(self, env):
        _log(book_slug="my-life", chapter_slug="01-home",
             dimension="hedging", direction="less", normalized_rule="No hedging.")
        row_id = _rows()[0]["id"]
        result = json.loads(set_feedback_classification(
            "my-life", row_id, "sentence_rhythm", "shorter", "Shorter.",
        ))
        assert result["updated"] is True

    def test_invalid_pair_is_rejected(self, env):
        _log()
        row_id = _rows()[0]["id"]
        result = json.loads(set_feedback_classification(
            "firelight", row_id, "sentence_rhythm", "sideways", "x",
        ))
        assert "error" in result and "shorter" in result["error"]
        assert _rows()[0]["dimension"] is None

    def test_cannot_touch_another_authors_entry(self, env):
        _log(book_slug="second-light", chapter_slug="01-start")
        foreign = _rows("other-author")[0]["id"]
        result = json.loads(set_feedback_classification(
            "firelight", foreign, "sentence_rhythm", "shorter", "Shorter.",
        ))
        assert result["updated"] is False
        assert _rows("other-author")[0]["dimension"] is None

    def test_memoir_rule_with_a_name_is_rejected(self, env):
        _log(book_slug="my-life", chapter_slug="01-home",
             dimension="hedging", direction="less", normalized_rule="No hedging.")
        row_id = _rows()[0]["id"]
        result = json.loads(set_feedback_classification(
            "my-life", row_id, "hedging", "less", "Anna hedges too much.",
        ))
        assert "error" in result


class TestClosingFeedback:
    def test_mark_harvested_and_discard(self, env):
        _log()
        _log(comment_text="zweites")
        a, b = (r["id"] for r in _rows())
        h = json.loads(mark_feedback_harvested("firelight", [a]))
        d = json.loads(discard_feedback("firelight", [b]))
        assert h["changed"] == 1 and d["changed"] == 1
        conn = open_authors_db()
        try:
            assert get_feedback(conn, a)["status"] == "harvested"
            assert get_feedback(conn, b)["status"] == "discarded"
        finally:
            conn.close()

    def test_closed_entries_are_not_flipped(self, env):
        _log()
        a = _rows()[0]["id"]
        mark_feedback_harvested("firelight", [a])
        again = json.loads(discard_feedback("firelight", [a]))
        assert again["changed"] == 0

    def test_foreign_ids_are_ignored(self, env):
        _log(book_slug="second-light", chapter_slug="01-start")
        foreign = _rows("other-author")[0]["id"]
        result = json.loads(mark_feedback_harvested("firelight", [foreign]))
        assert result["changed"] == 0
        assert _rows("other-author")[0]["status"] == "pending"

    def test_rejects_empty_and_non_integer_ids(self, env):
        assert "error" in json.loads(mark_feedback_harvested("firelight", []))
        assert "error" in json.loads(discard_feedback("firelight", ["1"]))  # type: ignore[list-item]


class TestReviewRoundTwo:
    """Findings from the #665 code review."""

    def test_memoir_row_cannot_be_reclassified_with_a_name_via_another_book(self, env):
        _log(book_slug="my-life", chapter_slug="01-home",
             dimension="hedging", direction="less", normalized_rule="No hedging.")
        rid = _rows()[0]["id"]
        for via in ("firelight", "other-life"):
            result = json.loads(set_feedback_classification(
                via, rid, "sentence_rhythm", "shorter", "Write about Anna Mueller plainly.",
            ))
            assert "error" in result, via
        assert _rows()[0]["normalized_rule"] == "No hedging."

    def test_memoir_row_of_a_vanished_book_fails_closed(self, env, monkeypatch):
        _log(book_slug="my-life", chapter_slug="01-home",
             dimension="hedging", direction="less", normalized_rule="No hedging.")
        rid = _rows()[0]["id"]
        books = {k: v for k, v in BOOKS.items() if k != "my-life"}
        monkeypatch.setattr(_app._cache, "get", lambda: {"books": books})
        result = json.loads(set_feedback_classification(
            "firelight", rid, "sentence_rhythm", "shorter", "Plain rule.",
        ))
        assert "error" in result

    @pytest.mark.parametrize("rule", [
        "Annas voice is too polished",
        "Bergers habit of talking",
        "Anna_Berger style",
        "Ánna would not say it",
        "Li speaks too formally",
        "Schmidt family dialogue",
        "Anna\u2019s rhythm",
    ])
    def test_name_guard_catches_common_variants(self, env, rule):
        result = _log(book_slug="my-life", chapter_slug="01-home",
                      dimension="word_register", direction="plainer", normalized_rule=rule)
        assert "error" in result, rule

    def test_name_guard_reports_the_matching_token(self, env):
        result = _log(book_slug="my-life", chapter_slug="01-home",
                      dimension="word_register", direction="plainer",
                      normalized_rule="Anna sounds stiff")
        assert "anna" in result["error"].lower()

    @pytest.mark.parametrize("rule", [
        "Allow grace notes in the rhythm.",
        "Mom-style warmth in dialogue tags is fine.",
        "Plainer wording in narration.",
    ])
    def test_name_guard_does_not_block_ordinary_rules(self, env, rule):
        result = _log(book_slug="my-life", chapter_slug="01-home",
                      dimension="word_register", direction="plainer", normalized_rule=rule)
        assert result.get("logged") is True, result

    def test_database_errors_become_json_errors(self, env, monkeypatch):
        import sqlite3

        import routers.feedback as fb

        def boom(*a, **k):
            raise sqlite3.OperationalError("database is locked")

        monkeypatch.setattr(fb, "open_authors_db", boom)
        for call in (
            lambda: _log(),
            lambda: json.loads(list_pending_feedback("firelight")),
            lambda: json.loads(set_feedback_classification("firelight", 1, "pacing", "faster", "Faster.")),
            lambda: json.loads(mark_feedback_harvested("firelight", [1])),
        ):
            assert "locked" in call()["error"]

    def test_text_fields_have_a_length_cap(self, env):
        result = _log(comment_text="x" * 20000)
        assert "error" in result and "comment_text" in result["error"]
        assert _rows() == []

    def test_non_string_arguments_return_errors(self, env):
        assert "error" in _log(comment_text=None)
        assert "error" in _log(dimension=None, direction="x")
        assert "error" in _log(chapter_slug=["a"])
        assert "error" in json.loads(set_feedback_classification(
            "firelight", 1, "pacing", "faster", None))  # type: ignore[arg-type]

    @pytest.mark.parametrize("bad_id", [True, "1", 1.5])
    def test_set_classification_rejects_non_int_ids(self, env, bad_id):
        _log()
        result = json.loads(set_feedback_classification(
            "firelight", bad_id, "pacing", "faster", "Faster."))  # type: ignore[arg-type]
        assert "error" in result

    def test_author_whitespace_is_normalised(self, env):
        assert _log(book_slug="spaced", chapter_slug="01-x")["logged"] is True
        assert _rows("ethan-cole")[0]["author_slug"] == "ethan-cole"

    def test_fiction_book_with_people_profiles_fails_closed(self, env):
        result = _log(book_slug="mixed-up", chapter_slug="01-x")
        assert "error" in result and "memoir" in result["error"]
        assert _rows() == []

    def test_closed_row_cannot_be_reclassified_through_the_tool(self, env):
        _log()
        rid = _rows()[0]["id"]
        mark_feedback_harvested("firelight", [rid])
        result = json.loads(set_feedback_classification(
            "firelight", rid, "pacing", "faster", "Faster."))
        assert result["updated"] is False


class TestGetVoiceCandidates:
    def _seed(self, n=3, **kw):
        for i in range(1, n + 1):
            chapter = "01-arrival" if i % 2 else "02-fire"
            _log(
                chapter_slug=chapter, comment_text=f"kürzer {i}",
                dimension="sentence_rhythm", direction="shorter",
                normalized_rule="Prefer shorter sentences.", **kw,
            )

    def test_returns_candidate_with_genre_scope(self, env):
        self._seed(3)
        result = json.loads(get_voice_candidates("ethan-cole"))
        assert result["author_slug"] == "ethan-cole"
        assert len(result["candidates"]) == 1
        c = result["candidates"][0]
        assert (c["dimension"], c["direction"], c["target_section"]) == (
            "sentence_rhythm", "shorter", "style_principles")
        assert c["scope"] == {"universal": False, "genres": ["dark-fantasy", "lgbtq"]}

    def test_below_threshold_returns_nothing_and_counts_unclassified(self, env):
        self._seed(2)
        _log(comment_text="noch offen")
        result = json.loads(get_voice_candidates("ethan-cole"))
        assert result["candidates"] == []
        assert result["unclassified"] == 1

    def test_book_filter_restricts_category_and_checks_author(self, env):
        self._seed(3)
        ok = json.loads(get_voice_candidates("ethan-cole", "firelight"))
        assert len(ok["candidates"]) == 1
        memoir_view = json.loads(get_voice_candidates("ethan-cole", "my-life"))
        assert memoir_view["candidates"] == []
        wrong = json.loads(get_voice_candidates("other-author", "firelight"))
        assert "error" in wrong

    def test_other_authors_evidence_is_not_mixed_in(self, env):
        self._seed(3)
        result = json.loads(get_voice_candidates("other-author"))
        assert result["candidates"] == []

    def test_rejects_bad_arguments(self, env):
        assert "error" in json.loads(get_voice_candidates(""))
        assert "error" in json.loads(get_voice_candidates(None))  # type: ignore[arg-type]
        assert "error" in json.loads(get_voice_candidates("ethan-cole", "ghost"))
