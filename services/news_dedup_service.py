import re
from typing import List, Dict, Any

from utils.text_similarity import is_similar


def clean_html(text: str) -> str:
    text = re.sub(r"<[^>]+>", "", text or "")
    return text.strip()


def normalize_title(title: str, stock_name: str = "") -> str:
    t = clean_html(title).lower()

    # 종목명 제거
    if stock_name:
        t = t.replace(stock_name.lower(), "")

    # 특수문자 정리
    t = re.sub(r"[\[\]\(\)\-–—_:\"'`·,./]", " ", t)
    t = re.sub(r"\s+", " ", t).strip()
    return t


def dedupe_news(news_docs: List[Dict[str, Any]], stock_name: str = "") -> List[Dict[str, Any]]:
    seen_urls = set()
    deduped = []

    for doc in news_docs:
        url = doc.get("url", "")
        if url and url in seen_urls:
            continue
        seen_urls.add(url)

        title = doc.get("title", "")
        norm_title = normalize_title(title, stock_name=stock_name)

        is_duplicate = False
        for existing in deduped:
            existing_norm = existing.get("_norm_title", "")
            if is_similar(norm_title, existing_norm, 0.9):
                is_duplicate = True
                break

        if not is_duplicate:
            new_doc = dict(doc)
            new_doc["title"] = clean_html(doc.get("title", ""))
            new_doc["summary"] = clean_html(doc.get("summary", ""))
            new_doc["_norm_title"] = norm_title
            deduped.append(new_doc)

    # 내부용 필드 제거
    for doc in deduped:
        doc.pop("_norm_title", None)

    return deduped
