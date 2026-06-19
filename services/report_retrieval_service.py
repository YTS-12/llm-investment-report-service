from services.company_identity_service import company_search_variants, normalize_company_name


def _normalize_company(value: str) -> str:
    return normalize_company_name(value).strip().lower().replace(" ", "")


def _rank_company_hits(hits: list[dict], company: str) -> list[dict]:
    target = _normalize_company(company)
    exact = [hit for hit in hits if _normalize_company(hit.get("company", "")) == target]
    if exact:
        return exact

    contains = [
        hit
        for hit in hits
        if target and target in _normalize_company(hit.get("company", ""))
    ]
    if contains:
        return contains

    return hits


def _dedupe_hits(hits: list[dict]) -> list[dict]:
    seen: set[str] = set()
    deduped = []
    for hit in hits:
        doc_id = hit.get("doc_id", "")
        if doc_id in seen:
            continue
        seen.add(doc_id)
        deduped.append(hit)
    return deduped


def find_previous_reports(company: str, limit: int = 3):
    """
    company 기준으로 과거 보고서 검색
    """
    from indexing.meili_indexer import search_documents

    company = normalize_company_name(company)
    hits = []
    for variant in company_search_variants(company):
        result = search_documents("reports", variant, limit=max(limit * 3, 10))
        hits.extend(result.get("hits", []))
    hits = _dedupe_hits(hits)
    ranked = _rank_company_hits(hits, company)
    target = _normalize_company(company)
    ranked = [
        hit for hit in ranked
        if _normalize_company(hit.get("company", "")) == target
    ]
    # NOTE: 과거에는 여기서 회사명이 final_report/markdown_report 본문에
    # 문자열로 포함되는지까지 추가로 걸렀으나, markdown_report는 Meili에
    # 색인되지 않는(항상 비어 있는) 필드라 정상 보고서를 탈락시키는 버그였다.
    # company 필드 정확 일치만으로 충분히 정밀하므로 본문 필터는 제거한다.
    return ranked[:limit]


def search_reports(company: str = "", session_id: str = "", limit: int = 10):
    from indexing.meili_indexer import search_documents

    company = normalize_company_name(company) if company else ""
    hits = []
    if company:
        for variant in company_search_variants(company):
            result = search_documents("reports", variant, limit=max(limit * 3, 10))
            hits.extend(result.get("hits", []))
    else:
        result = search_documents("reports", "", limit=max(limit * 3, 10))
        hits = result.get("hits", [])
    hits = _dedupe_hits(hits)
    if company:
        hits = _rank_company_hits(hits, company)
    if session_id:
        hits = [hit for hit in hits if hit.get("session_id") == session_id]
    return hits[:limit]
