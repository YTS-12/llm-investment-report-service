import re
from typing import Any, Dict

import requests
from bs4 import BeautifulSoup

from utils.logger import logger
from utils.retry import with_retries


HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/122.0.0.0 Safari/537.36"
    )
}

# 네이버 '기업실적분석' 표의 행 라벨 → 내부 키
FINANCIAL_ROW_LABELS = {
    "매출액": "revenue",
    "영업이익": "operating_income",
    "당기순이익": "net_income",
    "영업이익률": "operating_margin",
    "순이익률": "net_margin",
    "ROE(지배주주)": "roe",
    "부채비율": "debt_ratio",
    "당좌비율": "quick_ratio",
    "유보율": "retention_ratio",
    "EPS(원)": "eps",
    "PER(배)": "per",
    "BPS(원)": "bps",
    "PBR(배)": "pbr",
    "주당배당금(원)": "dividend_per_share",
    "시가배당률(%)": "dividend_yield",
    "배당성향(%)": "payout_ratio",
}


@with_retries(
    max_attempts=3,
    base_delay=1.0,
    retry_on=(requests.ConnectionError, requests.Timeout),
)
def get_naver_finance_html(ticker: str) -> str:
    url = f"https://finance.naver.com/item/main.naver?code={ticker}"
    response = requests.get(url, headers=HEADERS, timeout=20)
    response.raise_for_status()
    return response.text


def _clean_text(text: str) -> str:
    text = text or ""
    text = text.replace("\xa0", " ")
    text = re.sub(r"\s+", " ", text)
    return text.strip()


def _normalize_value(value: str) -> str:
    value = _clean_text(value)
    return "" if value in {"", "-", "N/A"} else value


def _extract_pattern(text: str, pattern: str) -> str:
    match = re.search(pattern, text, re.DOTALL)
    if not match:
        return ""
    return _normalize_value(match.group(1))


def _extract_two_values(text: str, pattern: str) -> tuple[str, str]:
    match = re.search(pattern, text, re.DOTALL)
    if not match:
        return "", ""
    return _normalize_value(match.group(1)), _normalize_value(match.group(2))


def _slice_after_label(text: str, label: str) -> str:
    try:
        return text.split(label, 1)[1]
    except IndexError:
        return ""


def _extract_pair_after_anchor(
    text: str,
    anchor: str,
    pair_pattern: str,
    window: int = 400,
) -> tuple[str, str]:
    tail = _slice_after_label(text, anchor)
    if not tail:
        return "", ""
    snippet = tail[:window]
    return _extract_two_values(snippet, pair_pattern)


def _parse_financial_table(soup) -> dict | None:
    """'기업실적분석' 표를 컬럼(기간)·행(항목) 구조로 파싱한다.

    헤더 1행: '최근 연간 실적'(colspan N) / '최근 분기 실적'으로 연간·분기 컬럼 구분.
    헤더 2행: 각 컬럼의 기간(2025.12, 2026.03, 2026.06 (E) ...).
    """
    sec = soup.select_one("div.cop_analysis") or soup.select_one("div.section.cop_analysis")
    table = sec.select_one("table") if sec else None
    if not table:
        return None

    head_rows = table.select("thead tr")
    if len(head_rows) < 2:
        return None

    annual_count = 0
    for th in head_rows[0].find_all(["th", "td"]):
        if "연간" in th.get_text():
            try:
                annual_count = int(th.get("colspan", 1))
            except (TypeError, ValueError):
                annual_count = 1

    periods = []
    for i, th in enumerate(head_rows[1].find_all(["th", "td"])):
        raw = th.get_text(" ", strip=True)
        periods.append({
            "period": raw.replace("(E)", "").strip(),
            "kind": "annual" if i < annual_count else "quarter",
            "estimate": "(E)" in raw,
        })

    rows: dict[str, list[str]] = {}
    for tr in table.select("tbody tr"):
        th = tr.find("th")
        if not th:
            continue
        label = _clean_text(th.get_text(" ", strip=True))
        rows[label] = [td.get_text(" ", strip=True) for td in tr.find_all("td")]

    return {"periods": periods, "rows": rows}


def _latest_actual(values: list, periods: list, kind: str) -> tuple[str, str]:
    """해당 종류(annual/quarter)에서 추정치(E)가 아닌 가장 최근(우측) 실적값 (기간, 값)."""
    for i in range(len(periods) - 1, -1, -1):
        period = periods[i]
        if period["kind"] != kind or period["estimate"]:
            continue
        if i < len(values):
            value = _normalize_value(values[i])
            if value:
                return period["period"], value
    return "", ""


def _build_financials(table_data: dict | None) -> dict:
    """각 재무 항목의 '최신 연간/분기 실적값(기간 포함)'을 구조화한다."""
    if not table_data:
        return {}
    periods = table_data["periods"]
    compact = {lbl.replace(" ", ""): key for lbl, key in FINANCIAL_ROW_LABELS.items()}

    financials: dict[str, dict] = {}
    for row_label, values in table_data["rows"].items():
        key = FINANCIAL_ROW_LABELS.get(row_label) or compact.get(row_label.replace(" ", ""))
        if not key:
            continue
        financials[key] = {
            "annual": _latest_actual(values, periods, "annual"),
            "quarter": _latest_actual(values, periods, "quarter"),
        }
    return financials


def parse_naver_finance_basic(ticker: str) -> Dict[str, Any]:
    html = get_naver_finance_html(ticker)
    soup = BeautifulSoup(html, "lxml")
    page_text = _clean_text(soup.get_text(" ", strip=True))

    result: Dict[str, Any] = {
        "ticker": ticker,
        "source": "naver_finance",
        "stock_name": "",
        "current_price": "",
        "market_cap": "",
        "foreign_ratio": "",
        "target_price": "",
        "investment_opinion": "",
        "high_52w": "",
        "low_52w": "",
        "per": "",
        "eps": "",
        "estimated_per": "",
        "estimated_eps": "",
        "pbr": "",
        "bps": "",
        "financials": {},
    }

    title_area = soup.select_one("div.wrap_company h2 a")
    if title_area:
        result["stock_name"] = _clean_text(title_area.get_text(strip=True))

    price_area = soup.select_one("p.no_today span.blind")
    if price_area:
        result["current_price"] = _clean_text(price_area.get_text(strip=True))

    result["market_cap"] = _extract_pattern(
        page_text,
        r"시가총액\s+시가총액\s+([0-9,조억만원\s]+?원)",
    )
    result["foreign_ratio"] = _extract_pattern(
        page_text,
        r"외국인소진율\(B/A\).*?([0-9.]+%)",
    )

    opinion_match = re.search(
        r"투자의견\s+투자의견\s+l\s+목표주가\s+([0-9.]+)\s+([가-힣]+)\s+l\s+([0-9,]+)",
        page_text,
    )
    if opinion_match:
        result["investment_opinion"] = (
            f"{_normalize_value(opinion_match.group(1))} {_normalize_value(opinion_match.group(2))}"
        ).strip()
        result["target_price"] = _normalize_value(opinion_match.group(3))

    high_52w, low_52w = _extract_two_values(
        page_text,
        r"52주최고\s+l\s+최저\s+([0-9,]+)\s+l\s+([0-9,]+)",
    )
    result["high_52w"] = high_52w
    result["low_52w"] = low_52w

    per, eps = _extract_pair_after_anchor(
        page_text,
        "PER/EPS",
        r"([0-9.]+)\s+배\s+l\s+([0-9,]+)\s+원",
    )
    result["per"] = per
    result["eps"] = eps

    est_per, est_eps = _extract_pair_after_anchor(
        page_text,
        "추정PER",
        r"([0-9.]+)\s+배\s+l\s+([0-9,]+)\s+원",
    )
    result["estimated_per"] = est_per
    result["estimated_eps"] = est_eps

    pbr, bps = _extract_pair_after_anchor(
        page_text,
        "PBR l BPS",
        r"([0-9.]+)\s+배\s+l\s+([0-9,]+)\s+원",
    )
    result["pbr"] = pbr
    result["bps"] = bps

    result["financials"] = _build_financials(_parse_financial_table(soup))

    if not result["stock_name"] and not result["current_price"]:
        # 핵심 필드가 비었다 = 네이버 금융 HTML 구조 변경 신호일 수 있음.
        logger.warning(
            "Naver finance parse yielded no key fields (HTML 구조 변경 가능) | ticker=%s",
            ticker,
        )

    return result
