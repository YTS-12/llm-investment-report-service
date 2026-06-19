import re
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta
from typing import Any

from data_collectors.dart_api import find_corp_code, find_stock_code, search_disclosures
from data_collectors.ecos_api import collect_macro_series_context
from data_collectors.naver_finance_scraper import parse_naver_finance_basic
from data_collectors.naver_news_api import search_news
from data_collectors.normalize import (
    normalize_disclosures,
    normalize_ecos_rows,
    normalize_news_items,
    normalize_price_history,
)
from data_collectors.yfinance_api import get_basic_info, get_price_history
from services.company_identity_service import normalize_company_name
from services.query_normalizer_service import normalize_query
from utils.logger import logger


COMPANY_TICKER_MAP = {
    "삼성전자": {"yahoo": "005930.KS", "naver": "005930"},
    "sk하이닉스": {"yahoo": "000660.KS", "naver": "000660"},
    "현대차": {"yahoo": "005380.KS", "naver": "005380"},
}

DISCLOSURE_NOT_FOUND_MESSAGE = "최근 공시를 찾지 못했습니다."
DISCLOSURE_CORP_CODE_FALLBACK = (
    "회사명에 해당하는 DART corp code를 찾지 못했습니다. 추가 공시 메모 입력으로 보완할 수 있습니다."
)
DISCLOSURE_COLLECTION_ERROR = (
    "자동 공시 수집 중 오류가 발생했습니다. 추가 공시 메모 입력으로 보완할 수 있습니다."
)
DISCLOSURE_CATEGORY_WEIGHTS = {
    "earnings_update": 100,
    "capital_change": 95,
    "financing": 92,
    "contract": 90,
    "shareholder_return": 88,
    "ownership_change": 82,
    "mna": 82,
    "event_risk": 80,
    "capex": 76,
    "dividend": 72,
    "material_event": 72,
    "management_event": 68,
    "periodic_report": 55,
    "ir_event": 40,
    "general_disclosure": 20,
}

# 공시 수집 설정
# OpenDART list.json의 pblntf_ty(공시유형)로 나눠 수집한다. 지분공시(D, 종목당 수천 건)에
# 핵심 공시가 묻히지 않도록 정기공시(A)·주요사항보고(B)·거래소공시(I=잠정실적·배당 등)를
# 분리 수집해 반드시 확보한다.
DISCLOSURE_PRIORITY_TYPES = ("A", "B", "I")
DISCLOSURE_PER_TYPE_COUNT = 30       # 유형별로 가져올 공시 수
DISCLOSURE_SUMMARY_TOP_K = 5         # LLM 입력 텍스트에 담을 상위 건수
DISCLOSURE_EVENTS_TOP_K = 15         # 구조화 저장(disclosure_events)에 보존할 건수
DISCLOSURE_PROTECTED_IMPORTANCE = 5  # 이 이상 중요도는 절단에서 항상 보호


def _normalize_company_key(company: str) -> str:
    normalized = normalize_company_name(company)
    return normalize_query(normalized).replace(" ", "").lower()


def resolve_ticker(company: str) -> dict[str, str]:
    company_key = _normalize_company_key(company)
    if company_key in COMPANY_TICKER_MAP:
        return COMPANY_TICKER_MAP[company_key]

    stock_code = re.sub(r"\D", "", company or "")
    if len(stock_code) == 6:
        return {"yahoo": f"{stock_code}.KS", "naver": stock_code}

    # 하드코딩 맵·6자리 코드가 아니면 DART corp 테이블에서 상장 종목코드를 자동 해석한다.
    # 이미 받아오는 DART 데이터에 전 상장사 stock_code가 들어 있어, 추가 의존성 없이
    # 커버리지를 3종목 → 전 상장사로 넓힌다. (KOSDAQ의 Yahoo 접미사는 .KS로 가정 →
    # Yahoo 시세는 일부 실패할 수 있으나 네이버 재무는 코드만으로 정상 동작한다.)
    dart_code = find_stock_code(company)
    if len(dart_code) == 6:
        return {"yahoo": f"{dart_code}.KS", "naver": dart_code}

    return {"yahoo": "", "naver": ""}


def strip_html(text: str) -> str:
    return re.sub(r"<[^>]+>", "", text or "").strip()


def summarize_news_docs(news_docs: list[dict], top_k: int = 5) -> str:
    lines = []
    for doc in news_docs[:top_k]:
        title = strip_html(doc.get("title", ""))
        summary = strip_html(doc.get("summary", ""))
        lines.append(f"- 제목: {title}\n  요약: {summary}")
    return "\n".join(lines)


def summarize_price_docs(price_docs: list[dict], top_k: int = 5) -> str:
    lines = []
    for doc in price_docs[-top_k:]:
        lines.append(
            f"- 날짜: {doc.get('date')}, 종가: {doc.get('close')}, 거래량: {doc.get('volume')}"
        )
    return "\n".join(lines)


def summarize_naver_basic(naver_basic: dict[str, Any]) -> str:
    if not naver_basic:
        return ""

    lines = []
    head_fields = [
        ("stock_name", "종목명"),
        ("current_price", "현재가"),
        ("market_cap", "시가총액"),
        ("foreign_ratio", "외국인소진율"),
        ("investment_opinion", "투자의견"),
        ("target_price", "목표주가"),
        ("high_52w", "52주 최고가"),
        ("low_52w", "52주 최저가"),
        ("per", "PER(현재)"),
        ("eps", "EPS(현재)"),
        ("estimated_per", "추정 PER"),
        ("estimated_eps", "추정 EPS"),
        ("pbr", "PBR(현재)"),
        ("bps", "BPS(현재)"),
    ]
    for field, label in head_fields:
        value = naver_basic.get(field)
        if value:
            lines.append(f"- {label}: {value}")

    # 기업실적분석 표의 '최신 실적값'을 기간과 함께 제시(분기 우선, 흐름 지표는 연간도 함께).
    financials = naver_basic.get("financials", {}) or {}
    metric_labels = [
        ("revenue", "매출액", True),
        ("operating_income", "영업이익", True),
        ("net_income", "당기순이익", True),
        ("operating_margin", "영업이익률(%)", False),
        ("roe", "ROE(%)", False),
        ("debt_ratio", "부채비율(%)", False),
    ]
    for key, label, is_flow in metric_labels:
        metric = financials.get(key)
        if not metric:
            continue
        annual_period, annual_value = metric.get("annual", ("", ""))
        quarter_period, quarter_value = metric.get("quarter", ("", ""))
        parts = []
        if quarter_value:
            parts.append(f"최신 분기({quarter_period}) {quarter_value}")
        if annual_value and (is_flow or not quarter_value):
            parts.append(f"최근 연간({annual_period}) {annual_value}")
        if parts:
            lines.append(f"- {label}: " + ", ".join(parts))

    return "\n".join(lines)


def _rank_disclosures(disclosures: list[dict]) -> list[dict]:
    """공시를 (중요도 → 카테고리 가중치 → 접수일) 내림차순으로 정렬한다."""
    return sorted(
        disclosures,
        key=lambda item: (
            int(item.get("importance", 0) or 0),
            DISCLOSURE_CATEGORY_WEIGHTS.get(item.get("category", ""), 0),
            item.get("receipt_date", ""),
        ),
        reverse=True,
    )


def _select_disclosures(disclosures: list[dict], top_k: int) -> list[dict]:
    """랭킹 상위 top_k에, 절단으로 누락될 고중요도 공시를 더해 보호한다.

    실적·증자처럼 중요도가 높은 공시는 top_k를 넘더라도 빠지지 않게 한다.
    """
    ranked = _rank_disclosures(disclosures)
    head = ranked[:top_k]
    protected = [
        item
        for item in ranked[top_k:]
        if int(item.get("importance", 0) or 0) >= DISCLOSURE_PROTECTED_IMPORTANCE
    ]
    return head + protected


def build_disclosure_events(disclosures: list[dict], top_k: int = DISCLOSURE_EVENTS_TOP_K) -> list[dict]:
    """요약 텍스트와 동일한 랭킹으로 상위 공시의 '구조화 수치'를 보존한다.

    summarize_disclosures가 LLM 입력용 텍스트를 만든다면, 이 함수는 파서가
    추출한 detail_metrics(정밀 수치)를 구조 그대로 응답/저장에 싣기 위한 것이다.
    (과거에는 텍스트로만 풀려 LLM 단계에서 누락/변형될 위험이 있었다.)
    """
    events = []
    for item in _select_disclosures(disclosures, top_k):
        events.append({
            "report_name": item.get("report_name", ""),
            "receipt_date": item.get("receipt_date", ""),
            "corp_name": item.get("corp_name", ""),
            "category": item.get("category", ""),
            "importance": item.get("importance", ""),
            "signal": item.get("signal", ""),
            "event_name": item.get("event_name", ""),
            "detail_metrics": item.get("detail_metrics", {}) or {},
            "impact_summary": item.get("impact_summary", ""),
            "viewer_url": item.get("viewer_url", ""),
        })
    return events


def summarize_disclosures(disclosures: list[dict], top_k: int = DISCLOSURE_SUMMARY_TOP_K) -> str:
    if not disclosures:
        return DISCLOSURE_NOT_FOUND_MESSAGE

    selected = _select_disclosures(disclosures, top_k)

    lines = []
    for item in selected:
        category = item.get("category", "")
        importance = item.get("importance", "")
        signal = item.get("signal", "")
        event_name = item.get("event_name", "")
        viewer_url = item.get("viewer_url", "")
        impact_summary = item.get("impact_summary", "")
        body_excerpt = item.get("body_excerpt", "")
        detail_metrics = item.get("detail_metrics", {}) or {}

        extra = []
        if category:
            extra.append(f"분류: {category}")
        if importance:
            extra.append(f"중요도: {importance}/5")
        if signal:
            extra.append(f"시그널: {signal}")
        if event_name:
            extra.append(f"세부 이벤트: {event_name}")
        if viewer_url:
            extra.append(f"원문: {viewer_url}")

        lines.append(
            f"- 접수일: {item.get('receipt_date', '')}, 공시명: {item.get('report_name', '')}, 제출사: {item.get('corp_name', '')}"
        )
        if extra:
            lines.append(f"  {', '.join(extra)}")

        if detail_metrics:
            detail_parts = [
                f"{key}: {value}"
                for key, value in detail_metrics.items()
                if value
            ]
            if detail_parts:
                lines.append(f"  추출 세부값: {', '.join(detail_parts[:5])}")

        if impact_summary:
            lines.append(f"  영향 요약: {impact_summary}")

        if body_excerpt:
            lines.append(f"  본문 발췌: {body_excerpt}")

    return "\n".join(lines)


def _collect_news_data(company: str) -> tuple[list[dict], str]:
    try:
        news_json = search_news(company, display=10, sort="date")
        news_docs = normalize_news_items(news_json, company)
        return news_docs, summarize_news_docs(news_docs, top_k=5)
    except Exception as exc:
        logger.warning("News collection failed | company=%s | error=%s", company, repr(exc))
        return [], ""


def _fetch_priority_disclosures(corp_code: str, start_date: str, end_date: str) -> dict:
    """공시유형(pblntf_ty)별로 나눠 수집해 합친다(rcept_no 기준 중복 제거).

    지분공시(D)가 수천 건씩 쌓이는 종목에서 '최근순 일괄 수집'을 하면 실적·증자·잠정실적
    같은 핵심 공시가 절단돼 사라진다. 정기공시(A)·주요사항(B)·거래소공시(I=잠정실적/배당 등)를
    유형별로 따로 가져와 핵심 공시를 반드시 확보한다.
    """
    seen: set = set()
    merged: list[dict] = []
    for pblntf_ty in DISCLOSURE_PRIORITY_TYPES:
        try:
            result = search_disclosures(
                corp_code,
                start_date,
                end_date,
                page_count=DISCLOSURE_PER_TYPE_COUNT,
                pblntf_ty=pblntf_ty,
            )
        except Exception as exc:
            logger.warning(
                "Disclosure type fetch failed | type=%s | error=%s", pblntf_ty, repr(exc)
            )
            continue
        for item in result.get("list", []) or []:
            key = item.get("rcept_no", "") or id(item)
            if key in seen:
                continue
            seen.add(key)
            merged.append(item)
    return {"list": merged}


def _dedupe_earnings_disclosures(disclosures: list[dict]) -> list[dict]:
    """잠정실적(earnings_update)의 정정/원본/과거분기 중복을 제거하고 최신 1건만 남긴다.

    같은 분기 실적이 [기재정정]·원본으로 중복되고 단위(조/억)가 들쭉날쭉하면 LLM이
    '수치 불일치'로 오판한다. 접수일이 가장 최신이고, 매출이 억원 표(콤마 정수) 형태로
    깔끔하게 추출된 변형 1건만 채택한다.
    """
    earnings = [d for d in disclosures if d.get("category") == "earnings_update"]
    if len(earnings) <= 1:
        return disclosures
    others = [d for d in disclosures if d.get("category") != "earnings_update"]

    def quality(item: dict) -> tuple:
        revenue = str((item.get("detail_metrics") or {}).get("revenue", ""))
        # 억원 표 정상값(콤마 정수)을 조 단위 소수(133.87)보다 우선
        clean_unit = 1 if ("," in revenue and "." not in revenue) else 0
        return (
            item.get("receipt_date", ""),
            clean_unit,
            len(item.get("detail_metrics") or {}),
        )

    best = max(earnings, key=quality)
    return others + [best]


def _collect_disclosures_data(company: str) -> tuple[str, list[dict]]:
    try:
        corp_code = find_corp_code(company)
        if not corp_code:
            return DISCLOSURE_CORP_CODE_FALLBACK, []

        end_date = datetime.today().strftime("%Y%m%d")
        start_date = (datetime.today() - timedelta(days=365)).strftime("%Y%m%d")
        disclosures_json = _fetch_priority_disclosures(corp_code, start_date, end_date)
        normalized_disclosures = normalize_disclosures(disclosures_json)
        normalized_disclosures = _dedupe_earnings_disclosures(normalized_disclosures)
        return (
            summarize_disclosures(normalized_disclosures, top_k=DISCLOSURE_SUMMARY_TOP_K),
            build_disclosure_events(normalized_disclosures, top_k=DISCLOSURE_EVENTS_TOP_K),
        )
    except Exception as exc:
        logger.warning(
            "Disclosure collection failed | company=%s | error=%s",
            company,
            repr(exc),
        )
        return DISCLOSURE_COLLECTION_ERROR, []


def _collect_yahoo_market_data(yahoo_ticker: str) -> tuple[list[str], list[dict], dict[str, Any]]:
    if not yahoo_ticker:
        return [], [], {}

    try:
        market_data_parts: list[str] = []
        price_history = get_price_history(yahoo_ticker, period="1mo")
        price_docs = normalize_price_history(price_history)
        if price_docs:
            market_data_parts.append(summarize_price_docs(price_docs, top_k=5))
        yahoo_basic_info = get_basic_info(yahoo_ticker)
        return market_data_parts, price_docs, yahoo_basic_info
    except Exception as exc:
        logger.warning(
            "Yahoo market collection failed | ticker=%s | error=%s",
            yahoo_ticker,
            repr(exc),
        )
        return [], [], {}


def _collect_naver_market_data(naver_ticker: str) -> tuple[list[str], dict[str, Any]]:
    if not naver_ticker:
        return [], {}

    try:
        naver_basic = parse_naver_finance_basic(naver_ticker)
        market_data_parts = []
        naver_summary = summarize_naver_basic(naver_basic)
        if naver_summary:
            market_data_parts.append(naver_summary)
        return market_data_parts, naver_basic
    except Exception as exc:
        logger.warning(
            "Naver finance collection failed | ticker=%s | error=%s",
            naver_ticker,
            repr(exc),
        )
        return [], {}


def _collect_market_data(yahoo_ticker: str, naver_ticker: str) -> dict[str, Any]:
    with ThreadPoolExecutor(max_workers=2) as executor:
        yahoo_future = executor.submit(_collect_yahoo_market_data, yahoo_ticker)
        naver_future = executor.submit(_collect_naver_market_data, naver_ticker)

        yahoo_parts, price_docs, yahoo_basic_info = yahoo_future.result()
        naver_parts, naver_basic = naver_future.result()

    return {
        "market_data_parts": [*yahoo_parts, *naver_parts],
        "price_docs": price_docs,
        "yahoo_basic_info": yahoo_basic_info,
        "naver_basic": naver_basic,
    }


def _collect_macro_data() -> tuple[list[dict], str, dict[str, Any]]:
    try:
        macro_context = collect_macro_series_context()
        macro_docs: list[dict] = []
        for series_name, series_rows in macro_context.get("series_rows", {}).items():
            macro_docs.extend(normalize_ecos_rows(series_rows, series_name))

        return macro_docs, macro_context.get("macro_summary", ""), macro_context
    except Exception as exc:
        logger.warning("Macro collection failed | error=%s", repr(exc))
        return [], "", {}


def collect_all_data(company: str) -> dict[str, Any]:
    company = normalize_company_name(company)
    tickers = resolve_ticker(company)
    yahoo_ticker = tickers["yahoo"]
    naver_ticker = tickers["naver"]

    with ThreadPoolExecutor(max_workers=4) as executor:
        news_future = executor.submit(_collect_news_data, company)
        disclosures_future = executor.submit(_collect_disclosures_data, company)
        market_future = executor.submit(_collect_market_data, yahoo_ticker, naver_ticker)
        macro_future = executor.submit(_collect_macro_data)

        news_docs, news_summary = news_future.result()
        disclosures_summary, disclosure_events = disclosures_future.result()
        market_result = market_future.result()
        macro_docs, macro_summary, macro_context = macro_future.result()

    return {
        "company": company,
        "news_docs": news_docs,
        "news_summary": news_summary,
        "price_docs": market_result["price_docs"],
        "market_data_summary": "\n".join(
            part for part in market_result["market_data_parts"] if part
        ),
        "yahoo_basic_info": market_result["yahoo_basic_info"],
        "naver_basic": market_result["naver_basic"],
        "macro_docs": macro_docs,
        "macro_context": macro_context,
        "macro_summary": macro_summary,
        "disclosures_summary": disclosures_summary,
        "disclosure_events": disclosure_events,
    }
