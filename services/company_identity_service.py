import re

from services.query_normalizer_service import normalize_query


COMPANY_ALIAS_MAP = {
    "삼성": "삼성전자",
    "삼성전자": "삼성전자",
    "samsung electronics": "삼성전자",
    "sk하이닉스": "SK하이닉스",
    "sk hynix": "SK하이닉스",
    "하이닉스": "SK하이닉스",
    "현대자동차": "현대차",
    "현대차": "현대차",
}


def normalize_company_name(company: str) -> str:
    text = normalize_query(company).strip()
    compact = text.replace(" ", "")
    lowered = compact.lower()

    if text in COMPANY_ALIAS_MAP:
        return COMPANY_ALIAS_MAP[text]
    if compact in COMPANY_ALIAS_MAP:
        return COMPANY_ALIAS_MAP[compact]
    if lowered in {key.lower(): value for key, value in COMPANY_ALIAS_MAP.items()}:
        lowered_map = {key.lower(): value for key, value in COMPANY_ALIAS_MAP.items()}
        return lowered_map[lowered]

    stock_code = re.sub(r"\D", "", text or "")
    if len(stock_code) == 6:
        return stock_code

    return text


def company_search_variants(company: str) -> list[str]:
    normalized = normalize_company_name(company)
    compact = normalized.replace(" ", "")
    variants = [normalized, compact]
    return list(dict.fromkeys([item for item in variants if item]))
