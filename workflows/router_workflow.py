from typing import TypedDict
from langgraph.graph import StateGraph, START, END

from services.router_service import detect_report_mode
from workflows.report_workflow import build_workflow
from workflows.update_report_workflow import build_update_workflow


new_report_app = build_workflow()
update_report_app = build_update_workflow()


class RouterState(TypedDict, total=False):
    company: str
    news: str
    disclosures: str
    market_data: str
    macro: str
    report_mode: str
    previous_report: str
    structured_report: dict
    judgement: str
    one_line_summary: str
    investment_thesis: list[str]
    judgement_change_conditions: list[str]
    monitoring_checklist: list[str]
    ten_line_summary: list[str]
    data_limitations: str
    final_report: str


def detect_mode_node(state: RouterState):
    result = detect_report_mode(state["company"])
    return {
        "report_mode": result["report_mode"],
        "previous_report": result["previous_report"],
    }


def new_report_node(state: RouterState):
    result = new_report_app.invoke({
        "company": state["company"],
        "news": state["news"],
        "disclosures": state["disclosures"],
        "market_data": state["market_data"],
        "macro": state["macro"],
    })
    return {
        "final_report": result.get("final_report", ""),
        "structured_report": result.get("structured_report", {}),
        "judgement": result.get("judgement", ""),
        "one_line_summary": result.get("one_line_summary", ""),
        "investment_thesis": result.get("investment_thesis", []),
        "judgement_change_conditions": result.get("judgement_change_conditions", []),
        "monitoring_checklist": result.get("monitoring_checklist", []),
        "ten_line_summary": result.get("ten_line_summary", []),
        "data_limitations": result.get("data_limitations", ""),
    }


def update_report_node(state: RouterState):
    result = update_report_app.invoke({
        "company": state["company"],
        "news": state["news"],
        "disclosures": state["disclosures"],
        "market_data": state["market_data"],
        "macro": state["macro"],
        "previous_report": state.get("previous_report", ""),
    })
    return {
        "final_report": result.get("final_update_report", ""),
        "structured_report": result.get("structured_report", {}),
        "judgement": result.get("judgement", ""),
        "one_line_summary": result.get("one_line_summary", ""),
        "investment_thesis": result.get("investment_thesis", []),
        "judgement_change_conditions": result.get("judgement_change_conditions", []),
        "monitoring_checklist": result.get("monitoring_checklist", []),
        "ten_line_summary": result.get("ten_line_summary", []),
        "data_limitations": result.get("data_limitations", ""),
    }


def route_by_mode(state: RouterState):
    return state["report_mode"]


def build_router_workflow():
    graph = StateGraph(RouterState)

    graph.add_node("detect_mode_node", detect_mode_node)
    graph.add_node("new_report_node", new_report_node)
    graph.add_node("update_report_node", update_report_node)

    graph.add_edge(START, "detect_mode_node")
    graph.add_conditional_edges(
        "detect_mode_node",
        route_by_mode,
        {
            "new": "new_report_node",
            "update": "update_report_node",
        },
    )
    graph.add_edge("new_report_node", END)
    graph.add_edge("update_report_node", END)

    return graph.compile()
