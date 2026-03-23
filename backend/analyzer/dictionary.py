import json
import re
from dataclasses import dataclass

from unidecode import unidecode

from backend.config import DATA_DIR


@dataclass
class SwearMatch:
    word: str
    level: int
    weight: float
    category: str


class SwearDictionary:
    def __init__(self):
        self._terms: list[dict] = []
        self._patterns: list[tuple[re.Pattern, dict]] = []
        self._load()

    def _load(self):
        path = DATA_DIR / "swear_dictionary.json"
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
        self._terms = data["terms"]
        self._patterns = []
        for term in self._terms:
            normalized = self._normalize(term["word"])
            pattern = re.compile(
                r"\b" + re.escape(normalized) + r"\b",
                re.IGNORECASE,
            )
            self._patterns.append((pattern, term))

    @staticmethod
    def _normalize(text: str) -> str:
        return unidecode(text).lower().strip()

    def find_matches(self, text: str) -> list[SwearMatch]:
        normalized = self._normalize(text)
        matches = []
        for pattern, term in self._patterns:
            if pattern.search(normalized):
                matches.append(
                    SwearMatch(
                        word=term["word"],
                        level=term["level"],
                        weight=term["weight"],
                        category=term["category"],
                    )
                )
        return matches


# Singleton
swear_dictionary = SwearDictionary()
