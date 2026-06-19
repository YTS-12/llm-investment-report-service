from services.company_identity_service import normalize_company_name
from chains.structured_compare_chain import structured_compare_chain
from services.report_formatter_service import build_fallback_compare_report
from services.report_retrieval_service import find_previous_reports
from utils.logger import logger
from workflows.compare_report_workflow import build_compare_workflow


compare_app = build_compare_workflow()


def generate_compare_report(
    company_a: str,
    sector_a: str,
    company_b: str,
    sector_b: str,
) -> dict:
    company_a = normalize_company_name(company_a)
    company_b = normalize_company_name(company_b)
    previous_a = find_previous_reports(company_a, limit=1)
    previous_b = find_previous_reports(company_b, limit=1)

    report_a = (
        previous_a[0]["final_report"]
        if previous_a
        else f"{company_a}에 대한 저장된 보고서가 없습니다. 업종 참고값은 {sector_a}입니다."
    )
    report_b = (
        previous_b[0]["final_report"]
        if previous_b
        else f"{company_b}에 대한 저장된 보고서가 없습니다. 업종 참고값은 {sector_b}입니다."
    )

    try:
        result = compare_app.invoke(
            {
                "company_a": company_a,
                "company_b": company_b,
                "news_a": report_a,
                "disclosures_a": "",
                "market_data_a": "",
                "macro_a": f"업종: {sector_a}",
                "news_b": report_b,
                "disclosures_b": "",
                "market_data_b": "",
                "macro_b": f"업종: {sector_b}",
            }
        )
        final_report = result["final_report"]
        structured_result = structured_compare_chain.invoke(
            {
                "company_a": company_a,
                "company_b": company_b,
                "fact_summary": result.get("fact_summary", ""),
                "analysis_summary": result.get("analysis_summary", ""),
                "report_draft": final_report,
            }
        )
    except Exception as exc:
        logger.exception(
            "Compare report fallback | company_a=%s | company_b=%s | error=%s",
            company_a,
            company_b,
            repr(exc),
        )
        final_report = build_fallback_compare_report(
            company_a=company_a,
            company_b=company_b,
            report_a=report_a,
            report_b=report_b,
            reason=str(exc),
        )
        structured_result = None

    response = {
        "company_a": company_a,
        "company_b": company_b,
        "final_report": final_report,
        "comparison_mode": "local_compare",
    }
    if structured_result is not None:
        response["structured_compare"] = structured_result.model_dump()
        response["one_line_summary"] = structured_result.one_line_summary
        response["overall_winner"] = structured_result.overall_winner
    return response
