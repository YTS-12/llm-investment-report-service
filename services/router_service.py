from services.company_identity_service import normalize_company_name
from services.report_retrieval_service import find_previous_reports


def detect_report_mode(company: str) -> dict:
    """
    회사명 기준으로 이전 보고서 존재 여부를 확인하고
    report_mode를 결정한다.
    """
    company = normalize_company_name(company)
    previous_reports = find_previous_reports(company, limit=1)

    if previous_reports:
        return {
            "report_mode": "update",
            "previous_report": previous_reports[0].get("final_report", ""),
            "previous_report_doc": previous_reports[0],
        }

    return {
        "report_mode": "new",
        "previous_report": "",
        "previous_report_doc": None,
    }
