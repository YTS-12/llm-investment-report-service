import os
from datetime import datetime
from typing import Any, Dict

import requests

from utils.env import load_project_env


DOTENV_PATH = load_project_env(override=True)

ECOS_API_KEY = os.getenv("ECOS_API_KEY")
if not ECOS_API_KEY:
    raise ValueError(f"ECOS_API_KEY가 없습니다. .env 파일을 확인하세요: {DOTENV_PATH}")


def get_ecos_raw(
    stat_code: str,
    item_code1: str,
    start: str,
    end: str,
    cycle: str = "M",
    lang: str = "kr",
    start_count: int = 1,
    end_count: int = 100,
    item_code2: str | None = None,
    item_code3: str | None = None,
    item_code4: str | None = None,
) -> Dict[str, Any]:
    """
    ECOS Open API raw 응답 반환
    stat_code: 통계표코드
    item_code1: 항목코드
    start/end: YYYYMM 또는 YYYYMMDD 형식
    cycle: D / M / Q / A
    """
    parts = [
        "https://ecos.bok.or.kr/api/StatisticSearch",
        ECOS_API_KEY,
        "json",
        lang,
        str(start_count),
        str(end_count),
        stat_code,
        cycle,
        start,
        end,
        item_code1,
    ]
    for extra_code in [item_code2, item_code3, item_code4]:
        if extra_code:
            parts.append(extra_code)

    url = "/".join(parts)

    response = requests.get(url, timeout=20)
    response.raise_for_status()
    return response.json()


def parse_ecos_rows(raw_json: Dict[str, Any]) -> list[dict]:
    """ECOS 응답에서 실제 row만 추출"""
    if "StatisticSearch" not in raw_json:
        return []

    rows = raw_json["StatisticSearch"].get("row", [])
    if not isinstance(rows, list):
        return []

    return rows


MACRO_SERIES_CONFIG = {
    "policy_rate": {
        "label": "한국은행 기준금리",
        "stat_code": "722Y001",
        "item_code1": "0101000",
        "cycle": "M",
        "months": 12,
    },
    "usdkrw": {
        "label": "원/달러 환율(종가 15:30)",
        "stat_code": "731Y006",
        "item_code1": "0000003",
        "cycle": "M",
        "months": 12,
    },
    "leading_cycle": {
        "label": "선행지수순환변동치",
        "stat_code": "901Y067",
        "item_code1": "I16E",
        "cycle": "M",
        "months": 12,
    },
    "coincident_cycle": {
        "label": "동행지수순환변동치",
        "stat_code": "901Y067",
        "item_code1": "I16D",
        "cycle": "M",
        "months": 12,
    },
    "export_index": {
        "label": "수출금액지수",
        "stat_code": "403Y001",
        "item_code1": "*AA",
        "cycle": "M",
        "months": 12,
    },
    "cpi": {
        "label": "소비자물가지수",
        "stat_code": "901Y009",
        "item_code1": "0",
        "cycle": "M",
        "months": 12,
    },
}


def _month_range(months: int = 12) -> tuple[str, str]:
    today = datetime.today()
    end = today.strftime("%Y%m")

    year = today.year
    month = today.month - (months - 1)
    while month <= 0:
        month += 12
        year -= 1

    start = f"{year}{month:02d}"
    return start, end


def _safe_float(value: Any) -> float | None:
    if value in (None, ""):
        return None
    try:
        return float(str(value).replace(",", ""))
    except Exception:
        return None


def build_series_snapshot(rows: list[dict], label: str) -> dict[str, Any]:
    valid_rows = []
    for row in rows:
        numeric_value = _safe_float(row.get("DATA_VALUE"))
        if numeric_value is None:
            continue
        valid_rows.append(
            {
                "time": row.get("TIME", ""),
                "value": numeric_value,
                "item_name": row.get("ITEM_NAME1") or label,
            }
        )

    valid_rows.sort(key=lambda row: row["time"])
    if not valid_rows:
        return {
            "label": label,
            "latest_time": "",
            "latest_value": None,
            "previous_value": None,
            "delta": None,
            "pct_change": None,
            "trend": "unknown",
            "series": [],
        }

    latest = valid_rows[-1]
    previous = valid_rows[-2] if len(valid_rows) >= 2 else None
    baseline = valid_rows[-4] if len(valid_rows) >= 4 else valid_rows[0]

    delta = None
    pct_change = None
    if baseline and baseline["value"] is not None:
        delta = latest["value"] - baseline["value"]
        if baseline["value"] != 0:
            pct_change = (delta / baseline["value"]) * 100

    if delta is None:
        trend = "stable"
    elif abs(delta) < 0.05:
        trend = "stable"
    elif delta > 0:
        trend = "up"
    else:
        trend = "down"

    return {
        "label": label,
        "latest_time": latest["time"],
        "latest_value": latest["value"],
        "previous_value": previous["value"] if previous else None,
        "delta": delta,
        "pct_change": pct_change,
        "trend": trend,
        "series": valid_rows,
    }


def _format_delta(snapshot: dict[str, Any], suffix: str = "") -> str:
    delta = snapshot.get("delta")
    if delta is None:
        return "추세 판단 불가"

    if abs(delta) < 0.05:
        return "최근 대체로 안정"

    direction = "상승" if delta > 0 else "하락"
    return f"최근 {direction} ({delta:+.2f}{suffix})"


def build_rate_view(rate_snapshot: dict[str, Any]) -> str:
    latest = rate_snapshot.get("latest_value")
    time = rate_snapshot.get("latest_time", "")
    trend_text = _format_delta(rate_snapshot, "%p")

    if latest is None:
        return "금리 데이터가 부족해 기준금리 방향성을 판단하기 어렵다."

    delta = rate_snapshot.get("delta") or 0.0
    if delta <= -0.1:
        tone = "기준금리 인하 흐름이 반영되며 완화적 기조가 이어지고 있다."
    elif delta >= 0.1:
        tone = "기준금리 상승 흐름이 이어지며 긴축 압력이 남아 있다."
    else:
        tone = "기준금리는 최근 큰 변동 없이 안정적으로 유지되고 있다."

    return f"{time} 기준 한국은행 기준금리는 {latest:.2f}%이며, {trend_text}. {tone}"


def build_fx_view(fx_snapshot: dict[str, Any]) -> str:
    latest = fx_snapshot.get("latest_value")
    time = fx_snapshot.get("latest_time", "")
    trend_text = _format_delta(fx_snapshot, "원")

    if latest is None:
        return "환율 데이터가 부족해 원화 방향성을 판단하기 어렵다."

    pct_change = fx_snapshot.get("pct_change") or 0.0
    if pct_change >= 1.0:
        tone = "원/달러 환율 상승과 원화 약세 흐름이 이어지고 있다."
    elif pct_change <= -1.0:
        tone = "원/달러 환율 하락과 원화 강세 흐름이 확인된다."
    else:
        tone = "환율은 최근 좁은 범위에서 움직이며 대체로 안정적이다."

    return f"{time} 기준 원/달러 환율은 {latest:.1f}원이며, {trend_text}. {tone}"


def build_growth_view(
    leading_snapshot: dict[str, Any],
    coincident_snapshot: dict[str, Any],
    export_snapshot: dict[str, Any],
) -> str:
    signals: list[str] = []
    positive = 0
    negative = 0

    leading_value = leading_snapshot.get("latest_value")
    if leading_value is not None:
        if leading_value >= 100 and leading_snapshot.get("trend") != "down":
            positive += 1
        elif leading_value < 100 and leading_snapshot.get("trend") == "down":
            negative += 1
        signals.append(
            f"선행지수순환변동치 {leading_value:.1f} ({_format_delta(leading_snapshot)})"
        )

    coincident_value = coincident_snapshot.get("latest_value")
    if coincident_value is not None:
        if coincident_value >= 100 and coincident_snapshot.get("trend") != "down":
            positive += 1
        elif coincident_value < 100 and coincident_snapshot.get("trend") == "down":
            negative += 1
        signals.append(
            f"동행지수순환변동치 {coincident_value:.1f} ({_format_delta(coincident_snapshot)})"
        )

    export_change = export_snapshot.get("pct_change")
    export_value = export_snapshot.get("latest_value")
    if export_value is not None:
        if export_change is not None and export_change >= 1.0:
            positive += 1
        elif export_change is not None and export_change <= -1.0:
            negative += 1
        export_desc = (
            f"최근 3개월 기준 {export_change:+.1f}%"
            if export_change is not None
            else "추세 판단 불가"
        )
        signals.append(f"수출금액지수 {export_value:.1f} ({export_desc})")

    if positive >= 2 and positive >= negative:
        conclusion = "경기 회복 또는 개선 흐름이 이어지고 있다."
    elif negative >= 2 and negative > positive:
        conclusion = "경기 둔화 또는 악화 신호가 상대적으로 우세하다."
    else:
        conclusion = "경기 방향성은 뚜렷하지 않으며 혼조 또는 중립 흐름에 가깝다."

    if not signals:
        return "경기 데이터가 부족해 경기 흐름을 판단하기 어렵다."

    return f"{'; '.join(signals)}. {conclusion}"


def build_inflation_view(cpi_snapshot: dict[str, Any]) -> str:
    latest = cpi_snapshot.get("latest_value")
    time = cpi_snapshot.get("latest_time", "")

    if latest is None:
        return "물가 데이터가 부족해 인플레이션 방향성을 판단하기 어렵다."

    pct_change = cpi_snapshot.get("pct_change") or 0.0  # 최근 3개월 CPI 변화율(%)
    if pct_change >= 1.0:
        tone = "최근 소비자물가 상승 압력이 확대되며 인플레이션이 높아지는 흐름이다."
    elif pct_change <= 0.2:
        tone = "소비자물가 상승세가 둔화되며 인플레이션 압력이 약해지고 있다."
    else:
        tone = "소비자물가는 최근 완만한 흐름으로 인플레이션은 대체로 안정적이다."

    return f"{time} 기준 소비자물가지수는 {latest:.2f}이며, 최근 3개월 {pct_change:+.2f}% 변동. {tone}"


def collect_macro_series_context() -> dict[str, Any]:
    series_payloads: dict[str, list[dict]] = {}
    snapshots: dict[str, dict[str, Any]] = {}

    for key, config in MACRO_SERIES_CONFIG.items():
        start, end = _month_range(config["months"])
        try:
            raw = get_ecos_raw(
                stat_code=config["stat_code"],
                item_code1=config["item_code1"],
                start=start,
                end=end,
                cycle=config["cycle"],
            )
            rows = parse_ecos_rows(raw)
        except Exception:
            # 한 계열이 실패해도 나머지 거시 지표 수집은 계속되게 한다.
            rows = []
        series_payloads[key] = rows
        snapshots[key] = build_series_snapshot(rows, config["label"])

    rate_view = build_rate_view(snapshots["policy_rate"])
    fx_view = build_fx_view(snapshots["usdkrw"])
    growth_view = build_growth_view(
        snapshots["leading_cycle"],
        snapshots["coincident_cycle"],
        snapshots["export_index"],
    )
    inflation_view = build_inflation_view(snapshots["cpi"])

    summary_lines = []
    for key in [
        "policy_rate",
        "usdkrw",
        "cpi",
        "leading_cycle",
        "coincident_cycle",
        "export_index",
    ]:
        snapshot = snapshots[key]
        latest = snapshot.get("latest_value")
        if latest is None:
            continue
        summary_lines.append(
            f"- {snapshot['label']}: {latest:.2f} ({snapshot.get('latest_time')}), {_format_delta(snapshot)}"
        )

    return {
        "series_rows": series_payloads,
        "snapshots": snapshots,
        "rate_view": rate_view,
        "fx_view": fx_view,
        "growth_view": growth_view,
        "inflation_view": inflation_view,
        "macro_summary": "\n".join(summary_lines),
    }
