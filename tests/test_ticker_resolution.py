"""티커 해석(B1: DART corp 테이블 기반 자동 해석) 단위테스트."""
import data_collectors.dart_api as dart
import services.data_pipeline_service as dps


FAKE_ROWS = [
    {"corp_name": "삼성전자", "stock_code": "005930"},
    {"corp_name": "카카오", "stock_code": "035720"},
    {"corp_name": "어떤비상장", "stock_code": ""},
]


class TestFindStockCode:
    def test_exact_listed(self, monkeypatch):
        monkeypatch.setattr(dart, "load_corp_codes", lambda: FAKE_ROWS)
        assert dart.find_stock_code("카카오") == "035720"

    def test_unlisted_excluded(self, monkeypatch):
        # stock_code가 비어있는(비상장) 회사는 제외
        monkeypatch.setattr(dart, "load_corp_codes", lambda: FAKE_ROWS)
        assert dart.find_stock_code("어떤비상장") == ""

    def test_not_found(self, monkeypatch):
        monkeypatch.setattr(dart, "load_corp_codes", lambda: FAKE_ROWS)
        assert dart.find_stock_code("없는회사") == ""


class TestResolveTicker:
    def test_hardcoded_map_wins(self):
        assert dps.resolve_ticker("삼성전자") == {"yahoo": "005930.KS", "naver": "005930"}

    def test_six_digit_code(self):
        assert dps.resolve_ticker("000660") == {"yahoo": "000660.KS", "naver": "000660"}

    def test_dart_fallback_for_other_company(self, monkeypatch):
        # 맵에 없고 6자리도 아닌 이름 → DART corp 테이블 폴백
        monkeypatch.setattr(dps, "find_stock_code", lambda name: "035720")
        assert dps.resolve_ticker("카카오") == {"yahoo": "035720.KS", "naver": "035720"}

    def test_unresolvable_returns_empty(self, monkeypatch):
        monkeypatch.setattr(dps, "find_stock_code", lambda name: "")
        assert dps.resolve_ticker("정체불명회사") == {"yahoo": "", "naver": ""}
