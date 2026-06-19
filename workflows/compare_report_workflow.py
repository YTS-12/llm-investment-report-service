from typing import TypedDict
from langgraph.graph import StateGraph, START, END

from chains.compare_fact_chain import compare_fact_chain
from chains.compare_analysis_chain import compare_analysis_chain
from chains.compare_report_chain import compare_report_chain


class CompareState(TypedDict, total=False):
    company_a: str
    company_b: str
    news_a: str
    disclosures_a: str
    market_data_a: str
    macro_a: str
    news_b: str
    disclosures_b: str
    market_data_b: str
    macro_b: str
    fact_summary: str
    analysis_summary: str
    final_report: str


def compare_fact_node(state: CompareState):
    result = compare_fact_chain.invoke(state)
    return {"fact_summary": result}


def compare_analysis_node(state: CompareState):
    result = compare_analysis_chain.invoke({
        "company_a": state["company_a"],
        "company_b": state["company_b"],
        "fact_summary": state["fact_summary"],
    })
    return {"analysis_summary": result}


def compare_report_node(state: CompareState):
    result = compare_report_chain.invoke({
        "company_a": state["company_a"],
        "company_b": state["company_b"],
        "fact_summary": state["fact_summary"],
        "analysis_summary": state["analysis_summary"],
    })
    return {"final_report": result}


def build_compare_workflow():
    graph = StateGraph(CompareState)
    graph.add_node("compare_fact_node", compare_fact_node)
    graph.add_node("compare_analysis_node", compare_analysis_node)
    graph.add_node("compare_report_node", compare_report_node)

    graph.add_edge(START, "compare_fact_node")
    graph.add_edge("compare_fact_node", "compare_analysis_node")
    graph.add_edge("compare_analysis_node", "compare_report_node")
    graph.add_edge("compare_report_node", END)
    return graph.compile()