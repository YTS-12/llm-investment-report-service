import io
import os
import re
import zipfile
from functools import lru_cache
from xml.etree import ElementTree as ET

import requests
from bs4 import BeautifulSoup

from utils.env import load_project_env
from utils.logger import logger


DOTENV_PATH = load_project_env(override=True)

DART_API_KEY = os.getenv("DART_API_KEY") or os.getenv("OPEN_DART_API_KEY")

# 전용 상세 파서가 있는 공시 카테고리(추출 실패 가시화 판단에 사용)
_DETAIL_PARSER_CATEGORIES = {
    "earnings_update",
    "ir_event",
    "ownership_change",
    "contract",
    "capital_change",
    "financing",
    "shareholder_return",
    "capex",
}


def build_disclosure_viewer_url(receipt_no: str) -> str:
    return f"https://dart.fss.or.kr/dsaf001/main.do?rcpNo={receipt_no}"


@lru_cache(maxsize=128)
def fetch_disclosure_document_xml(receipt_no: str) -> str:
    url = "https://opendart.fss.or.kr/api/document.xml"
    response = requests.get(
        url,
        params={"crtfc_key": DART_API_KEY, "rcept_no": receipt_no},
        timeout=30,
    )
    response.raise_for_status()

    content = response.content
    if content[:2] == b"PK":
        with zipfile.ZipFile(io.BytesIO(content)) as archive:
            first_name = archive.namelist()[0]
            raw = archive.read(first_name)
    else:
        raw = content

    for encoding in ("utf-8", "cp949", "euc-kr"):
        try:
            return raw.decode(encoding)
        except UnicodeDecodeError:
            continue
    return raw.decode("utf-8", errors="ignore")


def extract_document_text(xml_text: str) -> str:
    parser = "html.parser" if "<html" in (xml_text or "").lower() else "xml"
    soup = BeautifulSoup(xml_text, parser)
    for tag in soup.find_all(["style", "script"]):
        tag.decompose()
    text = soup.get_text(" ", strip=True)
    text = " ".join(text.split())
    text = re.sub(r"\.xforms\s+\*.*?(?:보고서|결정)", "", text, flags=re.IGNORECASE)
    text = re.sub(r"\s{2,}", " ", text)
    return text


def extract_document_rows(xml_text: str) -> list[list[str]]:
    parser = "html.parser" if "<html" in (xml_text or "").lower() else "xml"
    soup = BeautifulSoup(xml_text, parser)
    rows = []
    for tr in soup.find_all("tr"):
        cells = [
            " ".join(cell.get_text(" ", strip=True).split())
            for cell in tr.find_all(["td", "th"])
        ]
        cells = [cell for cell in cells if cell]
        if cells:
            rows.append(cells)
    return rows


def _compact_text(text: str) -> str:
    return " ".join((text or "").split())


def _clean_value(value: str) -> str:
    compact = _compact_text(value).strip(" :-")
    if compact in {"", "-", "--", "---", "N/A", "해당없음"}:
        return ""
    return compact


def _normalize_numeric_token(value: str) -> str:
    cleaned = _clean_value(value)
    if not cleaned:
        return ""
    match = re.search(r"[-\d,]+(?:\.\d+)?", cleaned)
    return match.group(0) if match else cleaned


def _find_last_row_values(rows: list[list[str]], label: str) -> list[str]:
    for row in reversed(rows):
        for index, cell in enumerate(row):
            if label in cell:
                return [value for value in row[index + 1 :] if value]
    return []


def _extract_excerpt(text: str, limit: int = 320) -> str:
    compact = _compact_text(text)
    if compact.startswith(".xforms"):
        first_section = re.search(r"\b1\.\s*", compact)
        if first_section:
            compact = compact[first_section.start() :]
    if len(compact) <= limit:
        return compact
    return compact[: limit - 3].rstrip() + "..."


def _extract_metric(text: str, patterns: list[str], value_pattern: str) -> str:
    for pattern in patterns:
        regex = re.compile(
            rf"{pattern}\s*[:：]?\s*({value_pattern})",
            re.IGNORECASE,
        )
        matches = list(regex.finditer(text))
        if matches:
            value = _clean_value(matches[-1].group(1))
            if value:
                return value
    return ""


def _extract_segment(
    text: str,
    start_pattern: str,
    end_patterns: list[str],
    max_len: int = 160,
) -> str:
    start_match = re.search(start_pattern, text, re.IGNORECASE)
    if not start_match:
        return ""

    segment = text[start_match.end() : start_match.end() + max_len]
    end_positions = []
    for pattern in end_patterns:
        match = re.search(pattern, segment, re.IGNORECASE)
        if match:
            end_positions.append(match.start())

    if end_positions:
        segment = segment[: min(end_positions)]

    return _clean_value(segment)


def _extract_date_range(text: str) -> str:
    match = re.search(
        r"(\d{4}[./-]\d{1,2}[./-]\d{1,2})\s*(?:~|∼|-|부터)\s*(\d{4}[./-]\d{1,2}[./-]\d{1,2})",
        text,
    )
    if match:
        return f"{match.group(1)} ~ {match.group(2)}"
    return ""


def _extract_counterparty(text: str) -> str:
    return _extract_metric(
        text,
        [r"계약상대(?:방)?", r"상대방", r"거래상대방"],
        r"[가-힣A-Za-z0-9&.,()\s-]{2,100}",
    )


def _extract_holder_name(text: str) -> str:
    matches = re.findall(r"보고자\s*:\s*([A-Za-z가-힣\s]{2,80})", text)
    if matches:
        return _clean_value(matches[-1])

    named_match = re.search(
        r"성명(?:명칭)?\s*([A-Za-z가-힣0-9().&\-\s]{2,80}?)\s+(?:사업자등록번호|성별|국내외\s*구분|국적)",
        text,
    )
    if named_match:
        return _clean_value(named_match.group(1))

    return _extract_metric(
        text,
        [r"성명(?:명칭)?", r"주요주주"],
        r"[가-힣A-Za-z0-9&.,()\s-]{2,80}",
    )


def _extract_funding_purpose(text: str) -> str:
    return _extract_metric(
        text,
        [r"자금조달\s*목적", r"조달\s*목적", r"사용\s*목적", r"투자목적"],
        r"[가-힣A-Za-z0-9,\s()/·-]{2,120}",
    )


def _extract_ir_datetime(text: str) -> str:
    match = re.search(
        r"일시\s*([0-9]{4}[-./][0-9]{1,2}[-./][0-9]{1,2}(?:\s+[0-9:]{1,5})?)",
        text,
    )
    if match:
        return _clean_value(match.group(1))
    return ""


def _extract_ir_location(text: str) -> str:
    paired_match = re.search(
        r"일시\s+[0-9\-:\s.]+\s+장소\s+(.+?)\s+2\.\s*참가\s*대상자",
        text,
        re.IGNORECASE,
    )
    if paired_match:
        return _clean_value(paired_match.group(1))

    return _extract_segment(
        text,
        r"장소\s*",
        [r"\s+\d+\.\s*", r"\s+참가\s*대상자", r"\s+개최목적", r"\s+개최방법"],
    )


def _extract_ir_purpose(text: str) -> str:
    return _extract_segment(
        text,
        r"개최목적\s*",
        [r"\s+\d+\.\s*", r"\s+개최방법", r"\s+후원기관", r"\s+주요\s*설명회내용"],
    )


def _extract_earnings_metric_block(text: str, label: str) -> dict:
    pattern = re.compile(
        rf"{label}\s+당해실적\s+([-\d.,]+)\s+([-\d.,]+)\s+([-\d.,]+)\s+([-\dA-Za-z가-힣]+)\s+([-\d.,]+)\s+([-\d.,]+)",
        re.IGNORECASE,
    )
    match = pattern.search(text)
    if not match:
        return {}

    current_value = _clean_value(match.group(1))
    yoy_change_rate = _clean_value(match.group(6))
    return {
        "current_value": current_value,
        "previous_value": _clean_value(match.group(2)),
        "qoq_change_rate": f"{_clean_value(match.group(3))}%" if _clean_value(match.group(3)) else "",
        "previous_year_value": _clean_value(match.group(5)),
        "yoy_change_rate": f"{yoy_change_rate}%" if yoy_change_rate else "",
    }


def _parse_earnings_update(text: str) -> dict:
    revenue_block = _extract_earnings_metric_block(text, "매출액")
    operating_income_block = _extract_earnings_metric_block(text, "영업이익")
    net_income_block = _extract_earnings_metric_block(text, "당기순이익")
    return {
        "revenue": revenue_block.get("current_value", ""),
        "revenue_yoy_change_rate": revenue_block.get("yoy_change_rate", ""),
        "operating_income": operating_income_block.get("current_value", ""),
        "operating_income_yoy_change_rate": operating_income_block.get("yoy_change_rate", ""),
        "net_income": net_income_block.get("current_value", ""),
        "net_income_yoy_change_rate": net_income_block.get("yoy_change_rate", ""),
    }


def _parse_ir_event(text: str) -> dict:
    return {
        "event_datetime": _extract_ir_datetime(text),
        "event_location": _extract_ir_location(text),
        "event_purpose": _extract_ir_purpose(text),
    }


def _parse_ownership_change(text: str) -> dict:
    metrics = {
        "holder_name": _extract_holder_name(text),
        "share_count": _extract_metric(
            text,
            [r"보유주식수", r"소유주식수", r"특정증권등의 수"],
            r"[\d,]+(?:\.\d+)?\s*(?:주)?",
        ),
        "holding_ratio": _extract_metric(
            text,
            [r"보유비율", r"소유비율"],
            r"[-+]?[\d,]+(?:\.\d+)?\s*%",
        ),
        "change_ratio": _extract_metric(
            text,
            [r"증감비율", r"변동비율"],
            r"[-+]?[\d,]+(?:\.\d+)?\s*%",
        ),
    }

    current_total = re.search(
        r"이번보고서제출일\s+\d{4}[-./]\d{2}[-./]\d{2}\s+보통주식\s+[\d,]+\s+[\d.]+\s+종류주식\s+[\d,]+\s+[\d.]+\s+증권예탁증권\s+[\d,]+\s+[\d.]+\s+합계\s+([\d,]+)\s+([\d.]+)",
        text,
    )
    if current_total:
        metrics["current_total_shares"] = _clean_value(current_total.group(1))
        metrics["current_total_ratio"] = _clean_value(current_total.group(2)) + "%"

    delta_total = re.search(
        r"증감\s+보통주식\s+[-\d,]+\s+[-\d.]+\s+종류주식\s+[-\d,]+\s+[-\d.]+\s+증권예탁증권\s+[-\d,]+\s+[-\d.]+\s+합계\s+([-\d,]+)\s+([-\d.]+)",
        text,
    )
    if delta_total:
        metrics["change_shares"] = _clean_value(delta_total.group(1))
        metrics["change_ratio"] = _clean_value(delta_total.group(2)) + "%"

    current_common = re.search(
        r"이번보고서제출일\s+\d{4}[-./]\d{2}[-./]\d{2}\s+보통주식\s+([\d,]+)\s+([\d.]+)",
        text,
    )
    if current_common:
        metrics["common_shares"] = _clean_value(current_common.group(1))
        metrics["common_ratio"] = _clean_value(current_common.group(2)) + "%"

    return metrics


def _parse_contract(text: str, rows: list[list[str]] | None = None) -> dict:
    rows = rows or []
    amount_pattern = r"[\d,]+(?:\.\d+)?\s*(?:원|주|억원|천만원|백만원|조원)?"

    contract_name = _extract_segment(
        text,
        r"체결계약명\s*",
        [r"\s+2\.\s*계약내역", r"\s+계약내역", r"\s+계약금액"],
        120,
    )
    if not contract_name:
        contract_name = _clean_value(" ".join(_find_last_row_values(rows, "체결계약명")))

    contract_amount = _extract_metric(text, [r"계약금액\(원\)", r"계약금액"], amount_pattern)
    if not contract_amount:
        contract_amount = _clean_value(" ".join(_find_last_row_values(rows, "계약금액(원)")))

    sales_ratio_match = re.search(
        r"계약내역\s+계약금액\(원\)\s+[\d,]+\s+최근매출액\(원\)\s+[\d,]+\s+매출액대비\(%\)\s+([-\d.]+)",
        text,
    )
    sales_ratio = _clean_value(sales_ratio_match.group(1)) if sales_ratio_match else ""
    if not sales_ratio:
        sales_ratio = _clean_value(" ".join(_find_last_row_values(rows, "매출액대비(%)")))
    if not sales_ratio:
        sales_ratio = _extract_metric(text, [r"매출액대비\(%\)", r"최근매출액대비"], r"[-+]?[\d,]+(?:\.\d+)?")
    counterparty = _extract_segment(
        text,
        r"계약상대\s*",
        [r"\s+-\s*회사와의 관계", r"\s+4\.\s*판매", r"\s+판매ㆍ공급지역"],
        120,
    ) or _extract_counterparty(text)
    if not counterparty:
        counterparty = _clean_value(" ".join(_find_last_row_values(rows, "3. 계약상대")))

    period_match = re.search(
        r"계약기간\s+시작일\s+(\d{4}[-./]\d{2}[-./]\d{2})\s+종료일\s+(\d{4}[-./]\d{2}[-./]\d{2})",
        text,
    )
    contract_period = ""
    if period_match:
        contract_period = f"{period_match.group(1)} ~ {period_match.group(2)}"
    if not contract_period:
        start_values = _find_last_row_values(rows, "5. 계약기간")
        end_values = _find_last_row_values(rows, "종료일")
        if start_values and end_values:
            start_date = _clean_value(start_values[-1])
            end_date = _clean_value(end_values[-1])
            if start_date or end_date:
                contract_period = f"{start_date} ~ {end_date}".strip(" ~")

    supply_region = _extract_segment(
        text,
        r"판매ㆍ공급지역\s*",
        [r"\s+5\.\s*계약기간", r"\s+계약기간", r"\s+6\.\s*주요\s*계약조건"],
        80,
    )
    if not supply_region:
        supply_region = _clean_value(" ".join(_find_last_row_values(rows, "4. 판매ㆍ공급지역")))
    advance_payment = ""
    payment_terms = ""
    advance_values = _find_last_row_values(rows, "계약금ㆍ선급금 유무")
    if advance_values:
        advance_payment = _clean_value(advance_values[-1])
    payment_values = _find_last_row_values(rows, "대금지급 조건 등")
    if payment_values:
        payment_terms = _clean_value(" ".join(payment_values))
    if not advance_payment:
        advance_payment = _extract_metric(
            text,
            [r"계약금ㆍ선급금\s*유무"],
            r"[가-힣A-Za-z-]{1,20}",
        )

    return {
        "contract_name": contract_name,
        "counterparty": counterparty,
        "contract_amount": contract_amount + ("원" if contract_amount and not contract_amount.endswith("원") else ""),
        "sales_ratio": sales_ratio + "%" if sales_ratio and not sales_ratio.endswith("%") else sales_ratio,
        "contract_period": contract_period or _extract_date_range(text),
        "supply_region": supply_region,
        "payment_terms": payment_terms,
        "advance_payment": advance_payment,
    }


def _parse_capital_change(text: str, rows: list[list[str]] | None = None) -> dict:
    rows = rows or []
    issue_price = _extract_metric(
        text,
        [r"신주\s*발행가액\s*보통주식\s*\(원\)", r"신주의\s*발행가액\s*보통주식\s*\(원\)", r"발행가액"],
        r"[\d,]+",
    )
    if not issue_price:
        issue_price = _clean_value(" ".join(_find_last_row_values(rows, "신주 발행가액")))
    shares_to_issue = _extract_metric(
        text,
        [r"신주의\s*종류와\s*수\s*보통주식\s*\(주\)", r"신주수", r"발행예정주식수"],
        r"[\d,]+",
    )
    if not shares_to_issue:
        shares_to_issue = _clean_value(" ".join(_find_last_row_values(rows, "1. 신주의 종류와 수")))
    pre_issue_total_shares = _extract_metric(
        text,
        [r"증자전\s*발행주식총수\s*\(주\)\s*보통주식\s*\(주\)", r"증자전\s*발행주식총수"],
        r"[\d,]+",
    )
    operating_funds = _extract_metric(text, [r"운영자금\s*\(원\)"], r"[\d,]+")
    facility_funds = _extract_metric(text, [r"시설자금\s*\(원\)"], r"[\d,]+")
    debt_repayment_funds = _extract_metric(text, [r"채무상환자금\s*\(원\)"], r"[\d,]+")
    issuance_method = _extract_metric(text, [r"증자방식"], r"[가-힣A-Za-z0-9,\s()·-]{2,60}")
    if not issuance_method:
        issuance_method = _clean_value(" ".join(_find_last_row_values(rows, "5. 증자방식")))
    payment_date = _extract_metric(text, [r"납입일"], r"\d{4}년\s*\d{2}월\s*\d{2}일|\d{4}[-./]\d{2}[-./]\d{2}")
    if not payment_date:
        payment_date = _clean_value(" ".join(_find_last_row_values(rows, "9. 납입일")))

    funding_parts = []
    if operating_funds:
        funding_parts.append(f"운영자금 {operating_funds}원")
    if facility_funds:
        funding_parts.append(f"시설자금 {facility_funds}원")
    if debt_repayment_funds:
        funding_parts.append(f"채무상환자금 {debt_repayment_funds}원")

    return {
        "shares_to_issue": shares_to_issue + ("주" if shares_to_issue and not shares_to_issue.endswith("주") else ""),
        "issue_price": issue_price + ("원" if issue_price and not issue_price.endswith("원") else ""),
        "pre_issue_total_shares": pre_issue_total_shares + ("주" if pre_issue_total_shares and not pre_issue_total_shares.endswith("주") else ""),
        "operating_funds": operating_funds + ("원" if operating_funds and not operating_funds.endswith("원") else ""),
        "facility_funds": facility_funds + ("원" if facility_funds and not facility_funds.endswith("원") else ""),
        "debt_repayment_funds": debt_repayment_funds + ("원" if debt_repayment_funds and not debt_repayment_funds.endswith("원") else ""),
        "funding_purpose": ", ".join(funding_parts),
        "issuance_method": issuance_method,
        "payment_date": payment_date,
    }


def _parse_financing(text: str, report_name: str, rows: list[list[str]] | None = None) -> dict:
    rows = rows or []
    if "전환사채" in report_name:
        bond_total = _extract_metric(
            text,
            [r"사채의\s*권면\(전자등록\)\s*총액\(원\)", r"사채의\s*총액"],
            r"[\d,]+",
        )
        sale_amount = _extract_metric(
            text,
            [r"매도금액\s*금액\(원\)", r"매도금액"],
            r"[\d,]+",
        )
        sale_purpose = _extract_segment(
            text,
            r"매도\s*목적\s*",
            [r"\s+11\.\s*전환에", r"\s+전환에\s*관한\s*사항", r"\s+공정거래위원회"],
            80,
        )
        conversion_price = _extract_metric(
            text,
            [r"전환가액\(원/주\)", r"전환가액"],
            r"[\d,]+",
        )
        convertible_shares = _extract_metric(
            text,
            [r"전환에\s*따라발행할\s*주식\s*종류\s*보통주\s*주식수", r"주식수"],
            r"[\d,]+",
        )
        convertible_ratio = _extract_metric(
            text,
            [r"주식총수\s*대비비율\(%\)", r"주식총수\s*대비\s*비율"],
            r"[-+]?[\d,]+(?:\.\d+)?",
        )
        if not bond_total:
            bond_total = _clean_value(" ".join(_find_last_row_values(rows, "사채의 권면(전자등록) 총액(원)")))
        if not sale_amount:
            sale_amount = _clean_value(" ".join(_find_last_row_values(rows, "매도금액")))
        if not conversion_price:
            conversion_price = _clean_value(" ".join(_find_last_row_values(rows, "전환가액(원/주)")))
        if not convertible_shares:
            convertible_shares = _clean_value(" ".join(_find_last_row_values(rows, "주식수")))
        if not convertible_ratio:
            convertible_ratio = _clean_value(" ".join(_find_last_row_values(rows, "주식총수 대비비율(%)")))

        return {
            "bond_total": bond_total + ("원" if bond_total and not bond_total.endswith("원") else ""),
            "sale_amount": sale_amount + ("원" if sale_amount and not sale_amount.endswith("원") else ""),
            "sale_purpose": sale_purpose,
            "conversion_price": conversion_price + ("원" if conversion_price and not conversion_price.endswith("원") else ""),
            "convertible_shares": convertible_shares + ("주" if convertible_shares and not convertible_shares.endswith("주") else ""),
            "convertible_ratio": convertible_ratio + "%" if convertible_ratio and not convertible_ratio.endswith("%") else convertible_ratio,
        }

    if "신주인수권부사채" in report_name:
        bond_total = _extract_metric(
            text,
            [r"취득한\s*사채의\s*권면\(전자등록\)총액\s*\(통화단위\)", r"사채의\s*권면\(전자등록\)\s*총액"],
            r"[\d,]+",
        )
        acquisition_amount = _extract_metric(
            text,
            [r"사채\s*취득금액\s*\(통화단위\)", r"취득금액"],
            r"[\d,]+",
        )
        exercise_price = _extract_metric(
            text,
            [r"주당\s*신주인수권행사가액\(원\)", r"신주인수권행사가액"],
            r"[\d,]+",
        )
        fund_source = _extract_segment(
            text,
            r"취득자금의\s*원천\s*",
            [r"\s+6\.\s*사채의\s*취득방법", r"\s+사채의\s*취득방법", r"\s+6\.\s*", r"\s+7\.\s*기타"],
            80,
        )
        acquisition_method = _extract_segment(
            text,
            r"사채의\s*취득방법\s*",
            [r"\s+7\.\s*기타", r"\s+기타\s*투자판단", r"\s+관련공시"],
            80,
        )
        acquisition_reason = _extract_segment(
            text,
            r"취득사유\s*:\s*",
            [r"\s+-\s*향후\s*처리", r"\s+향후\s*처리\s*방법", r"\s+5\.\s*취득자금"],
            140,
        )
        remaining_balance = _extract_metric(
            text,
            [r"취득후\s*사채의\s*권면\(전자등록\)잔액\s*\(통화단위\)"],
            r"[\d,]+",
        )
        if not bond_total:
            bond_total = _clean_value(" ".join(_find_last_row_values(rows, "취득한 사채의 권면(전자등록)총액")))
        if not acquisition_amount:
            acquisition_amount = _clean_value(" ".join(_find_last_row_values(rows, "사채 취득금액")))
        if not exercise_price:
            exercise_price = _clean_value(" ".join(_find_last_row_values(rows, "주당 신주인수권행사가액(원)")))
        if not fund_source:
            fund_source = _clean_value(" ".join(_find_last_row_values(rows, "취득자금의 원천")))
        if not acquisition_method:
            acquisition_method = _clean_value(" ".join(_find_last_row_values(rows, "사채의 취득방법")))
        if not remaining_balance:
            remaining_balance = _clean_value(" ".join(_find_last_row_values(rows, "취득후 사채의 권면(전자등록)잔액")))

        return {
            "bond_total": bond_total + ("원" if bond_total and not bond_total.endswith("원") else ""),
            "acquisition_amount": acquisition_amount + ("원" if acquisition_amount and not acquisition_amount.endswith("원") else ""),
            "exercise_price": exercise_price + ("원" if exercise_price and not exercise_price.endswith("원") else ""),
            "fund_source": fund_source,
            "acquisition_method": acquisition_method,
            "acquisition_reason": acquisition_reason,
            "remaining_balance": remaining_balance + ("원" if remaining_balance and not remaining_balance.endswith("원") else ""),
        }

    if "교환사채" in report_name:
        bond_total = _extract_metric(
            text,
            [r"취득한\s*사채의\s*권면총액", r"사채의\s*권면\(전자등록\)\s*총액\(원\)", r"사채의\s*총액"],
            r"[\d,]+",
        )
        issue_amount = _extract_metric(
            text,
            [r"사채\s*취득금액", r"발행금액", r"매도금액", r"취득금액"],
            r"[\d,]+",
        )
        exchange_price = _extract_metric(
            text,
            [r"교환가액\s*\(원\)", r"교환가액\(원/주\)", r"교환가액"],
            r"[\d,]+",
        )
        exchange_target = _extract_metric(
            text,
            [r"교환대상\s*주식", r"교환대상"],
            r"[가-힣A-Za-z0-9,\s()·-]{2,80}",
        )
        exchangeable_shares = _extract_metric(
            text,
            [r"교환대상\s*주식수", r"주식수"],
            r"[\d,]+",
        )
        purpose = _extract_segment(
            text,
            r"(?:발행|매도|취득)\s*목적\s*",
            [r"\s+\d+\.\s*", r"\s+교환에\s*관한\s*사항", r"\s+기타\s*투자판단"],
            100,
        )
        acquisition_reason = _extract_segment(
            text,
            r"만기전\s*취득사유\s*및\s*향후\s*처리방법\s*",
            [r"\s+5\.\s*취득자금의\s*원천", r"\s+취득자금의\s*원천", r"\s+6\.\s*사채의\s*취득방법"],
            120,
        )
        fund_source = _extract_segment(
            text,
            r"취득자금의\s*원천\s*",
            [r"\s+6\.\s*사채의\s*취득방법", r"\s+사채의\s*취득방법", r"\s+7\.\s*기타"],
            80,
        )
        acquisition_method = _extract_segment(
            text,
            r"사채의\s*취득방법\s*",
            [r"\s+7\.\s*기타", r"\s+기타\s*투자판단", r"\s+관련공시"],
            80,
        )
        remaining_balance = _extract_metric(
            text,
            [r"취득후\s*사채의\s*권면잔액", r"취득후\s*사채의\s*권면\(전자등록\)잔액"],
            r"[\d,]+",
        )
        if not bond_total:
            bond_total = _normalize_numeric_token(" ".join(_find_last_row_values(rows, "취득한 사채의 권면총액")))
        if not issue_amount:
            issue_amount = _normalize_numeric_token(" ".join(_find_last_row_values(rows, "2. 사채 취득금액 (통화단위)")))
        if not exchange_price:
            exchange_price = _clean_value(" ".join(_find_last_row_values(rows, "교환가액 (원)")))
        if not exchange_target:
            exchange_target = _clean_value(" ".join(_find_last_row_values(rows, "교환대상 주식")))
        if not exchangeable_shares:
            exchangeable_shares = _clean_value(" ".join(_find_last_row_values(rows, "교환대상 주식수")))
        if not acquisition_reason:
            acquisition_reason = _clean_value(" ".join(_find_last_row_values(rows, "4. 만기전 취득사유 및 향후 처리방법")))
        if not fund_source:
            fund_source = _clean_value(" ".join(_find_last_row_values(rows, "5. 취득자금의 원천")))
        if not acquisition_method:
            acquisition_method = _clean_value(" ".join(_find_last_row_values(rows, "6. 사채의 취득방법")))
        if not remaining_balance:
            remaining_balance = _normalize_numeric_token(" ".join(_find_last_row_values(rows, "3. 취득후 사채의 권면잔액 (통화단위)")))

        return {
            "bond_total": bond_total + ("원" if bond_total and not bond_total.endswith("원") else ""),
            "issue_amount": issue_amount + ("원" if issue_amount and not issue_amount.endswith("원") else ""),
            "exchange_price": exchange_price + ("원" if exchange_price and not exchange_price.endswith("원") else ""),
            "exchange_target": exchange_target,
            "exchangeable_shares": exchangeable_shares + ("주" if exchangeable_shares and not exchangeable_shares.endswith("주") else ""),
            "exchange_purpose": purpose,
            "acquisition_reason": acquisition_reason,
            "fund_source": fund_source,
            "acquisition_method": acquisition_method,
            "remaining_balance": remaining_balance + ("원" if remaining_balance and not remaining_balance.endswith("원") else ""),
        }

    return _parse_capital_change(text, rows)


def _parse_shareholder_return(text: str) -> dict:
    amount_pattern = r"[\d,]+(?:\.\d+)?\s*(?:원|주|억원|천만원|백만원|조원)"
    return {
        "share_count": _extract_metric(
            text,
            [r"취득예정주식수", r"처분예정주식수", r"취득주식수"],
            amount_pattern,
        ),
        "transaction_amount": _extract_metric(
            text,
            [r"취득예정금액", r"처분예정금액", r"취득금액"],
            amount_pattern,
        ),
        "period": _extract_date_range(text),
    }


def _parse_share_cancellation(text: str) -> dict:
    common_match = re.search(
        r"소각할\s*주식의\s*종류와\s*수\s*보통주식\s*\(주\)\s*([\d,]+)",
        text,
    )
    preferred_match = re.search(
        r"소각할\s*주식의\s*종류와\s*수.*?종류주식\s*\(주\)\s*([\d,]+)",
        text,
        re.DOTALL,
    )
    amount_match = re.search(r"소각예정금액\(원\)\s*([\d,]+)", text)
    purpose_match = re.search(
        r"중요사항\s*-\s*금번\s*주식\s*소각\s*결정은\s*(.+?)\s*-\s*배당가능이익",
        text,
    )

    common_shares = _clean_value(common_match.group(1)) if common_match else ""
    preferred_shares = _clean_value(preferred_match.group(1)) if preferred_match else ""
    cancellation_amount = (
        _clean_value(amount_match.group(1)) + "원" if amount_match else ""
    )
    purpose = _clean_value(purpose_match.group(1)) if purpose_match else ""

    metrics = {
        "common_shares_to_cancel": common_shares,
        "preferred_shares_to_cancel": preferred_shares,
        "cancellation_amount": cancellation_amount,
        "cancellation_purpose": purpose,
    }

    if common_shares or preferred_shares:
        total = 0
        for value in (common_shares, preferred_shares):
            if value:
                total += int(value.replace(",", ""))
        if total:
            metrics["share_count"] = f"{total:,}주"
    return metrics


def _parse_capex(text: str) -> dict:
    amount_pattern = r"[\d,]+(?:\.\d+)?\s*(?:원|주|억원|천만원|백만원|조원)"
    return {
        "investment_amount": _extract_metric(
            text,
            [r"투자금액", r"투자예정금액"],
            amount_pattern,
        ),
        "equity_ratio": _extract_metric(
            text,
            [r"자기자본대비", r"자기자본\s*대비"],
            r"[-+]?[\d,]+(?:\.\d+)?\s*%",
        ),
        "purpose": _extract_funding_purpose(text),
    }


def _extract_detail_metrics(
    text: str,
    category: str,
    report_name: str = "",
    rows: list[list[str]] | None = None,
) -> dict:
    parsers = {
        "earnings_update": _parse_earnings_update,
        "ir_event": _parse_ir_event,
        "ownership_change": _parse_ownership_change,
        "contract": lambda value: _parse_contract(value, rows),
        "capital_change": lambda value: _parse_capital_change(value, rows),
        "financing": lambda value: _parse_financing(value, report_name, rows),
        "shareholder_return": _parse_share_cancellation if "소각" in report_name else _parse_shareholder_return,
        "capex": _parse_capex,
    }
    parser = parsers.get(category)
    if not parser:
        return {}

    metrics = parser(text)
    return {key: value for key, value in metrics.items() if _clean_value(str(value))}


def build_disclosure_impact_summary(report_name: str, category: str, metrics: dict) -> str:
    significant_keys = {
        "earnings_update": ["revenue", "revenue_yoy_change_rate", "operating_income", "operating_income_yoy_change_rate"],
        "contract": ["contract_name", "contract_amount", "sales_ratio", "counterparty", "contract_period", "supply_region"],
        "capital_change": ["shares_to_issue", "issue_price", "funding_purpose", "issuance_method"],
        "financing": [
            "sale_amount",
            "acquisition_amount",
            "issue_amount",
            "conversion_price",
            "exercise_price",
            "exchange_price",
            "convertible_shares",
            "exchangeable_shares",
            "sale_purpose",
            "acquisition_reason",
            "exchange_purpose",
        ],
        "shareholder_return": ["share_count", "cancellation_amount", "transaction_amount"],
        "capex": ["investment_amount", "equity_ratio"],
        "ownership_change": ["holder_name", "current_total_shares", "current_total_ratio", "change_shares", "change_ratio"],
        "ir_event": ["event_datetime", "event_location", "event_purpose"],
    }
    keys = significant_keys.get(category, [])
    parts = [metrics[key] for key in keys if metrics.get(key)]
    if not parts:
        return ""
    return f"{report_name} 핵심 포인트: " + ", ".join(parts[:3])


def extract_disclosure_details(receipt_no: str, report_name: str, category: str) -> dict:
    if not receipt_no:
        return {"body_excerpt": "", "detail_metrics": {}, "impact_summary": ""}

    try:
        xml_text = fetch_disclosure_document_xml(receipt_no)
        document_text = extract_document_text(xml_text)
        document_rows = extract_document_rows(xml_text)
    except Exception as exc:
        # 과거에는 조용히 빈 dict를 반환해 '왜 비었는지'를 알 수 없었다.
        # 원문 다운로드/파싱 실패를 명시적으로 기록한다.
        logger.warning(
            "Disclosure document fetch/parse failed | receipt_no=%s | category=%s | error=%s",
            receipt_no,
            category,
            repr(exc),
        )
        return {"body_excerpt": "", "detail_metrics": {}, "impact_summary": ""}

    metrics = _extract_detail_metrics(document_text, category, report_name, document_rows)
    if not metrics and category in _DETAIL_PARSER_CATEGORIES:
        # 전용 파서가 있는 카테고리인데 수치를 하나도 못 뽑았다 = 공시 양식 변경 신호일 수 있음.
        logger.warning(
            "Disclosure detail extraction returned no metrics | receipt_no=%s | category=%s | report_name=%s",
            receipt_no,
            category,
            report_name,
        )
    return {
        "body_excerpt": _extract_excerpt(document_text),
        "detail_metrics": metrics,
        "impact_summary": build_disclosure_impact_summary(report_name, category, metrics),
    }


def _normalize_name(name: str) -> str:
    return (name or "").replace(" ", "").strip().lower()


@lru_cache(maxsize=1)
def load_corp_codes() -> list[dict]:
    url = "https://opendart.fss.or.kr/api/corpCode.xml"
    response = requests.get(url, params={"crtfc_key": DART_API_KEY}, timeout=30)
    response.raise_for_status()

    with zipfile.ZipFile(io.BytesIO(response.content)) as archive:
        xml_name = archive.namelist()[0]
        xml_bytes = archive.read(xml_name)

    root = ET.fromstring(xml_bytes)
    rows = []
    for item in root.findall("list"):
        rows.append(
            {
                "corp_code": (item.findtext("corp_code") or "").strip(),
                "corp_name": (item.findtext("corp_name") or "").strip(),
                "stock_code": (item.findtext("stock_code") or "").strip(),
                "modify_date": (item.findtext("modify_date") or "").strip(),
            }
        )
    return rows


def find_corp_code(company_name: str) -> str:
    normalized = _normalize_name(company_name)
    if not normalized:
        return ""

    rows = load_corp_codes()
    for row in rows:
        if _normalize_name(row["corp_name"]) == normalized:
            return row["corp_code"]

    for row in rows:
        corp_name = _normalize_name(row["corp_name"])
        if normalized in corp_name or corp_name in normalized:
            return row["corp_code"]

    return ""


def find_stock_code(company_name: str) -> str:
    """회사명을 DART corp 테이블의 상장 종목코드(6자리)로 변환한다.

    상장사만(stock_code 보유)을 대상으로 '정확 일치'를 우선한다. 못 찾으면 "".
    하드코딩 티커맵 없이 KRX 상장 종목을 폭넓게 자동 해석하기 위한 보조기다.
    (정밀도 우선 — 부분일치는 잘못된 종목 매핑 위험이 있어 사용하지 않는다.)
    """
    normalized = _normalize_name(company_name)
    if not normalized:
        return ""

    for row in load_corp_codes():
        code = (row.get("stock_code") or "").strip()
        if code and _normalize_name(row["corp_name"]) == normalized:
            return code
    return ""


def search_disclosures(
    corp_code: str,
    bgn_de: str,
    end_de: str,
    page_count: int = 10,
    pblntf_ty: str | None = None,
):
    """OpenDART 공시검색(list.json).

    pblntf_ty(공시유형)로 유형별 필터가 가능하다:
      A 정기공시(사업/반기/분기보고서) · B 주요사항보고 · C 발행공시 · D 지분공시
      · E 기타 · F 외부감사 · G 펀드 · H 자산유동화
      · I 거래소공시(수시·공정공시·잠정실적·배당) · J 공정위공시
    page_count는 최대 100.
    """
    url = "https://opendart.fss.or.kr/api/list.json"
    params = {
        "crtfc_key": DART_API_KEY,
        "corp_code": corp_code,
        "bgn_de": bgn_de,
        "end_de": end_de,
        "page_no": 1,
        "page_count": page_count,
    }
    if pblntf_ty:
        params["pblntf_ty"] = pblntf_ty
    res = requests.get(url, params=params, timeout=20)
    res.raise_for_status()
    return res.json()
