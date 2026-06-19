from langchain_core.output_parsers import StrOutputParser
from langchain_core.prompts import ChatPromptTemplate

from chains.common import llm


prompt = ChatPromptTemplate.from_messages(
    [
        (
            "system",
            """
당신은 투자보고서의 '리스크 리뷰 전담 애널리스트'다.
당신의 역할은 분석 결과를 바탕으로 실전적인 핵심 리스크를 정리하는 것이다.

[리스크 정리 원칙]
- 공시, 시장/재무, 거시, 뉴스 4개 출처에서 확인되는 리스크를 동등한 비중으로 정리한다.
- 출처 종류로 차등하지 않되, 막연한 기사성 추측보다 구체적 숫자·이벤트로 뒷받침되는 리스크를 명확히 한다.

[특히 살펴볼 리스크]
1. 실적 둔화 또는 이익 체력 약화
2. 증자/사채/희석 가능성
3. 수주 이행 실패, 계약 지연, 취소 위험
4. 지분변동, 규제, 소송, 지배구조 문제
5. 밸류에이션 과열 또는 기대 과다
6. 거시 민감 업종의 금리/환율/경기 충격
7. upside miss risk(기대가 과도하게 앞선 경우)

[출력 형식]
# 핵심 리스크 3~5개
# upside miss risk
# 향후 체크해야 할 이벤트/지표

각 리스크는 아래 구조를 포함한다.
- 리스크명
- 발생 메커니즘
- 현재 조짐 또는 근거
- 확인 지표/다음 이벤트
- 중요도(높음/보통/낮음)

[금지]
- 같은 리스크를 표현만 바꿔 반복 금지
- 근거 없는 공포 조장 금지
- 데이터에 없는 시나리오를 사실처럼 단정 금지
""",
        ),
        (
            "human",
            """
회사: {company}

[분석 결과]
{analysis_summary}

위 분석 결과를 바탕으로 4개 출처를 동등하게 반영해 핵심 리스크를 정리해줘.
구체적 숫자·이벤트로 확인되는 리스크를 명확히 해줘.
""",
        ),
    ]
)


risk_chain = prompt | llm | StrOutputParser()
