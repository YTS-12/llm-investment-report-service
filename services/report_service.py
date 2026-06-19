from services.company_identity_service import normalize_company_name
from workflows.report_workflow import build_workflow
from services.report_formatter_service import build_fallback_report
from utils.logger import logger

app_workflow = build_workflow()

def generate_investment_report(
    company: str,
    news: str,
    disclosures: str,
    market_data: str,
    macro: str,
) -> dict:
    company = normalize_company_name(company)
    input_state = {
        "company": company,
        "news": news,
        "disclosures": disclosures,
        "market_data": market_data,
        "macro": macro,
    }

    try:
        result = app_workflow.invoke(input_state)
    except Exception as exc:
        logger.exception(
            "Report generation fallback | company=%s | error=%s",
            company,
            repr(exc),
        )
        fallback_report = build_fallback_report(
            company=company,
            news=news,
            disclosures=disclosures,
            market_data=market_data,
            macro=macro,
            reason=str(exc),
        )
        return {
            "company": company,
            "fact_summary": news or disclosures or market_data or macro,
            "analysis_summary": "LLM 연결 실패로 심화 분석을 수행하지 못했습니다.",
            "risk_summary": "외부 모델 연결 또는 네트워크 상태를 확인해야 합니다.",
            "final_report": fallback_report,
            "report_mode": "fallback",
            "generation_error": str(exc),
        }

    response = {
        "company": company,
        "fact_summary": result.get("fact_summary", ""),
        "analysis_summary": result.get("analysis_summary", ""),
        "risk_summary": result.get("risk_summary", ""),
        "final_report": result.get("final_report", ""),
        "report_mode": "new",
    }

    for field in [
        "structured_report",
        "judgement",
        "one_line_summary",
        "investment_thesis",
        "judgement_change_conditions",
        "monitoring_checklist",
        "ten_line_summary",
        "data_limitations",
    ]:
        if field in result:
            response[field] = result.get(field)

    return response
