"""Style analysis tools for comparing text against author profiles."""

from __future__ import annotations

import re
from collections import Counter
from pathlib import Path
from typing import Any


# Common AI-tell words — the banned list
AI_TELL_WORDS = {
    "delve", "tapestry", "nuanced", "vibrant", "landscape", "embark",
    "resonate", "pivotal", "multifaceted", "realm", "testament",
    "intricate", "myriad", "unprecedented", "foster", "navigate",
    "uncover", "ever-evolving", "beacon", "juxtaposition", "paradigm",
    "synergy", "interplay", "aforementioned", "groundbreaking",
    "spearhead", "leverage", "underpin", "underscore", "overarching",
    "holistic", "robust", "streamline", "cutting-edge", "game-changer",
    "deep-dive", "utilize", "facilitate", "endeavor", "comprehensive",
    "furthermore", "moreover", "henceforth", "notwithstanding",
    "bustling", "piercing", "riveting", "captivating", "mesmerizing",
}

# Common filter words that indicate telling instead of showing
FILTER_WORDS = {
    "she saw", "he saw", "she heard", "he heard",
    "she felt", "he felt", "she thought", "he thought",
    "she noticed", "he noticed", "she realized", "he realized",
    "she wondered", "he wondered", "she knew", "he knew",
    "she watched", "he watched", "she observed", "he observed",
}


def scan_ai_tells(text: str) -> list[dict[str, Any]]:
    """Scan text for AI-tell vocabulary. Returns list of findings with context."""
    findings = []
    lines = text.splitlines()

    for i, line in enumerate(lines, 1):
        line_lower = line.lower()
        for word in AI_TELL_WORDS:
            # Match whole word
            pattern = rf'\b{re.escape(word)}\b'
            for match in re.finditer(pattern, line_lower):
                start = max(0, match.start() - 30)
                end = min(len(line), match.end() + 30)
                context = line[start:end].strip()
                findings.append({
                    "word": word,
                    "line": i,
                    "context": f"...{context}...",
                })

    return findings


def scan_filter_words(text: str) -> list[dict[str, Any]]:
    """Scan for filter words that indicate 'telling' instead of 'showing'."""
    findings = []
    lines = text.splitlines()

    for i, line in enumerate(lines, 1):
        line_lower = line.lower()
        for phrase in FILTER_WORDS:
            if phrase in line_lower:
                findings.append({
                    "phrase": phrase,
                    "line": i,
                    "context": line.strip()[:80],
                })

    return findings


def analyze_vocabulary_complexity(text: str) -> dict[str, Any]:
    """Analyze vocabulary complexity metrics."""
    # Remove frontmatter
    text = re.sub(r"^---\s*\n.*?\n---\s*\n", "", text, flags=re.DOTALL)

    words = re.findall(r'\b[a-zA-Z]+\b', text.lower())
    if not words:
        return {"total_words": 0}

    unique_words = set(words)
    word_freq = Counter(words)

    # Type-token ratio
    ttr = len(unique_words) / len(words)

    # Average word length
    avg_length = sum(len(w) for w in words) / len(words)

    # Long words (3+ syllables, approximated by length > 7)
    long_words = [w for w in unique_words if len(w) > 7]
    long_word_ratio = len(long_words) / len(unique_words) if unique_words else 0

    return {
        "total_words": len(words),
        "unique_words": len(unique_words),
        "type_token_ratio": round(ttr, 3),
        "avg_word_length": round(avg_length, 1),
        "long_word_ratio": round(long_word_ratio, 3),
        "most_common": word_freq.most_common(20),
    }


def analyze_dialog_ratio(text: str) -> dict[str, Any]:
    """Analyze the ratio of dialog to narration."""
    # Remove frontmatter
    text = re.sub(r"^---\s*\n.*?\n---\s*\n", "", text, flags=re.DOTALL)

    # Find text within quotes
    dialog_matches = re.findall(r'["\u201c](.*?)["\u201d]', text)
    dialog_words = sum(len(d.split()) for d in dialog_matches)
    total_words = len(text.split())

    ratio = dialog_words / total_words if total_words else 0

    return {
        "total_words": total_words,
        "dialog_words": dialog_words,
        "narration_words": total_words - dialog_words,
        "dialog_ratio": round(ratio, 3),
        "dialog_percent": round(ratio * 100, 1),
    }


def check_paragraph_uniformity(text: str) -> dict[str, Any]:
    """Check if paragraphs are suspiciously uniform in length (AI tell)."""
    # Remove frontmatter
    text = re.sub(r"^---\s*\n.*?\n---\s*\n", "", text, flags=re.DOTALL)

    paragraphs = [p.strip() for p in text.split("\n\n") if p.strip()]
    if len(paragraphs) < 3:
        return {"count": len(paragraphs), "uniformity": "insufficient data"}

    lengths = [len(p.split()) for p in paragraphs]
    mean = sum(lengths) / len(lengths)
    variance = sum((l - mean) ** 2 for l in lengths) / len(lengths)
    std_dev = variance ** 0.5

    # Human paragraphs vary a LOT
    # AI paragraphs tend to be uniform
    if std_dev > 20:
        rating = "Human-like (high variance)"
    elif std_dev > 10:
        rating = "Moderate variance"
    else:
        rating = "Suspiciously uniform (AI-like)"

    return {
        "count": len(paragraphs),
        "mean_length": round(mean, 1),
        "std_dev": round(std_dev, 1),
        "min_length": min(lengths),
        "max_length": max(lengths),
        "uniformity_rating": rating,
    }
