from langchain_core.prompts import ChatPromptTemplate

from chains.common import llm
from schemas.report_schema import StructuredFollowupAnswer


prompt = ChatPromptTemplate.from_messages(
    [
        (
            "system",
            """
당신은 국내 투자 보고서 생성 서비스의 구조화 후속질문 응답자다.
반드시 이전 보고서와 대화 맥락을 참고해서, 구조화된 응답 스키마를 채워라.

[핵심 규칙]
- company와 question은 입력값 그대로 유지한다.
- short_answer는 질문에 대한 직접 답변이어야 한다.
- supporting_points는 최소 2개 이상 작성한다.
- 입력 데이터에 없는 사실은 추정하지 않는다.
- 부족한 정보가 있으면 missing_data에 적고, answer_markdown에도 명시한다.
""",
        ),
        (
            "human",
            """
회사: {company}

[세션 대화 기록]
{memory}

[가장 최근 보고서]
{latest_report}

[사용자 질문]
{question}

위 정보를 바탕으로 구조화된 후속질문 응답을 생성해줘.
""",
        ),
    ]
)


structured_followup_chain = prompt | llm.with_structured_output(
    StructuredFollowupAnswer,
    method="json_schema",
)
