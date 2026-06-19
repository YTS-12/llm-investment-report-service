from typing import TypedDict
from langgraph.graph import StateGraph, START, END

from services.report_retrieval_service import find_previous_reports
from chains.update_fact_chain import update_fact_chain
from chains.diff_chain import diff_chain
from chains.update_report_chain import update_report_chain
from chains.risk_chain import risk_chain
from chains.structured_report_chain import structured_report_chain


class UpdateReportState(TypedDict, total=False):
    company: str
    news: str
    disclosures: str
    market_data: str
    macro: str
    previous_report: str
    update_fact_summary: str
    diff_summary: str
    update_risk_summary: str
    structured_report: dict
    final_update_report: str
    judgement: str
    one_line_summary: str
    investment_thesis: list[str]
    judgement_change_conditions: list[str]
    monitoring_checklist: list[str]
    ten_line_summary: list[str]
    data_limitations: str


def retrieve_previous_report_node(state: UpdateReportState):
    hits = find_previous_reports(state["company"], limit=1)
    previous_report = hits[0]["final_report"] if hits else "이전 보고서 없음"
    return {"previous_report": previous_report}


def update_fact_node(state: UpdateReportState):
    result = update_fact_chain.invoke({
        "company": state["company"],
        "previous_report": state["previous_report"],
        "news": state["news"],
        "disclosures": state["disclosures"],
        "market_data": state["market_data"],
        "macro": state["macro"],
    })
    return {"update_fact_summary": result}


def diff_node(state: UpdateReportState):
    result = diff_chain.invoke({
        "company": state["company"],
        "update_fact_summary": state["update_fact_summary"],
    })
    return {"diff_summary": result}


def update_report_node(state: UpdateReportState):
    result = update_report_chain.invoke({
        "company": state["company"],
        "previous_report": state["previous_report"],
        "update_fact_summary": state["update_fact_summary"],
        "diff_summary": state["diff_summary"],
    })
    return {"final_update_report": result}


def update_risk_node(state: UpdateReportState):
    # diff_summary는 '무엇이 어떻게 달라졌는가'에 대한 해석이다.
    # 이를 분석 입력으로 보고 risk_chain으로 '변경분 기반' 리스크를 새로 도출한다.
    # (이전 버전은 diff_summary를 risk_summary 자리에 그대로 재사용해
    #  변경 해석이 리스크로 둔갑하는 문제가 있었다.)
    result = risk_chain.invoke({
        "company": state["company"],
        "analysis_summary": state["diff_summary"],
    })
    return {"update_risk_summary": result}


def structured_update_report_node(state: UpdateReportState):
    result = structured_report_chain.invoke({
        "company": state["company"],
        "fact_summary": state.get("update_fact_summary", ""),
        "analysis_summary": state.get("diff_summary", ""),
        "risk_summary": state.get("update_risk_summary", ""),
        "report_draft": state.get("final_update_report", ""),
    })
    return {
        "structured_report": result.model_dump(),
        "final_update_report": result.markdown_report,
        "judgement": result.judgement,
        "one_line_summary": result.one_line_summary,
        "investment_thesis": result.investment_thesis,
        "judgement_change_conditions": result.judgement_change_conditions,
        "monitoring_checklist": result.monitoring_checklist,
        "ten_line_summary": result.ten_line_summary,
        "data_limitations": result.data_limitations or "",
    }


def build_update_workflow():
    graph = StateGraph(UpdateReportState)

    graph.add_node("retrieve_previous_report_node", retrieve_previous_report_node)
    graph.add_node("update_fact_node", update_fact_node)
    graph.add_node("diff_node", diff_node)
    graph.add_node("update_report_node", update_report_node)
    graph.add_node("update_risk_node", update_risk_node)
    graph.add_node("structured_update_report_node", structured_update_report_node)

    graph.add_edge(START, "retrieve_previous_report_node")
    graph.add_edge("retrieve_previous_report_node", "update_fact_node")
    graph.add_edge("update_fact_node", "diff_node")
    graph.add_edge("diff_node", "update_report_node")
    graph.add_edge("update_report_node", "update_risk_node")
    graph.add_edge("update_risk_node", "structured_update_report_node")
    graph.add_edge("structured_update_report_node", END)

    return graph.compile()
