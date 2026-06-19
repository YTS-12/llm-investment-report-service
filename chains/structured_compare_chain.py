from langchain_core.prompts import ChatPromptTemplate

from chains.common import llm
from schemas.report_schema import StructuredCompareReport


prompt = ChatPromptTemplate.from_messages(
    [
        (
            "system",
            """
당신은 국내 주식 비교 보고서의 구조화 작성자다.
입력된 비교 사실과 비교 해석을 바탕으로 반드시 스키마에 맞는 구조화 비교 보고서를 작성하라.

[핵심 규칙]
- company_a, company_b는 입력값 그대로 유지한다.
- overall_winner는 A, B, 유사, 판단 유보 중 하나만 사용한다.
- comparison_points는 최소 3개 이상 작성한다.
- 각 비교 포인트는 숫자나 구체 이벤트를 근거로 삼는다.
- 데이터가 부족하면 winner를 '판단 유보' 또는 '유사'로 둔다.
- markdown_report는 사용자에게 바로 보여줄 수 있는 완결형 보고서여야 한다.
""",
        ),
        (
            "human",
            """
종목 A: {company_a}
종목 B: {company_b}

[비교 사실 요약]
{fact_summary}

[비교 해석]
{analysis_summary}

[비교 초안]
{report_draft}

위 정보를 바탕으로 구조화 비교 보고서를 생성해줘.
""",
        ),
    ]
)


structured_compare_chain = prompt | llm.with_structured_output(
    StructuredCompareReport,
    method="json_schema",
)
