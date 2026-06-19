from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import StrOutputParser
from chains.common import llm

prompt = ChatPromptTemplate.from_messages([
    (
        "system",
        """
당신은 종목 비교 보고서 작성 보조자다. 입력 데이터에서 사실만 정리하라. 해석하지 마라.

[데이터 취급 원칙]
- 두 종목의 뉴스·공시·시장/재무·거시 4개 출처를 동등한 비중으로 비교한다.
- 출처 종류로 차등하지 않고, 사실의 구체성·검증 가능성·최신성으로 판단한다.
"""
    ),
    (
        "human",
        """
종목 A: {company_a}
[뉴스]
{news_a}
[공시]
{disclosures_a}
[시장 데이터]
{market_data_a}
[거시]
{macro_a}

종목 B: {company_b}
[뉴스]
{news_b}
[공시]
{disclosures_b}
[시장 데이터]
{market_data_b}
[거시]
{macro_b}

비교 관점에서 사실만 정리해줘.
1. 공통점
2. 차이점
3. A의 핵심 사실
4. B의 핵심 사실
"""
    )
])

compare_fact_chain = prompt | llm | StrOutputParser()
