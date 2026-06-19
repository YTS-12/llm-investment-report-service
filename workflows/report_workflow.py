from typing import TypedDict
from langgraph.graph import StateGraph, START, END

from chains.fact_chain import fact_chain
from chains.analysis_chain import analysis_chain
from chains.risk_chain import risk_chain
from chains.report_chain import report_chain
from chains.structured_report_chain import structured_report_chain


class ReportState(TypedDict, total=False):
    company: str
    news: str
    disclosures: str
    market_data: str
    macro: str
    fact_summary: str
    analysis_summary: str
    risk_summary: str
    report_draft: str
    structured_report: dict
    final_report: str
    judgement: str
    one_line_summary: str
    investment_thesis: list[str]
    judgement_change_conditions: list[str]
    monitoring_checklist: list[str]
    ten_line_summary: list[str]
    data_limitations: str


def fact_node(state: ReportState):
    result = fact_chain.invoke({
        "company": state["company"],
        "news": state["news"],
        "disclosures": state["disclosures"],
        "market_data": state["market_data"],
        "macro": state["macro"],
    })
    return {"fact_summary": result}


def analysis_node(state: ReportState):
    result = analysis_chain.invoke({
        "company": state["company"],
        "fact_summary": state["fact_summary"],
    })
    return {"analysis_summary": result}


def risk_node(state: ReportState):
    result = risk_chain.invoke({
        "company": state["company"],
        "analysis_summary": state["analysis_summary"],
    })
    return {"risk_summary": result}


def report_node(state: ReportState):
    result = report_chain.invoke({
        "company": state["company"],
        "fact_summary": state["fact_summary"],
        "analysis_summary": state["analysis_summary"],
        "risk_summary": state["risk_summary"],
    })
    return {"report_draft": result}


def structured_report_node(state: ReportState):
    result = structured_report_chain.invoke({
        "company": state["company"],
        "fact_summary": state["fact_summary"],
        "analysis_summary": state["analysis_summary"],
        "risk_summary": state["risk_summary"],
        "report_draft": state.get("report_draft", ""),
    })
    return {
        "structured_report": result.model_dump(),
        "final_report": result.markdown_report,
        "judgement": result.judgement,
        "one_line_summary": result.one_line_summary,
        "investment_thesis": result.investment_thesis,
        "judgement_change_conditions": result.judgement_change_conditions,
        "monitoring_checklist": result.monitoring_checklist,
        "ten_line_summary": result.ten_line_summary,
        "data_limitations": result.data_limitations or "",
    }


def build_workflow():
    graph = StateGraph(ReportState)

    graph.add_node("fact_node", fact_node)
    graph.add_node("analysis_node", analysis_node)
    graph.add_node("risk_node", risk_node)
    graph.add_node("report_node", report_node)
    graph.add_node("structured_report_node", structured_report_node)

    graph.add_edge(START, "fact_node")
    graph.add_edge("fact_node", "analysis_node")
    graph.add_edge("analysis_node", "risk_node")
    graph.add_edge("risk_node", "report_node")
    graph.add_edge("report_node", "structured_report_node")
    graph.add_edge("structured_report_node", END)

    return graph.compile()
