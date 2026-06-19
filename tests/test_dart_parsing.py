"""DART 분류·파싱·요약 로직 단위테스트 (외부 API 불필요)."""
from data_collectors.normalize import classify_disclosure, extract_disclosure_event_name
from data_collectors.dart_api import (
    _parse_earnings_update,
    build_disclosure_impact_summary,
    _clean_value,
)


class TestClassifyDisclosure:
    def test_earnings_importance_5(self):
        category, importance, _ = classify_disclosure("영업(잠정)실적 (공정공시)")
        assert category == "earnings_update"
        assert importance == 5

    def test_capital_change(self):
        category, importance, _ = classify_disclosure("유상증자결정")
        assert (category, importance) == ("capital_change", 5)

    def test_convertible_bond_financing(self):
        category, importance, _ = classify_disclosure("전환사채권발행결정")
        assert (category, importance) == ("financing", 5)

    def test_supply_contract(self):
        category, importance, _ = classify_disclosure("단일판매ㆍ공급계약체결")
        assert (category, importance) == ("contract", 4)

    def test_unknown_general(self):
        category, importance, _ = classify_disclosure("기타 자율공시")
        assert (category, importance) == ("general_disclosure", 2)


class TestEventName:
    def test_first_parenthesis(self):
        assert extract_disclosure_event_name("영업(잠정)실적") == "잠정"

    def test_no_parenthesis(self):
        assert extract_disclosure_event_name("사업보고서") == ""


class TestCleanValue:
    def test_blank_markers(self):
        assert _clean_value("-") == ""
        assert _clean_value("해당없음") == ""

    def test_keeps_number(self):
        assert _clean_value("  1,000  ") == "1,000"


class TestParseEarnings:
    SAMPLE = (
        "매출액 당해실적 12,345 11,000 12.2 전년동기 9,500 30.0 "
        "영업이익 당해실적 2,000 1,800 11.1 전년동기 1,500 33.3 "
        "당기순이익 당해실적 1,500 1,300 15.3 전년동기 1,100 36.3"
    )

    def test_revenue(self):
        r = _parse_earnings_update(self.SAMPLE)
        assert r["revenue"] == "12,345"
        assert r["revenue_yoy_change_rate"] == "30.0%"

    def test_operating_income(self):
        r = _parse_earnings_update(self.SAMPLE)
        assert r["operating_income"] == "2,000"
        assert r["operating_income_yoy_change_rate"] == "33.3%"

    def test_net_income(self):
        r = _parse_earnings_update(self.SAMPLE)
        assert r["net_income"] == "1,500"


class TestImpactSummary:
    def test_top3_only(self):
        metrics = {
            "revenue": "12,345",
            "revenue_yoy_change_rate": "30.0%",
            "operating_income": "2,000",
            "operating_income_yoy_change_rate": "33.3%",
        }
        s = build_disclosure_impact_summary("영업(잠정)실적", "earnings_update", metrics)
        assert s.startswith("영업(잠정)실적 핵심 포인트:")
        assert "12,345" in s and "30.0%" in s and "2,000" in s
        assert "33.3%" not in s  # 4번째 필드는 상위 3개 절단으로 빠진다

    def test_empty_metrics(self):
        assert build_disclosure_impact_summary("x", "earnings_update", {}) == ""


class TestMaterialEventOrdering:
    def test_treasury_stock_goes_to_shareholder_return(self):
        # 주요사항보고서(자기주식취득결정) → material_event가 아니라 shareholder_return(전용 파서)
        category, _, _ = classify_disclosure("주요사항보고서(자기주식취득결정)")
        assert category == "shareholder_return"

    def test_capital_raise_still_capital_change(self):
        category, _, _ = classify_disclosure("주요사항보고서(유상증자결정)")
        assert category == "capital_change"

    def test_generic_material_event_fallback(self):
        # 세부 유형 없는 주요사항보고서는 여전히 material_event(catch-all)
        category, importance, _ = classify_disclosure("주요사항보고서(해산결정)")
        assert category == "material_event"
        assert importance == 5
