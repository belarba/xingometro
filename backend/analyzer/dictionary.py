import json
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
        self._normalized_map: dict[str, dict] = {}
        self._load()

    def _load(self):
        path = DATA_DIR / "swear_dictionary.json"
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
        self._terms = data["terms"]
        for term in self._terms:
            normalized = self._normalize(term["word"])
            self._normalized_map[normalized] = term

    @staticmethod
    def _normalize(text: str) -> str:
        return unidecode(text).lower().strip()

    def find_matches(self, text: str) -> list[SwearMatch]:
        normalized = self._normalize(text)
        matches = []
        for norm_word, term in self._normalized_map.items():
            if norm_word in normalized:
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
