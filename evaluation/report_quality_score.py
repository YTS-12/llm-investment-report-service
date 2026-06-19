def score_required_sections(report_text: str, expected_sections: list[str]) -> dict:
    found = sum(1 for sec in expected_sections if sec in report_text)
    total = len(expected_sections)
    return {
        "score": found / total if total else 0,
        "found": found,
        "total": total,
    }


def score_expected_keywords(report_text: str, expected_keywords: list[str]) -> dict:
    found = sum(1 for kw in expected_keywords if kw in report_text)
    total = len(expected_keywords)
    return {
        "score": found / total if total else 0,
        "found": found,
        "total": total,
    }


def overall_quality_score(section_score: float, keyword_score: float) -> float:
    return round((section_score * 0.6) + (keyword_score * 0.4), 4)