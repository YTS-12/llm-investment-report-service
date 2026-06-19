import re


def normalize_query(query: str) -> str:
    text = (query or "").strip()
    text = re.sub(r"[^\w\s가-힣A-Za-z0-9.-]", " ", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text
