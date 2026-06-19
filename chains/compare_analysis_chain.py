from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import StrOutputParser
from chains.common import llm

prompt = ChatPromptTemplate.from_messages([
    (
        "system",
        """
당신은 한국 주식 비교 분석가다. 두 종목의 상대적 강점과 약점을 해석하라.

[데이터 취급 원칙]
- 뉴스·공시·시장/재무·거시 4개 출처를 동등한 비중으로 반영해 비교한다.
- 출처 종류로 차등하지 않는다.
"""
    ),
    (
        "human",
        """
종목 A: {company_a}
종목 B: {company_b}

[비교 사실 요약]
{fact_summary}

아래 기준으로 해석해줘:
1. 상대 강점
2. 상대 약점
3. 뉴스/공시 관점 차이
4. 시장/거시 민감도 차이
5. 현재 시점에서 더 유리한 쪽과 그 이유
"""
    )
])

compare_analysis_chain = prompt | llm | StrOutputParser()
