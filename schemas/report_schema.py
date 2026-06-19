from typing import List, Literal, Optional

from pydantic import BaseModel, Field


ConfidenceLevel = Literal["높음", "보통", "낮음"]
JudgementType = Literal["관심", "관망", "보수적 접근", "추가 확인 필요"]
TimeHorizon = Literal["단기", "중기", "장기"]
ImportanceLevel = Literal["높음", "보통", "낮음"]


class KeyPoint(BaseModel):
    title: str = Field(..., description="핵심 포인트 제목")
    evidence: str = Field(..., description="핵심 근거 사실 또는 수치")
    implication: str = Field(..., description="투자 관점에서의 의미")
    time_horizon: TimeHorizon = Field(..., description="영향 시계열 구분")
    confidence: ConfidenceLevel = Field(..., description="해당 해석의 확신 수준")


class RiskItem(BaseModel):
    category: Literal[
        "실적 리스크",
        "재무/유동성/희석 리스크",
        "수주/이행/운영 리스크",
        "거시/환율/금리 리스크",
        "밸류에이션/포지셔닝 리스크",
        "규제/소송/거버넌스 리스크",
        "상방 놓침 리스크",
    ] = Field(..., description="리스크 카테고리")
    risk_name: str = Field(..., description="리스크명")
    mechanism: str = Field(..., description="리스크 발생 메커니즘")
    current_signal: str = Field(..., description="현재 조짐 또는 관찰 근거")
    check_points: List[str] = Field(..., description="향후 확인할 이벤트/지표")
    importance: ImportanceLevel = Field(..., description="중요도")


class FactConflictItem(BaseModel):
    issue: str = Field(..., description="상충하거나 확인이 필요한 이슈")
    preferred_source: str = Field(..., description="우선 채택한 출처")
    note: str = Field(..., description="확인 필요 사유 또는 처리 기준")


class StructuredReport(BaseModel):
    company: str = Field(..., description="회사명")
    judgement: JudgementType = Field(..., description="현재 투자 판단")
    one_line_summary: str = Field(..., description="한 줄 투자 판단 요약")
    investment_thesis: List[str] = Field(..., description="핵심 투자 근거 2~4개")
    judgement_change_conditions: List[str] = Field(
        ..., description="판단을 바꿀 수 있는 조건"
    )
    company_overview: str = Field(..., description="기업 개요 및 핵심 투자 전제")
    key_points: List[KeyPoint] = Field(..., description="최근 핵심 포인트 3개 이상")
    financial_interpretation: str = Field(..., description="실적/재무/밸류에이션 해석")
    disclosure_interpretation: str = Field(..., description="공시/이벤트 해설")
    market_interpretation: str = Field(..., description="수급/가격/심리 해석")
    macro_interpretation: str = Field(..., description="거시환경 영향 해석")
    key_risks: List[RiskItem] = Field(..., description="핵심 리스크 3개 이상")
    fact_conflicts: List[FactConflictItem] = Field(
        default_factory=list,
        description="상충 정보 또는 추가 확인 필요 사항",
    )
    monitoring_checklist: List[str] = Field(
        ..., description="향후 관찰 포인트 체크리스트"
    )
    ten_line_summary: List[str] = Field(..., description="10줄 이내 요약")
    markdown_report: str = Field(..., description="사용자용 최종 마크다운 보고서")
    data_limitations: Optional[str] = Field(
        default="",
        description="데이터 부족 또는 제약 사항",
    )


class ComparisonPoint(BaseModel):
    topic: str = Field(..., description="비교 주제")
    company_a_view: str = Field(..., description="종목 A 관점 요약")
    company_b_view: str = Field(..., description="종목 B 관점 요약")
    winner: Literal["A", "B", "유사", "판단 유보"] = Field(
        ..., description="상대 우위 판단"
    )
    reason: str = Field(..., description="판단 근거")


class StructuredCompareReport(BaseModel):
    company_a: str = Field(..., description="종목 A")
    company_b: str = Field(..., description="종목 B")
    one_line_summary: str = Field(..., description="한 줄 비교 요약")
    overall_winner: Literal["A", "B", "유사", "판단 유보"] = Field(
        ..., description="종합 상대 우위"
    )
    comparison_points: List[ComparisonPoint] = Field(
        ..., description="주요 비교 포인트 3개 이상"
    )
    risk_comparison: List[str] = Field(..., description="리스크 비교 요약")
    monitoring_points: List[str] = Field(..., description="비교 관찰 포인트")
    markdown_report: str = Field(..., description="최종 비교 보고서 마크다운")


class StructuredFollowupAnswer(BaseModel):
    company: str = Field(..., description="질문 대상 회사")
    question: str = Field(..., description="사용자 질문")
    short_answer: str = Field(..., description="질문에 대한 직접 답변")
    supporting_points: List[str] = Field(..., description="근거 포인트")
    missing_data: List[str] = Field(
        default_factory=list,
        description="추가 확인이 필요한 데이터",
    )
    answer_markdown: str = Field(..., description="사용자에게 보여줄 마크다운 답변")
