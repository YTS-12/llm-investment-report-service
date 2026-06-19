from langchain_core.output_parsers import StrOutputParser
from langchain_core.prompts import ChatPromptTemplate

from chains.common import llm


prompt = ChatPromptTemplate.from_messages(
    [
        (
            "system",
            """
당신은 투자 보고서의 변화 해석 담당자다.
업데이트 팩트 요약을 바탕으로, 무엇이 투자 판단을 실제로 바꾸는 변화인지 해석해야 한다.

[데이터 취급 원칙]
- 공시, 시장/재무, 거시, 뉴스 변화를 동등한 비중으로 본다.
- 출처 종류로 차등하지 않고, 구체적 숫자·이벤트로 확인되는 변화를 분명히 한다.

[해석 규칙]
- 투자 판단에 큰 영향을 주는 변화부터 다룬다.
- 변화의 방향을 긍정/부정/중립으로 나눈다.
- 이전 판단을 바꿀 만큼 강한 변화인지 따로 표시한다.

[출력 형식]
1. 투자 판단에 가장 큰 영향을 주는 변화 3가지
2. 긍정 변화
3. 부정 변화
4. 중립 변화
5. 판단 변경 가능성이 있는 추가 확인 포인트
""",
        ),
        (
            "human",
            """
회사: {company}

[변화된 사실 요약]
{update_fact_summary}

위 변화된 사실 요약을 4개 출처 동등 비중으로 해석해줘.
""",
        ),
    ]
)


diff_chain = prompt | llm | StrOutputParser()
