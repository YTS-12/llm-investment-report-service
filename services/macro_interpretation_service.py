import json
import re
from pathlib import Path
from typing import Any, Dict


# 업종 민감도 점수는 코드에 박지 않고 외부 JSON에서 로드한다(근거·출처 주석 포함).
_CONFIG_PATH = Path(__file__).resolve().parents[1] / "config" / "sector_sensitivity.json"
_NEUTRAL = {"rate": 0, "fx": 0, "growth": 0, "inflation": 0}


def _load_sector_config() -> tuple[dict, dict]:
    try:
        with open(_CONFIG_PATH, "r", encoding="utf-8") as f:
            data = json.load(f)
        return data.get("sectors", {}), data.get("default", dict(_NEUTRAL))
    except Exception:
        # 설정 파일이 없거나 깨져도 서비스가 죽지 않도록 중립값으로 폴백한다.
        return {}, dict(_NEUTRAL)


SECTOR_SENSITIVITY, SECTOR_DEFAULT = _load_sector_config()


def _norm_sector(name: str) -> str:
    return re.sub(r"[\s/]", "", name or "")


def get_sector_sensitivity(sector: str) -> dict:
    """업종명을 민감도 dict로 해석한다(정확 일치 → 부분 일치 → 기본 중립)."""
    key = (sector or "").strip()
    if key in SECTOR_SENSITIVITY:
        return SECTOR_SENSITIVITY[key]

    norm = _norm_sector(key)
    if norm:
        for name, sens in SECTOR_SENSITIVITY.items():
            normalized_name = _norm_sector(name)
            if normalized_name and (normalized_name in norm or norm in normalized_name):
                return sens
    return SECTOR_DEFAULT


def classify_rate_regime(rate_view: str) -> str:
    if "인하" in rate_view:
        return "rate_cut_expectation"
    if "상승" in rate_view or "인상" in rate_view:
        return "rate_hike_pressure"
    return "rate_stable"


def classify_fx_regime(fx_view: str) -> str:
    if "환율 상승" in fx_view or "원화 약세" in fx_view:
        return "weak_krw"
    if "환율 하락" in fx_view or "원화 강세" in fx_view:
        return "strong_krw"
    return "fx_stable"


def classify_growth_regime(growth_view: str) -> str:
    if "회복" in growth_view or "개선" in growth_view:
        return "growth_recovery"
    if "둔화" in growth_view or "악화" in growth_view:
        return "growth_slowdown"
    return "growth_neutral"


def classify_inflation_regime(inflation_view: str) -> str:
    view = inflation_view or ""
    if "확대" in view or "높아지" in view or "상승 압력" in view:
        return "inflation_high"
    if "둔화" in view or "약해" in view:
        return "inflation_low"
    return "inflation_stable"


def _sensitivity_value(sensitivity: dict, factor: str) -> int:
    try:
        return int(sensitivity.get(factor, 0) or 0)
    except Exception:
        return 0


def score_macro_for_sector(
    sector: str,
    rate_regime: str,
    fx_regime: str,
    growth_regime: str,
    inflation_regime: str = "inflation_stable",
) -> int:
    sensitivity = get_sector_sensitivity(sector)
    score = 0

    # 금리: 인상 = 민감도 부호 그대로, 인하 = 반대
    rate = _sensitivity_value(sensitivity, "rate")
    if rate_regime == "rate_cut_expectation":
        score += rate * -1
    elif rate_regime == "rate_hike_pressure":
        score += rate * 1

    # 환율: 원화 약세 = 민감도 부호 그대로, 강세 = 반대
    fx = _sensitivity_value(sensitivity, "fx")
    if fx_regime == "weak_krw":
        score += fx * 1
    elif fx_regime == "strong_krw":
        score += fx * -1

    # 경기: 회복 = 부호 그대로, 둔화 = 반대
    growth = _sensitivity_value(sensitivity, "growth")
    if growth_regime == "growth_recovery":
        score += growth * 1
    elif growth_regime == "growth_slowdown":
        score += growth * -1

    # 물가: 인플레 상승 = 부호 그대로, 둔화 = 반대 (2차 요인, 민감도 ±1 제한)
    inflation = _sensitivity_value(sensitivity, "inflation")
    if inflation_regime == "inflation_high":
        score += inflation * 1
    elif inflation_regime == "inflation_low":
        score += inflation * -1

    return score


def interpret_macro(
    sector: str,
    rate_view: str,
    fx_view: str,
    growth_view: str,
    inflation_view: str = "",
) -> Dict[str, Any]:
    rate_regime = classify_rate_regime(rate_view)
    fx_regime = classify_fx_regime(fx_view)
    growth_regime = classify_growth_regime(growth_view)
    inflation_regime = classify_inflation_regime(inflation_view)

    score = score_macro_for_sector(
        sector=sector,
        rate_regime=rate_regime,
        fx_regime=fx_regime,
        growth_regime=growth_regime,
        inflation_regime=inflation_regime,
    )

    if score >= 3:
        impact = "긍정"
    elif score <= -3:
        impact = "부정"
    else:
        impact = "중립"

    summary = (
        f"현재 거시 레짐은 금리={rate_regime}, 환율={fx_regime}, 경기={growth_regime}, "
        f"물가={inflation_regime}로 해석된다. "
        f"{sector} 업종에는 전반적으로 {impact}적인 환경으로 판단된다. "
        f"(macro_score={score})"
    )

    return {
        "sector": sector,
        "rate_regime": rate_regime,
        "fx_regime": fx_regime,
        "growth_regime": growth_regime,
        "inflation_regime": inflation_regime,
        "macro_score": score,
        "macro_impact": impact,
        "macro_summary": summary,
    }
