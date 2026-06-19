from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import StrOutputParser
from chains.common import llm

prompt = ChatPromptTemplate.from_messages([
    (
        "system",
        """
당신은 국내 투자 보고서 생성 서비스의 후속 질문 응답자다.
반드시 이전 보고서와 대화 맥락을 참고해서 답하라.
모르는 내용은 모른다고 말하고, 이전 보고서에 없는 사실은 추정하지 마라.
"""
    ),
    (
        "human",
        """
[세션 대화 기록]
{memory}

[가장 최근 보고서]
{latest_report}

[사용자 질문]
{question}

답변 형식:
1. 질문에 대한 직접 답변
2. 이전 보고서와의 연결점
3. 필요하면 추가 확인이 필요한 데이터
"""
    )
])

chat_followup_chain = prompt | llm | StrOutputParser()