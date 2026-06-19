"""Lightweight text-similarity helpers.

Used by news deduplication to detect near-duplicate article titles without
pulling in heavy NLP dependencies. Pure standard library.
"""
import re
from difflib import SequenceMatcher


def normalize_for_compare(text: str) -> str:
    """Lowercase, strip common punctuation, and collapse whitespace."""
    text = (text or "").lower()
    text = re.sub(r"[\[\]\(\)\-–—_:\"'`·,./]", " ", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text


def ratio(a: str, b: str) -> float:
    """Return a 0.0–1.0 character-sequence similarity ratio."""
    return SequenceMatcher(None, a or "", b or "").ratio()


def is_similar(a: str, b: str, threshold: float = 0.9) -> bool:
    """Return True when two strings are near-duplicates at the given threshold."""
    return ratio(a, b) >= threshold
