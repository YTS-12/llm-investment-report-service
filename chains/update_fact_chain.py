from langchain_core.output_parsers import StrOutputParser
from langchain_core.prompts import ChatPromptTemplate

from chains.common import llm


prompt = ChatPromptTemplate.from_messages(
    [
        (
            "system",
            """
당신은 투자 보고서의 업데이트 분석 보조자다.
이전 보고서와 최신 데이터를 비교해 '무엇이 실제로 중요하게 달라졌는지'만 사실로 정리해야 한다.

[데이터 취급 원칙]
- 공시, 시장/재무, 거시, 뉴스 4개 출처의 변화를 동등한 비중으로 본다.
- 출처 종류로 차등하지 않고, 사실의 구체성·검증 가능성·최신성으로 판단한다.

[정리 원칙]
- 해석하지 말고 사실만 정리한다.
- 의미 없는 문장 변화나 표현 차이는 제외한다.
- 어느 출처에서든 실제로 달라진 사실을 빠짐없이 적는다.

[출력 형식]
1. 새롭게 추가된 고중요 사실
2. 이전 보고서 이후 달라진 사실
3. 변화가 있지만 중요도가 낮은 항목
4. 변화 없음 또는 추가 확인 필요 항목
""",
        ),
        (
            "human",
            """
회사: {company}

[이전 보고서]
{previous_report}

[최신 뉴스]
{news}

[최신 공시]
{disclosures}

[최신 시장 데이터]
{market_data}

[최신 거시]
{macro}

위 내용을 4개 출처 동등 비중으로 비교해 사실만 정리해줘.
""",
        ),
    ]
)


update_fact_chain = prompt | llm | StrOutputParser()
