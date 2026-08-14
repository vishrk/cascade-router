import re

CODE_PATTERN = re.compile(r"```|\bdef\s+\w+\(|\bclass\s+\w+|\bfunction\s+\w+\(|[{};]\s*$", re.MULTILINE)
MATH_PATTERN = re.compile(r"\$.+?\$|\\\(.+?\\\)|[∫∑√π≤≥±]|\b\d+\s*[\^]\s*\d+|\bsolve for\b", re.IGNORECASE)
HARD_KEYWORDS = re.compile(
    r"\b(prove|derive|optimi[sz]e|design|architect|compare and contrast|step[- ]by[- ]step|"
    r"trade-?offs?|explain why|analyze)\b",
    re.IGNORECASE,
)
EASY_KEYWORDS = re.compile(r"\b(what is|who is|when (was|did)|define|list)\b", re.IGNORECASE)


def extract_features(prompt: str) -> dict:
    return {
        "token_count": len(prompt.split()),
        "has_code": bool(CODE_PATTERN.search(prompt)),
        "has_math": bool(MATH_PATTERN.search(prompt)),
        "has_hard_keywords": bool(HARD_KEYWORDS.search(prompt)),
        "has_easy_keywords": bool(EASY_KEYWORDS.search(prompt)),
    }


def score(prompt: str) -> float:
    """Heuristic complexity score in [0, 1]. Higher = more likely to need the strong model."""
    f = extract_features(prompt)

    value = min(f["token_count"] / 200, 0.3)
    if f["has_code"]:
        value += 0.3
    if f["has_math"]:
        value += 0.2
    if f["has_hard_keywords"]:
        value += 0.2
    if f["has_easy_keywords"] and not (f["has_code"] or f["has_math"]):
        value -= 0.15

    return max(0.0, min(1.0, value))
