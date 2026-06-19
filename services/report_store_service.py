import time
from typing import Any

from services.company_identity_service import normalize_company_name


def build_report_doc(session_id: str, report_data: dict) -> dict[str, Any]:
    structured = report_data.get("structured_report") or {}
    company = normalize_company_name(report_data.get("company", ""))
    return {
        "doc_id": f"report_{session_id}_{int(time.time())}",
        "session_id": session_id,
        "company": company,
        "judgement": report_data.get("judgement", structured.get("judgement", "")),
        "one_line_summary": report_data.get(
            "one_line_summary",
            structured.get("one_line_summary", ""),
        ),
        "investment_thesis": report_data.get(
            "investment_thesis",
            structured.get("investment_thesis", []),
        ),
        "judgement_change_conditions": report_data.get(
            "judgement_change_conditions",
            structured.get("judgement_change_conditions", []),
        ),
        "fact_summary": report_data.get("fact_summary", ""),
        "analysis_summary": report_data.get("analysis_summary", ""),
        "risk_summary": report_data.get("risk_summary", ""),
        "monitoring_checklist": report_data.get(
            "monitoring_checklist",
            structured.get("monitoring_checklist", []),
        ),
        "ten_line_summary": report_data.get(
            "ten_line_summary",
            structured.get("ten_line_summary", []),
        ),
        "data_limitations": report_data.get(
            "data_limitations",
            structured.get("data_limitations", ""),
        ),
        "structured_report": structured,
        "disclosure_events": report_data.get("disclosure_events", []),
        "final_report": report_data.get("final_report", ""),
        "report_mode": report_data.get("report_mode", ""),
        "created_at": int(time.time()),
    }


def save_report_to_index(session_id: str, report_data: dict):
    from indexing.meili_indexer import add_documents

    doc = build_report_doc(session_id, report_data)
    index_result = add_documents("reports", [doc])
    return {
        "saved": True,
        "indexed": True,
        "doc": doc,
        "index_result": index_result,
    }
