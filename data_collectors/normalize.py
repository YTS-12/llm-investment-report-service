import re
from typing import Any, Dict, List

from data_collectors.dart_api import (
    build_disclosure_viewer_url,
    extract_disclosure_details,
)


def normalize_news_items(news_json: Dict[str, Any], query: str) -> List[Dict[str, Any]]:
    items = news_json.get("items", [])
    normalized = []

    for idx, item in enumerate(items):
        normalized.append(
            {
                "doc_type": "news",
                "doc_id": f"news_{query}_{idx}",
                "query": query,
                "title": item.get("title", ""),
                "summary": item.get("description", ""),
                "url": item.get("originallink") or item.get("link", ""),
                "published_at": item.get("pubDate", ""),
                "source": "naver_news_api",
            }
        )

    return normalized


def normalize_disclosures(disclosure_json: Dict[str, Any]) -> List[Dict[str, Any]]:
    items = disclosure_json.get("list", [])
    normalized = []

    for idx, item in enumerate(items):
        report_name = item.get("report_nm", "")
        category, importance, signal = classify_disclosure(report_name)
        receipt_no = item.get("rcept_no", "")
        detail_payload = {}
        if receipt_no and importance >= 3:
            detail_payload = extract_disclosure_details(receipt_no, report_name, category)

        normalized.append(
            {
                "doc_type": "disclosure",
                "doc_id": f"disclosure_{receipt_no or idx}",
                "corp_name": item.get("corp_name", ""),
                "report_name": report_name,
                "receipt_no": receipt_no,
                "receipt_date": item.get("rcept_dt", ""),
                "flr_name": item.get("flr_nm", ""),
                "corp_cls": item.get("corp_cls", ""),
                "stock_code": item.get("stock_code", ""),
                "remark": item.get("rm", ""),
                "category": category,
                "importance": importance,
                "signal": signal,
                "event_name": extract_disclosure_event_name(report_name),
                "body_excerpt": detail_payload.get("body_excerpt", ""),
                "detail_metrics": detail_payload.get("detail_metrics", {}),
                "impact_summary": detail_payload.get("impact_summary", ""),
                "viewer_url": build_disclosure_viewer_url(receipt_no) if receipt_no else "",
                "source": "opendart",
            }
        )

    return normalized


def extract_disclosure_event_name(report_name: str) -> str:
    match = re.search(r"\(([^)]+)\)", report_name or "")
    if match:
        return match.group(1).strip()
    return ""


def classify_disclosure(report_name: str) -> tuple[str, int, str]:
    name = (report_name or "").strip()

    rules = [
        (
            ["유상증자", "무상증자", "감자"],
            "capital_change",
            5,
            "주식 수와 자본구조 변화 가능성",
        ),
        (
            ["전환사채", "신주인수권부사채", "교환사채", "회사채"],
            "financing",
            5,
            "희석 또는 자금조달 구조 변화 가능성",
        ),
        (
            ["영업(잠정)실적", "연결재무제표기준영업(잠정)실적", "매출액또는손익구조변경"],
            "earnings_update",
            5,
            "실적 모멘텀 또는 이익체력 변화",
        ),
        (
            ["단일판매ㆍ공급계약", "공급계약"],
            "contract",
            4,
            "매출 가시성 또는 수주 모멘텀",
        ),
        (
            ["기업설명회", "IR"],
            "ir_event",
            3,
            "시장 커뮤니케이션 및 투자자 기대 관리",
        ),
        (
            ["투자판단 관련 주요경영사항"],
            "management_event",
            4,
            "투자판단에 직접 영향이 있는 공시",
        ),
        (
            ["자기주식취득", "자기주식처분", "주식소각결정", "자기주식 소각"],
            "shareholder_return",
            4,
            "주주환원 또는 자본정책 신호",
        ),
        (
            ["배당", "현금ㆍ현물배당결정"],
            "dividend",
            4,
            "주주환원 정책 변화",
        ),
        (
            ["타법인주식및출자증권취득", "영업양수", "합병", "분할"],
            "mna",
            5,
            "사업구조 재편 또는 대형 변화",
        ),
        (
            ["시설투자", "신규시설투자"],
            "capex",
            4,
            "생산능력 또는 성장투자 확대",
        ),
        (
            ["최대주주등소유주식변동신고서", "임원ㆍ주요주주특정증권등소유상황보고서"],
            "ownership_change",
            3,
            "지배구조 또는 내부자 수급 변화",
        ),
        (
            ["조회공시", "소송", "횡령", "배임"],
            "event_risk",
            4,
            "단기 변동성 확대 가능성",
        ),
        (
            # 세부 유형(자기주식·시설투자·배당 등)에 안 걸린 일반 주요사항보고서 catch-all.
            # 구체 키워드 규칙들보다 뒤에 둬서 자사주 등이 전용 파서로 분류되게 한다.
            ["주요사항보고서"],
            "material_event",
            5,
            "중대한 경영 이벤트 가능성(세부 유형 미매칭)",
        ),
        (
            ["사업보고서", "반기보고서", "분기보고서"],
            "periodic_report",
            3,
            "정기 실적 및 사업 현황 점검",
        ),
    ]

    for keywords, category, importance, signal in rules:
        if any(keyword in name for keyword in keywords):
            return category, importance, signal

    return "general_disclosure", 2, "추가 확인이 필요한 일반 공시"


def normalize_price_history(price_rows) -> List[Dict[str, Any]]:
    rows = []

    if hasattr(price_rows, "iterrows"):
        iterator = price_rows.iterrows()
    else:
        iterator = enumerate(price_rows or [])

    for idx, row in iterator:
        rows.append(
            {
                "doc_type": "price",
                "doc_id": f"price_{idx}",
                "date": str(row.get("Date", "")),
                "open": safe_number(row.get("Open")),
                "high": safe_number(row.get("High")),
                "low": safe_number(row.get("Low")),
                "close": safe_number(row.get("Close")),
                "volume": safe_number(row.get("Volume")),
                "source": "yahoo_chart_api",
            }
        )
    return rows


def normalize_ecos_rows(rows: List[Dict[str, Any]], stat_name: str) -> List[Dict[str, Any]]:
    normalized = []

    for idx, row in enumerate(rows):
        normalized.append(
            {
                "doc_type": "macro",
                "doc_id": f"macro_{stat_name}_{idx}",
                "stat_name": stat_name,
                "time": row.get("TIME", ""),
                "value": row.get("DATA_VALUE", ""),
                "item_name": row.get("ITEM_NAME1", ""),
                "source": "ecos",
            }
        )

    return normalized


def safe_number(value: Any):
    try:
        if value is None:
            return None
        return float(value)
    except Exception:
        return value
