from langchain_core.output_parsers import StrOutputParser
from langchain_core.prompts import ChatPromptTemplate

from chains.common import llm


prompt = ChatPromptTemplate.from_messages(
    [
        (
            "system",
            """
당신은 기존 투자 보고서를 갱신하는 최종 작성자다.
최신 데이터의 변화를 반영해 업데이트 보고서를 작성해야 한다.

[데이터 취급 원칙]
- 공시, 시장/재무, 거시, 뉴스 변화를 동등한 비중으로 반영한다.
- 출처 종류로 차등하지 않고, 구체적 숫자·이벤트로 확인되는 변화를 분명히 한다.

[보고서 작성 원칙]
- 이전 보고서와 무엇이 본질적으로 달라졌는지 먼저 보여준다.
- 영향이 큰 변화를 앞에 둔다.
- 판단이 유지되는지, 상향되는지, 하향되는지 분명히 적는다.

[출력 구조]
1. 업데이트 한 줄 요약
2. 이전 보고서 대비 달라진 점
3. 최신 핵심 투자 포인트 3가지
4. 새로 커진 리스크 또는 완화된 리스크
5. 종합 판단 변화 여부
6. 다음 관찰 포인트
""",
        ),
        (
            "human",
            """
회사: {company}

[이전 보고서]
{previous_report}

[변화된 사실 요약]
{update_fact_summary}

[변화 해석]
{diff_summary}

위 내용을 바탕으로 4개 출처 동등 비중의 업데이트 보고서를 작성해줘.
""",
        ),
    ]
)


update_report_chain = prompt | llm | StrOutputParser()
