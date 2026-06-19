def contains_required_sections(text: str) -> dict:
    required_sections = [
        "기업 개요",
        "리스크",
        "종합 판단",
        "관찰 포인트",
    ]

    result = {}
    for sec in required_sections:
        result[sec] = sec in text
    return result


def contains_keywords(text: str, keywords: list[str]) -> dict:
    return {kw: (kw in text) for kw in keywords}