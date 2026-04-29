"""Static vocabularies and tunable constants for the manuscript checker.

Pure data — no functions, no dependencies. Everything in here is either a
frozen set of words used by the classifier and scanners, or a numeric
threshold the orchestrator and category scanners read.

Splitting this out (#118) makes the wordlists trivially testable and
keeps the scanner modules focused on logic rather than data.
"""

from __future__ import annotations

# ---------------------------------------------------------------------------
# N-gram configuration
# ---------------------------------------------------------------------------

# Range of n-gram lengths to consider. 4 catches "the ghost of a", 7 catches
# longer signature constructions like "for a hundred and fifty years" without
# blowing up the index for very long books.
DEFAULT_NGRAM_SIZES = (4, 5, 6, 7)

# Minimum occurrences to keep an n-gram. 2 means "appears at least twice".
DEFAULT_MIN_OCCURRENCES = 2

# Stop-words used for the "skip n-grams that are entirely stop-words" filter.
# Kept small on purpose — we want to catch "for a hundred and fifty years",
# which contains stop-words but also distinctive content tokens.
STOP_WORDS = frozenset(
    {
        "a",
        "an",
        "the",
        "and",
        "or",
        "but",
        "if",
        "then",
        "of",
        "to",
        "in",
        "on",
        "at",
        "by",
        "for",
        "with",
        "from",
        "into",
        "onto",
        "as",
        "is",
        "are",
        "was",
        "were",
        "be",
        "been",
        "being",
        "it",
        "its",
        "this",
        "that",
        "these",
        "those",
        "he",
        "she",
        "him",
        "her",
        "his",
        "hers",
        "they",
        "them",
        "their",
        "i",
        "me",
        "my",
        "we",
        "us",
        "our",
        "you",
        "your",
        "not",
        "no",
        "do",
        "does",
        "did",
        "have",
        "has",
        "had",
        "so",
        "than",
        "there",
        "here",
        "out",
        "up",
        "down",
        "over",
        "under",
        "off",
        "about",
        "again",
        "very",
        "just",
    }
)

# Body-part / face-part vocabulary that, when present in a repeated phrase,
# strongly suggests a character tell.
BODY_PARTS = frozenset(
    {
        "eye",
        "eyes",
        "eyebrow",
        "eyebrows",
        "brow",
        "brows",
        "lip",
        "lips",
        "mouth",
        "jaw",
        "jaws",
        "cheek",
        "cheeks",
        "chin",
        "ear",
        "ears",
        "nose",
        "nostril",
        "nostrils",
        "tongue",
        "throat",
        "neck",
        "shoulder",
        "shoulders",
        "chest",
        "back",
        "spine",
        "arm",
        "arms",
        "elbow",
        "wrist",
        "hand",
        "hands",
        "finger",
        "fingers",
        "thumb",
        "knuckle",
        "knuckles",
        "fist",
        "fists",
        "hip",
        "hips",
        "leg",
        "legs",
        "knee",
        "knees",
        "foot",
        "feet",
        "toe",
        "toes",
        "muscle",
        "muscles",
        "vein",
        "veins",
        "tendon",
        "tendons",
        "head",
        "skull",
        "temple",
        "temples",
        "scalp",
        "hair",
        "face",
    }
)

# Verbs that frequently appear in blocking tics (small physical movements
# repeated as a beat between dialog).
BLOCKING_VERBS = frozenset(
    {
        "opened",
        "closed",
        "shut",
        "blinked",
        "swallowed",
        "nodded",
        "shrugged",
        "shook",
        "shifted",
        "leaned",
        "looked",
        "glanced",
        "stared",
        "turned",
        "tilted",
        "frowned",
        "smiled",
        "smirked",
        "exhaled",
        "inhaled",
        "sighed",
        "shivered",
        "flinched",
        "twitched",
        "jumped",
        "tightened",
        "loosened",
        "pressed",
        "clenched",
        "unclenched",
    }
)

# Sensory adjectives / nouns. If a repeated phrase contains one of these,
# bias it toward "sensory repetition".
SENSORY_TOKENS = frozenset(
    {
        "smell",
        "scent",
        "stink",
        "stench",
        "odour",
        "odor",
        "perfume",
        "taste",
        "tasted",
        "tang",
        "bitter",
        "sweet",
        "sour",
        "salty",
        "metallic",
        "coppery",
        "iron",
        "rusty",
        "warm",
        "cold",
        "icy",
        "hot",
        "burning",
        "cool",
        "sound",
        "noise",
        "echo",
        "whisper",
        "hum",
        "buzz",
    }
)

# Tokens commonly inside structural tics like "the kind of X that Y" or
# "the first time in X". Used as a hint for the structural category.
STRUCTURAL_HINTS = frozenset({"kind", "sort", "type", "first", "last", "only", "way"})

# ---------------------------------------------------------------------------
# Adverb density thresholds (per 1000 words)
# ---------------------------------------------------------------------------

ADVERB_MEDIUM_PER_1K = 8.0
ADVERB_HIGH_PER_1K = 14.0

# `-ly` words that are NOT adverbs or are unavoidable (pronouns, nouns,
# common function words). Excluded from the density count to keep the signal
# meaningful.
LY_EXCLUSIONS = frozenset(
    {
        # Not adverbs
        "only",
        "family",
        "belly",
        "jelly",
        "rally",
        "folly",
        "holly",
        "silly",
        "bully",
        "lily",
        "ally",
        "really",  # "really" is an adverb but so
        # common (often in dialogue) that flagging it adds noise
        "early",
        "lovely",
        "lonely",
        "lively",
        "friendly",
        "deadly",
        "ugly",
        "holy",
        "homely",
        "ghastly",
        "ghostly",
        "gnarly",
        "scholarly",
        "timely",
        "costly",
        "oily",
        "hilly",
        "jolly",
        "chilly",
        "wooly",
        "woolly",
        "manly",
        "knightly",
        "kingly",
        "queenly",
        "princely",
        # Proper/place names that often end in -ly (kept small)
        "italy",
    }
)

# ---------------------------------------------------------------------------
# Filter words (POV distancing) thresholds
# ---------------------------------------------------------------------------

# Per-chapter thresholds — counts per 1000 words.
FILTER_WORD_MEDIUM_PER_1K = 3.0
FILTER_WORD_HIGH_PER_1K = 6.0

# ---------------------------------------------------------------------------
# Snapshot detector
# ---------------------------------------------------------------------------

SNAPSHOT_THRESHOLD_DEFAULT = 5

# Fallback action verbs when the reference file is missing.
ACTION_VERBS_FALLBACK = frozenset(
    {
        "walk",
        "run",
        "move",
        "step",
        "reach",
        "grab",
        "turn",
        "look",
        "sit",
        "stand",
        "open",
        "close",
        "push",
        "pull",
        "say",
        "ask",
        "tell",
        "call",
        "enter",
        "leave",
        "fall",
        "rise",
        "jump",
        "catch",
        "throw",
        "pull",
        "lift",
        "carry",
        "take",
        "give",
        "find",
        "decide",
        "realize",
        "notice",
    }
)

# ---------------------------------------------------------------------------
# Question-as-statement detector
# ---------------------------------------------------------------------------

# Interrogative openers. First token of the dialogue. Covers wh-questions and
# yes/no aux-verb questions.
QUESTION_OPENERS = frozenset(
    {
        # wh-questions
        "who",
        "what",
        "where",
        "when",
        "why",
        "how",
        "which",
        "whose",
        # aux-verb yes/no questions
        "do",
        "does",
        "did",
        "is",
        "are",
        "was",
        "were",
        "am",
        "can",
        "could",
        "will",
        "would",
        "shall",
        "should",
        "may",
        "might",
        "must",
        "have",
        "has",
        "had",
    }
)

# Contraction forms tokenised as the leading aux verb (e.g. "don't" → "don").
QUESTION_OPENER_CONTRACTIONS = frozenset(
    {
        "don",
        "doesn",
        "didn",
        "isn",
        "aren",
        "wasn",
        "weren",
        "can",
        "couldn",
        "won",
        "wouldn",
        "shouldn",
        "hasn",
        "haven",
        "hadn",
    }
)

# ---------------------------------------------------------------------------
# Callback scanner
# ---------------------------------------------------------------------------

CALLBACK_DEFERRED_SILENCE = 10  # chapters of silence before deferred → finding

# ---------------------------------------------------------------------------
# Memoir thresholds
# ---------------------------------------------------------------------------

TIMELINE_AMBIGUITY_MEDIUM_PER_1K = 3.0
TIMELINE_AMBIGUITY_HIGH_PER_1K = 6.0

PLATITUDE_MEDIUM_THRESHOLD = 2  # per chapter (absolute count)
PLATITUDE_HIGH_THRESHOLD = 3

# ---------------------------------------------------------------------------
# Cliché phrases (curated fallback)
# ---------------------------------------------------------------------------

# Curated list of the worst-offender fiction clichés. Kept deliberately short
# — better to catch the 30 phrases that are unambiguously stale than to
# false-positive on borderline imagery. Each entry compiled case-insensitive,
# word-bounded where needed.
CLICHE_PHRASES: tuple[str, ...] = (
    # Cardiovascular clichés
    "blood ran cold",
    "heart skipped a beat",
    "heart sank",
    "heart pounded in his chest",
    "heart pounded in her chest",
    "blood boiled",
    "pulse quickened",
    # Ocular / facial clichés
    "eyes widened in horror",
    "eyes narrowed",
    "rolled her eyes",
    "rolled his eyes",
    "locked eyes",
    "eyes met across the room",
    # Time / cosmic clichés
    "time stood still",
    "time seemed to slow",
    "the world fell away",
    "everything went black",
    "an eternity passed",
    # Breath / voice clichés
    "breath caught in her throat",
    "breath caught in his throat",
    "lump in his throat",
    "lump in her throat",
    "barely above a whisper",
    # Weather / atmosphere
    "it was a dark and stormy night",
    "a chill ran down his spine",
    "a chill ran down her spine",
    "hair stood on end",
    "hair on the back of his neck stood",
    "hair on the back of her neck stood",
    # Misc narrative
    "little did he know",
    "little did she know",
    "only time would tell",
    "sight for sore eyes",
    "needle in a haystack",
    "calm before the storm",
)


__all__ = [
    "ACTION_VERBS_FALLBACK",
    "ADVERB_HIGH_PER_1K",
    "ADVERB_MEDIUM_PER_1K",
    "BLOCKING_VERBS",
    "BODY_PARTS",
    "CALLBACK_DEFERRED_SILENCE",
    "CLICHE_PHRASES",
    "DEFAULT_MIN_OCCURRENCES",
    "DEFAULT_NGRAM_SIZES",
    "FILTER_WORD_HIGH_PER_1K",
    "FILTER_WORD_MEDIUM_PER_1K",
    "LY_EXCLUSIONS",
    "PLATITUDE_HIGH_THRESHOLD",
    "PLATITUDE_MEDIUM_THRESHOLD",
    "QUESTION_OPENER_CONTRACTIONS",
    "QUESTION_OPENERS",
    "SENSORY_TOKENS",
    "SNAPSHOT_THRESHOLD_DEFAULT",
    "STOP_WORDS",
    "STRUCTURAL_HINTS",
    "TIMELINE_AMBIGUITY_HIGH_PER_1K",
    "TIMELINE_AMBIGUITY_MEDIUM_PER_1K",
]
