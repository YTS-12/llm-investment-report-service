"""공시 요약·랭킹 로직 단위테스트."""
from services.data_pipeline_service import (
    summarize_disclosures,
    build_disclosure_events,
    DISCLOSURE_NOT_FOUND_MESSAGE,
)


def _disc(report_name, category, importance, receipt_date):
    return {
        "report_name": report_name,
        "category": category,
        "importance": importance,
        "receipt_date": receipt_date,
        "corp_name": "테스트",
        "signal": "",
        "event_name": "",
        "viewer_url": "",
        "impact_summary": "",
        "body_excerpt": "",
        "detail_metrics": {},
    }


class TestSummarizeDisclosures:
    def test_empty_returns_not_found(self):
        assert summarize_disclosures([]) == DISCLOSURE_NOT_FOUND_MESSAGE

    def test_importance_sorts_first(self):
        out = summarize_disclosures([
            _disc("일반공시", "general_disclosure", 2, "20260101"),
            _disc("잠정실적", "earnings_update", 5, "20260101"),
        ])
        assert out.index("잠정실적") < out.index("일반공시")

    def test_category_weight_breaks_tie(self):
        # 중요도 동일(5) → 카테고리 가중치(earnings 100 > financing 92)로 실적이 위
        out = summarize_disclosures([
            _disc("전환사채발행", "financing", 5, "20260301"),
            _disc("잠정실적공시", "earnings_update", 5, "20260101"),
        ])
        assert out.index("잠정실적공시") < out.index("전환사채발행")

    def test_top_k_truncation(self):
        items = [_disc(f"공시{i}", "general_disclosure", 2, f"2026010{i}") for i in range(1, 8)]
        out = summarize_disclosures(items, top_k=3)
        assert "공시7" in out      # 최신 → 포함
        assert "공시1" not in out  # 가장 오래됨 → 절단


class TestBuildDisclosureEvents:
    def test_preserves_detail_metrics(self):
        d = _disc("잠정실적", "earnings_update", 5, "20260101")
        d["detail_metrics"] = {"revenue": "12,345", "operating_income": "2,000"}
        events = build_disclosure_events([d])
        assert len(events) == 1
        assert events[0]["category"] == "earnings_update"
        assert events[0]["detail_metrics"]["revenue"] == "12,345"

    def test_ranking_and_top_k(self):
        items = [
            _disc("일반", "general_disclosure", 2, "20260101"),
            _disc("실적", "earnings_update", 5, "20260101"),
            _disc("계약", "contract", 4, "20260101"),
        ]
        events = build_disclosure_events(items, top_k=2)
        names = [e["report_name"] for e in events]
        assert names == ["실적", "계약"]  # 중요도순; 일반(2)은 top_k=2에서 제외


class TestHighImportanceProtection:
    def test_protected_never_truncated(self):
        # 중요도 5 공시가 top_k보다 많아도 전부 포함된다(절단 보호)
        items = [_disc(f"증자{i}", "capital_change", 5, f"2026010{i}") for i in range(1, 7)]
        out = summarize_disclosures(items, top_k=3)
        for i in range(1, 7):
            assert f"증자{i}" in out

    def test_low_importance_still_truncated(self):
        # 저중요도는 보호 대상이 아니므로 top_k에서 잘린다
        items = [_disc(f"일반{i}", "general_disclosure", 2, f"2026010{i}") for i in range(1, 7)]
        out = summarize_disclosures(items, top_k=3)
        included = sum(1 for i in range(1, 7) if f"일반{i}" in out)
        assert included == 3


class TestFetchPriorityDisclosures:
    def test_merges_types_and_dedups(self, monkeypatch):
        import services.data_pipeline_service as dps

        by_type = {
            "A": [{"rcept_no": "1", "report_nm": "분기보고서 (2026.03)"}],
            "B": [{"rcept_no": "2", "report_nm": "주요사항보고서(유상증자결정)"}],
            "I": [
                {"rcept_no": "2", "report_nm": "중복(이미 B에 있음)"},
                {"rcept_no": "3", "report_nm": "연결재무제표기준영업(잠정)실적(공정공시)"},
            ],
        }

        def fake_search(corp, start, end, page_count=10, pblntf_ty=None):
            return {"list": by_type.get(pblntf_ty, [])}

        monkeypatch.setattr(dps, "search_disclosures", fake_search)
        merged = dps._fetch_priority_disclosures("00126380", "20250101", "20260101")
        rcepts = [it["rcept_no"] for it in merged["list"]]
        # A,B,I 순서로 병합 + rcept_no=2 중복 제거
        assert rcepts == ["1", "2", "3"]


class TestDedupeEarnings:
    def test_keeps_latest_clean_earnings_only(self):
        from services.data_pipeline_service import _dedupe_earnings_disclosures

        disc = [
            {"category": "earnings_update", "receipt_date": "20260430",
             "detail_metrics": {"revenue": "133.87", "operating_income": "57.23"},
             "report_name": "[기재정정]잠정실적"},
            {"category": "earnings_update", "receipt_date": "20260430",
             "detail_metrics": {"revenue": "1,338,734", "operating_income": "572,328", "net_income": "x"},
             "report_name": "잠정실적"},
            {"category": "earnings_update", "receipt_date": "20260129",
             "detail_metrics": {"revenue": "938,374"}, "report_name": "잠정실적 과거분기"},
            {"category": "shareholder_return", "receipt_date": "20260318",
             "detail_metrics": {}, "report_name": "자사주"},
        ]
        out = _dedupe_earnings_disclosures(disc)
        earn = [d for d in out if d["category"] == "earnings_update"]
        assert len(earn) == 1  # 정정/원본/과거분기 중복 제거 → 1건
        assert earn[0]["detail_metrics"]["revenue"] == "1,338,734"  # 억원 깔끔한 변형 채택
        assert any(d["category"] == "shareholder_return" for d in out)  # 비-실적은 유지

    def test_single_or_none_unchanged(self):
        from services.data_pipeline_service import _dedupe_earnings_disclosures

        one = [{"category": "earnings_update", "receipt_date": "20260430",
                "detail_metrics": {"revenue": "1,338,734"}}]
        assert _dedupe_earnings_disclosures(one) == one
        assert _dedupe_earnings_disclosures([]) == []
