"""Smoke: the review-feedback tools are registered with the right annotations (#663 / #670)."""

from __future__ import annotations

import pytest

from tests.smoke._helpers import registered_tools

FEEDBACK_TOOLS = {
    "log_review_feedback": {"read_only": False},
    "list_pending_feedback": {"read_only": True},
    "set_feedback_classification": {"read_only": False},
    "get_voice_candidates": {"read_only": True},
    "mark_feedback_harvested": {"read_only": False},
    "discard_feedback": {"read_only": False},
}


@pytest.fixture(scope="module")
def tools() -> dict:
    return {t.name: t for t in registered_tools()}


@pytest.mark.parametrize("name,expected", sorted(FEEDBACK_TOOLS.items()))
def test_tool_is_registered_with_matching_read_only_hint(tools, name, expected):
    assert name in tools, f"{name} is not registered"
    annotations = tools[name].annotations
    assert annotations is not None, f"{name} has no annotations"
    assert bool(annotations.read_only_hint) is expected["read_only"], name


def test_write_tools_are_marked_idempotent(tools):
    for name, expected in FEEDBACK_TOOLS.items():
        if expected["read_only"]:
            continue
        annotations = tools[name].annotations
        assert annotations.idempotent_hint is True, name


def test_every_feedback_tool_has_an_actionable_docstring(tools):
    for name in FEEDBACK_TOOLS:
        description = tools[name].description or ""
        assert len(description.strip()) > 40, name
        assert "Returns" in description, f"{name} docstring does not state its return shape"
