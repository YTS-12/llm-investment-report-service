from services.data_pipeline_service import collect_all_data
from services.company_identity_service import normalize_company_name
from services.macro_interpretation_service import interpret_macro
from services.news_dedup_service import dedupe_news
from services.report_formatter_service import build_fallback_report
from services.router_service import detect_report_mode
from utils.logger import logger
from workflows.router_workflow import build_router_workflow


router_app = build_router_workflow()


def _merge_summary(collected_text: str, override_text: str) -> str:
    collected = (collected_text or "").strip()
    override = (override_text or "").strip()

    if collected and override:
        return f"{collected}\n- 사용자 추가 입력: {override}"
    if override:
        return override
    return collected


def generate_report_with_auto_pipeline(
    company: str,
    sector: str = "반도체",
    news_override: str = "",
    disclosures_override: str = "",
    market_data_override: str = "",
    macro_override: str = "",
) -> dict:
    company = normalize_company_name(company)
    route_info = detect_report_mode(company)
    detected_mode = route_info.get("report_mode", "new")

    try:
        collected = collect_all_data(company)
    except Exception as exc:
        logger.exception(
            "Auto pipeline data collection fallback | company=%s | error=%s",
            company,
            repr(exc),
        )
        collected = {
            "news_docs": [],
            "disclosures_summary": "",
            "disclosure_events": [],
            "market_data_summary": "",
            "macro_summary": "",
            "macro_context": {},
        }

    deduped_news = dedupe_news(collected["news_docs"], stock_name=company)

    collected_news_summary = "\n".join(
        [f"- {item['title']}: {item['summary']}" for item in deduped_news[:5]]
    )

    macro_context = collected.get("macro_context", {}) or {}
    rate_view = macro_context.get("rate_view", "금리는 최근 대체로 안정적이다.")
    fx_view = macro_context.get("fx_view", "환율은 최근 대체로 안정적이다.")
    growth_view = macro_context.get("growth_view", "경기 흐름은 최근 중립적이다.")
    inflation_view = macro_context.get("inflation_view", "물가는 최근 대체로 안정적이다.")

    macro_result = interpret_macro(
        sector=sector,
        rate_view=rate_view,
        fx_view=fx_view,
        growth_view=growth_view,
        inflation_view=inflation_view,
    )

    # 출처 간 우선순위 없음(동등 가중치) — 수집 요약과 사용자 추가 입력을 병합만 한다.
    news_summary = _merge_summary(collected_news_summary, news_override)
    disclosures_summary = _merge_summary(
        collected.get("disclosures_summary", ""),
        disclosures_override,
    )
    market_data_summary = _merge_summary(
        collected.get("market_data_summary", ""),
        market_data_override,
    )
    macro_summary = _merge_summary(
        "\n".join(
            part
            for part in [
                collected.get("macro_summary", ""),
                f"- 자동 거시 해석: {macro_result['macro_summary']}",
            ]
            if (part or "").strip()
        ),
        macro_override,
    )

    try:
        workflow_result = router_app.invoke(
            {
                "company": company,
                "news": news_summary,
                "disclosures": disclosures_summary,
                "market_data": market_data_summary,
                "macro": macro_summary,
            }
        )
        final_report = workflow_result.get("final_report", "")
        report_mode = workflow_result.get("report_mode", "") or detected_mode
    except Exception as exc:
        logger.exception(
            "Auto pipeline workflow fallback | company=%s | error=%s",
            company,
            repr(exc),
        )
        final_report = build_fallback_report(
            company=company,
            news=news_summary,
            disclosures=disclosures_summary,
            market_data=market_data_summary,
            macro=macro_summary,
            reason=str(exc),
        )
        report_mode = detected_mode
        workflow_result = {}

    response = {
        "company": company,
        "deduped_news_count": len(deduped_news),
        "macro_result": macro_result,
        "macro_views": {
            "rate_view": rate_view,
            "fx_view": fx_view,
            "growth_view": growth_view,
            "inflation_view": inflation_view,
        },
        "news_summary": news_summary,
        "disclosures_summary": disclosures_summary,
        "disclosure_events": collected.get("disclosure_events", []),
        "market_data_summary": market_data_summary,
        "macro_summary": macro_summary,
        "final_report": final_report,
        "report_mode": report_mode,
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
        if field in workflow_result:
            response[field] = workflow_result.get(field)

    return response
