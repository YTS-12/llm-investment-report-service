"""유틸·서비스 순수 로직 단위테스트 (외부 API 불필요)."""
from utils.text_similarity import is_similar, ratio, normalize_for_compare
from services.company_identity_service import normalize_company_name
from services.macro_interpretation_service import (
    interpret_macro,
    get_sector_sensitivity,
    classify_inflation_regime,
)


class TestTextSimilarity:
    def test_identical(self):
        assert ratio("삼성전자 실적", "삼성전자 실적") == 1.0

    def test_near_duplicate(self):
        assert is_similar("삼성전자 3분기 실적 발표", "삼성전자 3분기 실적 발표!", 0.9)

    def test_clearly_different(self):
        assert not is_similar("삼성전자 실적", "현대차 신차 출시", 0.9)

    def test_normalize_strips_punctuation(self):
        assert normalize_for_compare("[속보] 삼성, 신기록.") == "속보 삼성 신기록"


class TestCompanyIdentity:
    def test_alias_samsung(self):
        assert normalize_company_name("삼성") == "삼성전자"

    def test_alias_hynix(self):
        assert normalize_company_name("하이닉스") == "SK하이닉스"

    def test_six_digit_code_passthrough(self):
        assert normalize_company_name("005930") == "005930"

    def test_unknown_passthrough(self):
        assert normalize_company_name("없는회사") == "없는회사"


class TestInterpretMacro:
    def test_semiconductor_positive(self):
        r = interpret_macro("반도체", "금리 인하 기대", "원화 약세", "경기 회복")
        assert r["rate_regime"] == "rate_cut_expectation"
        assert r["fx_regime"] == "weak_krw"
        assert r["growth_regime"] == "growth_recovery"
        # 반도체(rate=1,fx=2,growth=2): 금리인하 -1, 약세 +2, 회복 +2 = 3
        assert r["macro_score"] == 3
        assert r["macro_impact"] == "긍정"

    def test_unknown_sector_neutral(self):
        # 미정의 업종 → 민감도 전부 0 → score 0 → 중립
        r = interpret_macro("정체불명업종", "금리 인하", "원화 약세", "경기 회복")
        assert r["macro_score"] == 0
        assert r["macro_impact"] == "중립"

    def test_stable_regimes_neutral(self):
        r = interpret_macro("반도체", "금리 안정", "환율 안정", "경기 중립")
        assert r["rate_regime"] == "rate_stable"
        assert r["inflation_regime"] == "inflation_stable"
        assert r["macro_impact"] == "중립"

    def test_inflation_dimension_active(self):
        # 정유(inflation=+1): 물가 확대 국면 → +1 반영 (물가 차원 복구 확인)
        r = interpret_macro(
            "정유", "금리 안정", "환율 안정", "경기 중립",
            inflation_view="소비자물가 상승 압력이 확대되고 있다",
        )
        assert r["inflation_regime"] == "inflation_high"
        assert r["macro_score"] == 1

    def test_steel_benefits_from_strong_won(self):
        # 철강(fx=-1): 수출주와 반대 — 원화 강세에서 점수가 더 높아야 함
        weak = interpret_macro("철강", "금리 안정", "원화 약세 흐름", "경기 중립")
        strong = interpret_macro("철강", "금리 안정", "원화 강세 흐름이 확인된다", "경기 중립")
        assert strong["fx_regime"] == "strong_krw"
        assert strong["macro_score"] > weak["macro_score"]


class TestSectorSensitivity:
    def test_new_sector_loaded_from_json(self):
        # 외부 JSON에서 신규 업종(조선)이 로드되는지
        assert get_sector_sensitivity("조선")["fx"] == 2

    def test_alias_partial_match(self):
        # "은행/금융" → 은행으로 부분 매칭
        assert get_sector_sensitivity("은행/금융")["rate"] == 2

    def test_unknown_returns_neutral(self):
        s = get_sector_sensitivity("정체불명업종")
        assert s.get("rate", 0) == 0 and s.get("fx", 0) == 0


class TestClassifyInflation:
    def test_high(self):
        assert classify_inflation_regime("소비자물가 상승 압력이 확대") == "inflation_high"

    def test_low(self):
        assert classify_inflation_regime("소비자물가 상승세가 둔화") == "inflation_low"

    def test_stable(self):
        assert classify_inflation_regime("") == "inflation_stable"
