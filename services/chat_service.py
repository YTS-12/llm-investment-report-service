from services.company_identity_service import normalize_company_name
from chains.chat_followup_chain import chat_followup_chain
from chains.structured_followup_chain import structured_followup_chain
from services.memory_service import load_messages
from services.report_formatter_service import build_fallback_followup_answer
from services.report_retrieval_service import find_previous_reports
from utils.logger import logger


def format_memory(messages: list[dict], max_turns: int = 10) -> str:
    selected = messages[-max_turns:]
    lines = []
    for msg in selected:
        lines.append(f"{msg['role']}: {msg['content']}")
    return "\n".join(lines)


def answer_followup(session_id: str, company: str, question: str) -> dict:
    company = normalize_company_name(company)
    memory = load_messages(session_id)
    memory_text = format_memory(memory)

    reports = find_previous_reports(company, limit=1)
    latest_report = reports[0]["final_report"] if reports else "이전 보고서 없음"

    try:
        answer = chat_followup_chain.invoke(
            {
                "memory": memory_text,
                "latest_report": latest_report,
                "question": question,
            }
        )
        structured_answer = structured_followup_chain.invoke(
            {
                "company": company,
                "memory": memory_text,
                "latest_report": latest_report,
                "question": question,
            }
        )
    except Exception as exc:
        logger.exception(
            "Follow-up fallback | session_id=%s | company=%s | error=%s",
            session_id,
            company,
            repr(exc),
        )
        answer = build_fallback_followup_answer(
            question=question,
            latest_report=latest_report,
            reason=str(exc),
        )
        structured_answer = None

    response = {
        "session_id": session_id,
        "company": company,
        "answer": answer,
    }
    if structured_answer is not None:
        response["structured_followup"] = structured_answer.model_dump()
        response["short_answer"] = structured_answer.short_answer
    return response
