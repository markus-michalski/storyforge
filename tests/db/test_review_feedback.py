"""Tests for the review_feedback table and CRUD helpers — Epic #663 / Issue #664."""

from __future__ import annotations

from pathlib import Path

import pytest

from tools.db.connection import ensure_authors_schema, open_db
from tools.db.review_feedback import (
    VALID_DECISIONS,
    VALID_SOURCES,
    VALID_STATUSES,
    get_feedback,
    insert_feedback,
    list_feedback,
    mark_feedback,
    remove_author_feedback,
    set_classification,
)


@pytest.fixture
def conn(tmp_path: Path):
    db = open_db(tmp_path / "authors.db")
    ensure_authors_schema(db)
    yield db
    db.close()


def _add(conn, **overrides) -> int | None:
    kwargs = dict(
        author_slug="ethan-cole",
        book_slug="firelight",
        chapter_slug="01-arrival",
        source_skill="reviewer",
        decision="accepted",
        book_category="fiction",
        genres="dark-fantasy,lgbtq",
        comment_text="zu verschwurbelt",
        before_text="The silence held the room like a held breath.",
        after_text="Nobody spoke.",
    )
    kwargs.update(overrides)
    return insert_feedback(conn, **kwargs)


class TestSchema:
    def test_ensure_schema_is_idempotent(self, conn):
        ensure_authors_schema(conn)
        ensure_authors_schema(conn)
        cols = {r[1] for r in conn.execute("PRAGMA table_info(review_feedback)")}
        assert {
            "author_slug", "book_slug", "chapter_slug", "book_category", "genres",
            "source_skill", "decision", "comment_text", "before_text", "after_text",
            "proposal_text", "dimension", "direction", "normalized_rule", "status",
            "content_hash", "created_at", "updated_at",
        } <= cols

    def test_does_not_touch_author_discoveries(self, conn):
        cols = {r[1] for r in conn.execute("PRAGMA table_info(author_discoveries)")}
        assert "review_feedback" not in cols
        assert "source_genres" in cols

    def test_enum_constants(self):
        assert {"reviewer", "fixer", "rewriter", "writer", "humanizer",
                "proofreader", "self_edit"} <= VALID_SOURCES
        assert VALID_DECISIONS == frozenset({"accepted", "reworked", "rejected", "self_edit"})
        assert VALID_STATUSES == frozenset({"pending", "classified", "harvested", "discarded"})


class TestInsert:
    def test_inserts_pending_row(self, conn):
        row_id = _add(conn)
        assert isinstance(row_id, int)
        row = get_feedback(conn, row_id)
        assert row["status"] == "pending"
        assert row["book_category"] == "fiction"
        assert row["dimension"] is None
        assert row["before_text"].startswith("The silence")

    def test_duplicate_returns_none(self, conn):
        assert _add(conn) is not None
        assert _add(conn) is None
        assert conn.execute("SELECT COUNT(*) FROM review_feedback").fetchone()[0] == 1

    def test_same_content_in_other_chapter_is_not_a_duplicate(self, conn):
        assert _add(conn) is not None
        assert _add(conn, chapter_slug="02-fire") is not None

    @pytest.mark.parametrize("field,value", [
        ("source_skill", "nobody"),
        ("decision", "maybe"),
        ("book_category", "poetry"),
    ])
    def test_rejects_invalid_enum_values(self, conn, field, value):
        with pytest.raises(ValueError, match=field):
            _add(conn, **{field: value})

    def test_rejects_entry_without_any_content(self, conn):
        with pytest.raises(ValueError, match="content"):
            _add(conn, comment_text="", before_text="", after_text="", proposal_text="")

    def test_rejected_proposal_is_stored(self, conn):
        row_id = _add(
            conn, source_skill="fixer", decision="rejected",
            comment_text="", before_text="", after_text="",
            proposal_text="Replace 'said' with 'murmured'.",
        )
        row = get_feedback(conn, row_id)
        assert row["decision"] == "rejected"
        assert row["proposal_text"].startswith("Replace")

    def test_classification_at_insert_marks_row_classified(self, conn):
        row_id = _add(conn, dimension="sentence_rhythm", direction="shorter",
                      normalized_rule="Prefer shorter sentences.")
        row = get_feedback(conn, row_id)
        assert row["status"] == "classified"
        assert row["dimension"] == "sentence_rhythm"


class TestMemoirPrivacy:
    def test_memoir_never_persists_raw_text(self, conn):
        row_id = _add(
            conn, book_category="memoir", genres="",
            comment_text="Das klingt nicht nach Anna, die so redet.",
            before_text="Anna sagte, sie wolle gehen.",
            after_text="Anna ging.",
            proposal_text="Anna sprach leise.",
            dimension="reflective_platitude", direction="less",
            normalized_rule="Cut explanatory commentary after an image.",
        )
        row = get_feedback(conn, row_id)
        for field in ("comment_text", "before_text", "after_text", "proposal_text"):
            assert row[field] == ""
        assert row["dimension"] == "reflective_platitude"

    def test_memoir_without_classification_is_rejected(self, conn):
        with pytest.raises(ValueError, match="classification"):
            _add(conn, book_category="memoir", genres="")

    def test_memoir_duplicates_are_still_detected(self, conn):
        kw = dict(book_category="memoir", genres="", dimension="hedging",
                  direction="less", normalized_rule="No hedging.")
        assert _add(conn, **kw) is not None
        assert _add(conn, **kw) is None


class TestList:
    def test_defaults_to_open_entries_for_author(self, conn):
        a = _add(conn)
        b = _add(conn, comment_text="anders", chapter_slug="02-fire")
        _add(conn, author_slug="someone-else", comment_text="x")
        mark_feedback(conn, [b], "harvested")
        rows = list_feedback(conn, "ethan-cole")
        assert [r["id"] for r in rows] == [a]

    def test_filter_by_book_and_chapter(self, conn):
        a = _add(conn)
        b = _add(conn, chapter_slug="02-fire", comment_text="anders")
        c = _add(conn, book_slug="other", comment_text="drittes")
        assert {r["id"] for r in list_feedback(conn, "ethan-cole")} == {a, b, c}
        assert {r["id"] for r in list_feedback(conn, "ethan-cole", book_slug="firelight")} == {a, b}
        only = list_feedback(conn, "ethan-cole", book_slug="firelight", chapter_slug="02-fire")
        assert [r["id"] for r in only] == [b]

    def test_status_filter(self, conn):
        a = _add(conn)
        mark_feedback(conn, [a], "discarded")
        assert list_feedback(conn, "ethan-cole") == []
        assert [r["id"] for r in list_feedback(conn, "ethan-cole", statuses=("discarded",))] == [a]

    def test_unknown_status_raises(self, conn):
        with pytest.raises(ValueError, match="status"):
            list_feedback(conn, "ethan-cole", statuses=("open",))

    def test_ordered_by_id(self, conn):
        ids = [_add(conn, comment_text=f"c{i}") for i in range(3)]
        assert [r["id"] for r in list_feedback(conn, "ethan-cole")] == ids


class TestClassificationAndStatus:
    def test_set_classification(self, conn):
        row_id = _add(conn)
        assert set_classification(
            conn, row_id, dimension="simile_density", direction="fewer",
            normalized_rule="Fewer similes.",
        ) is True
        row = get_feedback(conn, row_id)
        assert (row["dimension"], row["direction"], row["status"]) == (
            "simile_density", "fewer", "classified")

    def test_set_classification_unknown_id(self, conn):
        assert set_classification(conn, 999, dimension="d", direction="x",
                                  normalized_rule="r") is False

    def test_set_classification_requires_dimension_and_direction(self, conn):
        row_id = _add(conn)
        with pytest.raises(ValueError, match="dimension"):
            set_classification(conn, row_id, dimension="", direction="x", normalized_rule="r")

    def test_classification_does_not_resurrect_harvested_rows(self, conn):
        row_id = _add(conn)
        mark_feedback(conn, [row_id], "harvested")
        assert set_classification(conn, row_id, dimension="d", direction="x",
                                  normalized_rule="r") is False
        assert get_feedback(conn, row_id)["status"] == "harvested"

    def test_mark_returns_changed_count_and_ignores_unknown(self, conn):
        a, b = _add(conn), _add(conn, comment_text="b")
        assert mark_feedback(conn, [a, b, 999], "harvested") == 2

    def test_mark_only_accepts_terminal_statuses(self, conn):
        a = _add(conn)
        with pytest.raises(ValueError, match="status"):
            mark_feedback(conn, [a], "pending")

    def test_mark_empty_list_is_noop(self, conn):
        assert mark_feedback(conn, [], "harvested") == 0


class TestHardening:
    """Findings from the #664 code review."""

    @pytest.mark.parametrize("category", ["fiction", "memoir"])
    def test_whitespace_classification_is_not_a_classification(self, conn, category):
        with pytest.raises(ValueError, match="classification"):
            _add(conn, book_category=category, genres="",
                 dimension="  ", direction=" ", normalized_rule="x")

    @pytest.mark.parametrize("partial", [
        {"dimension": "sentence_rhythm"},
        {"direction": "shorter"},
    ])
    def test_partial_classification_raises(self, conn, partial):
        with pytest.raises(ValueError, match="classification"):
            _add(conn, **partial)

    def test_book_category_is_required(self, conn):
        with pytest.raises(TypeError):
            insert_feedback(
                conn, author_slug="a", book_slug="b", chapter_slug="c",
                source_skill="reviewer", decision="accepted", comment_text="x",
            )

    @pytest.mark.parametrize("field", ["author_slug", "book_slug", "chapter_slug"])
    @pytest.mark.parametrize("value", ["", "  ", None])
    def test_required_slugs_raise_instead_of_looking_like_duplicates(self, conn, field, value):
        with pytest.raises(ValueError, match=field):
            _add(conn, **{field: value})

    def test_mark_does_not_flip_closed_rows(self, conn):
        a, b = _add(conn), _add(conn, comment_text="b")
        assert mark_feedback(conn, [a], "harvested") == 1
        assert mark_feedback(conn, [a, b], "discarded") == 1
        assert get_feedback(conn, a)["status"] == "harvested"
        assert get_feedback(conn, b)["status"] == "discarded"

    def test_set_classification_ignores_discarded_rows(self, conn):
        row_id = _add(conn)
        mark_feedback(conn, [row_id], "discarded")
        assert set_classification(conn, row_id, dimension="d", direction="x",
                                  normalized_rule="r") is False

    def test_reclassifying_an_open_row_is_allowed(self, conn):
        row_id = _add(conn, dimension="a", direction="x", normalized_rule="r1")
        assert set_classification(conn, row_id, dimension="b", direction="y",
                                  normalized_rule="r2") is True
        assert get_feedback(conn, row_id)["dimension"] == "b"

    def test_separator_in_text_does_not_collide(self, conn):
        assert _add(conn, comment_text="a\x1fb", before_text="", after_text="c") is not None
        assert _add(conn, comment_text="a", before_text="b\x1fc", after_text="") is not None

    def test_surrounding_whitespace_is_not_a_new_entry(self, conn):
        assert _add(conn, comment_text="foo") is not None
        assert _add(conn, comment_text="foo ") is None

    def test_bare_string_status_is_accepted(self, conn):
        row_id = _add(conn)
        assert [r["id"] for r in list_feedback(conn, "ethan-cole", statuses="pending")] == [row_id]


class TestRemoveAuthorFeedback:
    def test_removes_only_that_authors_rows(self, conn):
        _add(conn)
        _add(conn, comment_text="zweiter")
        _add(conn, author_slug="other", comment_text="fremd")
        assert remove_author_feedback(conn, "ethan-cole") == 2
        assert list_feedback(conn, "ethan-cole", statuses=tuple(VALID_STATUSES)) == []
        assert len(list_feedback(conn, "other")) == 1

    def test_unknown_author_returns_zero(self, conn):
        assert remove_author_feedback(conn, "ghost") == 0
