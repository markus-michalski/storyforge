"""Markdown report rendering for ``scan_repetitions`` output.

Pure presentation — takes the dict returned by :func:`scan_repetitions`
and produces the text written to ``<book>/research/manuscript-report.md``.
"""

from __future__ import annotations

from collections import defaultdict
from typing import Any

CATEGORY_LABELS = {
    "book_rule_violation": "Book Rule Violations",
    "cliche": "Clichés",
    "question_as_statement": "Dialogue Punctuation (Q-word + period)",
    "filter_word": "POV Filter Words",
    "adverb_density": "Adverb Density (per Chapter)",
    "sentence_repetition": "Sentence-Level Repetitions (8-15 words)",
    "snapshot": "Snapshot Blocks (static description, no movement)",
    "callback_dropped": "Dropped Callbacks (promised threads, no follow-through)",
    "callback_deferred": "Deferred Callbacks (long-silent registered threads)",
    # Memoir-specific (Phase 3, #61)
    "anonymization_leak": "Anonymization Leaks (real name in manuscript)",
    "tidy_lesson_ending": "Tidy-Lesson Endings (chapter closes on a moral)",
    "reflective_platitude": "Reflective Platitude Density (retrospective commentary)",
    "timeline_ambiguity": "Timeline Ambiguity (temporal hand-waving)",
    "real_people_consistency": "Real-People Name Inconsistency",
    # N-gram repetition categories
    "simile": "Similes & Metaphors",
    "blocking_tic": "Blocking Tics",
    "character_tell": "Character Tells",
    "sensory": "Sensory Repetitions",
    "structural": "Structural Tics",
    "signature_phrase": "Signature Phrases",
}

CATEGORY_ORDER = [
    "book_rule_violation",
    "anonymization_leak",
    "cliche",
    "question_as_statement",
    "filter_word",
    "adverb_density",
    "sentence_repetition",
    "snapshot",
    "callback_dropped",
    "callback_deferred",
    # Memoir-specific
    "tidy_lesson_ending",
    "reflective_platitude",
    "timeline_ambiguity",
    "real_people_consistency",
    # N-gram repetition categories
    "simile",
    "character_tell",
    "blocking_tic",
    "structural",
    "sensory",
    "signature_phrase",
]


def render_report(scan_result: dict[str, Any]) -> str:
    """Turn a scan result into a human-readable Markdown report."""
    findings = scan_result.get("findings", [])
    chapters_scanned = scan_result.get("chapters_scanned", 0)
    summary = scan_result.get("summary", {})

    lines: list[str] = []
    lines.append("# Repetition Report")
    lines.append("")
    lines.append(f"**Chapters scanned:** {chapters_scanned}")
    lines.append(f"**Findings:** {len(findings)}")
    lines.append("")

    if not findings:
        lines.append("No cross-chapter repetitions detected with the current thresholds.")
        lines.append("")
        return "\n".join(lines)

    lines.append("## Summary")
    lines.append("")
    lines.append("| Category | High (4+) | Medium (2-3) |")
    lines.append("|---|---:|---:|")
    for cat in CATEGORY_ORDER:
        if cat not in summary:
            continue
        s = summary[cat]
        lines.append(
            f"| {CATEGORY_LABELS[cat]} | {s.get('high', 0)} | {s.get('medium', 0)} |"
        )
    lines.append("")

    by_category: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for f in findings:
        by_category[f["category"]].append(f)

    for cat in CATEGORY_ORDER:
        items = by_category.get(cat, [])
        if not items:
            continue
        lines.append(f"## {CATEGORY_LABELS[cat]}")
        lines.append("")
        for f in items:
            severity_marker = "**HIGH**" if f["severity"] == "high" else "MEDIUM"
            lines.append(f"### `{f['phrase']}` — {f['count']}× ({severity_marker})")
            lines.append("")
            if f.get("source_rule"):
                lines.append(f"> **Rule:** {f['source_rule']}")
                lines.append("")
            for occ in f["occurrences"]:
                lines.append(f"- **{occ['chapter']}** (line {occ['line']}): {occ['snippet']}")
            lines.append("")
            lines.append(_recommendation_for(f))
            lines.append("")
    return "\n".join(lines)


def _recommendation_for(finding: dict[str, Any]) -> str:
    """Short, category-aware revision recommendation."""
    cat = finding["category"]
    count = finding["count"]
    if cat == "book_rule_violation":
        return (
            f"_Recommendation:_ This violates a rule from the book's CLAUDE.md. "
            f"Rewrite per the user-authored guidance above — all {count} "
            f"occurrence{'s' if count != 1 else ''} should be revised unless "
            f"the rule explicitly allows an exception."
        )
    if cat == "cliche":
        return (
            f"_Recommendation:_ \"{finding['phrase']}\" is a worn-out fiction "
            f"cliché. Replace every occurrence with imagery specific to this "
            f"scene's POV, stakes, and sensory palette. If you must keep one, "
            f"make it ironic or subvert it."
        )
    if cat == "question_as_statement":
        return (
            "_Recommendation:_ A single flat-delivery question reads as a "
            "stylistic choice (think McCarthy). At this density it reads as "
            "a missing keystroke. Two fixes: **(A)** convert to a real "
            "question mark — most dialogue wants this. **(B)** keep the "
            "period and pair it with a narrative beat that tells the reader "
            "the delivery is deliberate, e.g.:\n\n"
            "> \"Who?\"\n"
            "> It was a demand, not a question.\n\n"
            "Pick (A) as the default. Reserve (B) for moments where the "
            "flatness is load-bearing."
        )
    if cat == "filter_word":
        return (
            "_Recommendation:_ Filter words mediate sensation through the POV "
            "character's head — \"she felt the cold\" instead of \"the cold "
            "bit through her coat\". In close-third, they weaken immersion. "
            "Rewrite most hits by dropping the filter verb and letting the "
            "sensation act directly on the scene. Some are load-bearing "
            "(internal realisation, dream logic); keep those."
        )
    if cat == "adverb_density":
        return (
            "_Recommendation:_ Heavy `-ly` adverb use usually signals weak "
            "verb choice: \"walked slowly\" → \"trudged\", \"said quietly\" → "
            "\"murmured\". Not every adverb is wrong — but when density is "
            "this high, at least half are propping up verbs that could stand "
            "on their own. Strip them and see what survives."
        )
    if cat == "simile":
        return (
            f"_Recommendation:_ Keep the strongest occurrence (usually the first) "
            f"and rewrite the other {count - 1} with fresh imagery rooted in the "
            f"current scene's senses."
        )
    if cat == "character_tell":
        return (
            "_Recommendation:_ A repeated body-part tell becomes invisible after "
            "the second use. Keep one or two, then vary the physical signal — "
            "a different body part, an action, or a verbal beat."
        )
    if cat == "blocking_tic":
        return (
            f"_Recommendation:_ Blocking beats lose impact when reused. Replace "
            f"{count - 1} occurrences with action that advances the scene or "
            f"reveals subtext."
        )
    if cat == "structural":
        return (
            f"_Recommendation:_ A structural tic ({count}×) trains the reader to "
            f"see the seams. Recast the weaker instances with different syntax."
        )
    if cat == "sensory":
        return (
            f"_Recommendation:_ Same sensory description in {count} places — "
            f"vary at least {count - 1} of them so each scene has its own texture."
        )
    if cat == "snapshot":
        count = finding["count"]
        return (
            f"_Recommendation:_ {count} consecutive descriptive sentences with no "
            f"action and no dialog — the scene becomes a photograph. Fix options: "
            f"**(A)** insert one beat of character action (reaching for something, "
            f"shifting weight, a micro-gesture that shows state of mind); "
            f"**(B)** cut the block to 2-3 sentences of pure setting and trust the "
            f"reader to fill in the rest; "
            f"**(C)** if description is intentional (lyrical pause, aftermath beat), "
            f"raise the per-book threshold in `## Linter Config → snapshot_threshold`."
        )
    if cat == "sentence_repetition":
        return (
            f"_Recommendation:_ This {len(finding['phrase'].split())}-word sentence "
            f"recurs {count}× — the loudest AI tell in the book. Do not fix by swapping "
            f"one word; the rhythm and structure are what the reader recognises. Rewrite "
            f"the emotional beat entirely: different body signal, different duration, "
            f"different syntax. If it is a deliberate motif, add it to the book's "
            f"## Allowed Repetitions section in CLAUDE.md."
        )
    if cat == "callback_dropped":
        return (
            f"_Recommendation:_ '{finding['phrase']}' is registered in the Callback "
            f"Register with a hard deadline or must-not-forget flag that has been "
            f"breached. Either (A) plant the callback in the appropriate chapter now, "
            f"(B) update the register entry to reflect the new plan, or "
            f"(C) remove the callback if the thread was intentionally dropped."
        )
    if cat == "callback_deferred":
        return (
            f"_Recommendation:_ '{finding['phrase']}' has been silent for {count} "
            f"chapters. Decide whether to plant it soon or remove it from the register."
        )
    if cat == "anonymization_leak":
        return (
            "_Recommendation:_ A person's real name appears in the manuscript despite "
            "their profile being marked as anonymized. Replace every occurrence with "
            "the pseudonym (or a relationship-term like 'my colleague') before the "
            "manuscript leaves the author's desk. This is a pre-publication blocker."
        )
    if cat == "tidy_lesson_ending":
        return (
            "_Recommendation:_ The chapter ends by explaining what the experience "
            "meant rather than letting the moment speak. Cut the lesson language and "
            "close on a concrete detail — an image, a gesture, a line of dialogue. "
            "The reader draws the meaning; the author renders the scene."
        )
    if cat == "reflective_platitude":
        return (
            "_Recommendation:_ Dense retrospective commentary ('looking back', "
            "'in hindsight', 'what I learned') collapses scene into TED talk. "
            "Memoir earns its reflection by first rendering the experience fully. "
            "Cut or push the commentary phrases to a single moment of narrating-self "
            "intrusion; let the rest of the chapter stay in the experiencing self."
        )
    if cat == "timeline_ambiguity":
        return (
            "_Recommendation:_ Temporal hand-waving ('at some point', 'eventually', "
            "'one day') leaves the reader unanchored. Memoir credibility depends on "
            "specificity: a season, a year, a day-of-week, a life stage. Replace at "
            "least the chapter-opening time anchor with something concrete. A few "
            "vague transitions inside a chapter are fine; flagging density means too "
            "many in a row with no specific date anywhere in the chapter."
        )
    if cat == "real_people_consistency":
        return (
            "_Recommendation:_ The same person is referred to by different name forms "
            "across chapters. Pick the canonical form (the pseudonym, or the first-name "
            "only, or the full pseudonym) and apply it consistently throughout. "
            "Inconsistency confuses readers and can partially undermine anonymization."
        )
    return (
        f"_Recommendation:_ Decide which occurrence is most necessary; cut or "
        f"rewrite the other {count - 1}."
    )


__all__ = ["CATEGORY_LABELS", "CATEGORY_ORDER", "render_report"]
