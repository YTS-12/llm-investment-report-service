"""네이버 기업실적분석 표 파싱(최신값 추출) 단위테스트."""
from data_collectors.naver_finance_scraper import _latest_actual, _build_financials


_PERIODS = [
    {"period": "2024.12", "kind": "annual", "estimate": False},
    {"period": "2025.12", "kind": "annual", "estimate": False},
    {"period": "2026.12", "kind": "annual", "estimate": True},   # 추정치
    {"period": "2025.12", "kind": "quarter", "estimate": False},
    {"period": "2026.03", "kind": "quarter", "estimate": False},
    {"period": "2026.06", "kind": "quarter", "estimate": True},  # 추정치
]


class TestLatestActual:
    def test_annual_skips_estimate(self):
        vals = ["27.93", "29.94", "", "29.94", "30.15", ""]
        # 2026.12은 추정치라 제외 → 2025.12 = 29.94
        assert _latest_actual(vals, _PERIODS, "annual") == ("2025.12", "29.94")

    def test_quarter_skips_estimate_and_empty(self):
        vals = ["27.93", "29.94", "", "29.94", "30.15", ""]
        # 2026.06은 추정치(빈값) 제외 → 2026.03 = 30.15 (현재 코드가 쓰던 [1]=2024가 아님!)
        assert _latest_actual(vals, _PERIODS, "quarter") == ("2026.03", "30.15")

    def test_none_when_all_empty(self):
        assert _latest_actual(["", "", "", "", "", ""], _PERIODS, "quarter") == ("", "")


class TestBuildFinancials:
    def test_maps_rows_to_latest_values(self):
        table = {
            "periods": [
                {"period": "2025.12", "kind": "annual", "estimate": False},
                {"period": "2026.03", "kind": "quarter", "estimate": False},
            ],
            "rows": {
                "부채비율": ["29.94", "30.15"],
                "매출액": ["3,336,059", "1,338,734"],
                "ROE(지배주주)": ["10.85", "19.16"],
            },
        }
        fin = _build_financials(table)
        assert fin["debt_ratio"]["quarter"] == ("2026.03", "30.15")
        assert fin["debt_ratio"]["annual"] == ("2025.12", "29.94")
        assert fin["revenue"]["quarter"] == ("2026.03", "1,338,734")
        assert fin["roe"]["quarter"] == ("2026.03", "19.16")

    def test_empty_table(self):
        assert _build_financials(None) == {}
