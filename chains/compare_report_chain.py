from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import StrOutputParser
from chains.common import llm

prompt = ChatPromptTemplate.from_messages([
    (
        "system",
        """
당신은 국내 투자 비교 보고서 작성자다.
반드시 마크다운 형식으로 작성하라.
구조:
1. 비교 한 줄 요약
2. 종목 A 핵심 포인트
3. 종목 B 핵심 포인트
4. 상대 강점/약점 비교
5. 리스크 비교
6. 종합 판단
7. 다음 관찰 포인트
"""
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

최종 비교 보고서를 작성해줘.
"""
    )
])

compare_report_chain = prompt | llm | StrOutputParser()