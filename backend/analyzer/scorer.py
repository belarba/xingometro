import re

from backend.analyzer.dictionary import SwearMatch


def caps_ratio(text: str) -> float:
    alpha = [c for c in text if c.isalpha()]
    if not alpha:
        return 0.0
    return sum(1 for c in alpha if c.isupper()) / len(alpha)


def has_repeated_chars(text: str) -> bool:
    return bool(re.search(r"(.)\1{3,}", text))


def exclamation_count(text: str) -> int:
    return text.count("!")


def calculate_rage(post_text: str, matches: list[SwearMatch]) -> float:
    if not matches:
        return 0.0

    base = max(m.weight for m in matches)

    if caps_ratio(post_text) > 0.5:
        base *= 1.2
    if has_repeated_chars(post_text):
        base *= 1.1
    if exclamation_count(post_text) > 2:
        base *= 1.1
    if len(matches) > 3:
        base *= 1.3

    return min(base, 10.0)
