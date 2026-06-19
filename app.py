from fastapi import FastAPI, Request
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
import time

from services.config_service import get_config_status
from services.company_identity_service import normalize_company_name
from services.memory_service import load_messages, save_message
from utils.error_handler import (
    AppConfigError,
    AppDataError,
    app_config_error_handler,
    app_data_error_handler,
    generic_exception_handler,
)
from utils.logger import logger


app = FastAPI(title="Investment Report Service")

app.mount("/static", StaticFiles(directory="frontend"), name="static")

app.add_exception_handler(AppDataError, app_data_error_handler)
app.add_exception_handler(AppConfigError, app_config_error_handler)
app.add_exception_handler(Exception, generic_exception_handler)


@app.middleware("http")
async def log_requests(request: Request, call_next):
    start = time.time()
    response = await call_next(request)
    duration = time.time() - start

    logger.info(
        f"HTTP {request.method} {request.url.path} "
        f"status={response.status_code} duration={duration:.3f}s"
    )
    return response


class ReportRequest(BaseModel):
    session_id: str
    company: str
    sector: str = "반도체"
    news: str = ""
    disclosures: str = ""
    market_data: str = ""
    macro: str = ""


class CompareRequest(BaseModel):
    company_a: str
    sector_a: str = "반도체"
    company_b: str
    sector_b: str = "반도체"


class FollowupRequest(BaseModel):
    session_id: str
    company: str
    question: str


def ensure_service_ready():
    status = get_config_status()
    if not status["ready"]:
        raise AppConfigError(status["message"])
    return status


@app.get("/health")
def health():
    status = get_config_status()
    return {"status": "ok", "config_ready": status["ready"]}


@app.get("/config-status")
def config_status():
    return get_config_status(force_refresh=True)


@app.get("/")
def root():
    return FileResponse("frontend/index.html")


@app.get("/memory/{session_id}")
def get_memory(session_id: str):
    return {"session_id": session_id, "messages": load_messages(session_id)}


@app.get("/reports")
def get_reports(company: str = "", session_id: str = "", limit: int = 10):
    ensure_service_ready()
    from services.report_retrieval_service import search_reports

    company = normalize_company_name(company) if company else ""
    return {
        "items": search_reports(company=company, session_id=session_id, limit=limit)
    }


@app.post("/generate-report")
def generate_report(payload: ReportRequest):
    ensure_service_ready()
    from services.orchestrator_service import generate_report_with_auto_pipeline
    from services.report_store_service import save_report_to_index

    if not payload.company.strip():
        raise AppDataError("company 값이 비어 있습니다.")
    company = normalize_company_name(payload.company)

    save_message(payload.session_id, "user", f"{company} 투자 보고서 생성 요청")

    result = generate_report_with_auto_pipeline(
        company=company,
        sector=payload.sector,
        news_override=payload.news,
        disclosures_override=payload.disclosures,
        market_data_override=payload.market_data,
        macro_override=payload.macro,
    )

    save_message(payload.session_id, "assistant", result.get("final_report", ""))
    save_report_to_index(payload.session_id, result)

    return result


@app.post("/compare-report")
def compare_report(payload: CompareRequest):
    ensure_service_ready()
    from services.compare_service import generate_compare_report

    if not payload.company_a.strip() or not payload.company_b.strip():
        raise AppDataError("비교할 두 회사명을 모두 입력해야 합니다.")
    company_a = normalize_company_name(payload.company_a)
    company_b = normalize_company_name(payload.company_b)

    return generate_compare_report(
        company_a=company_a,
        sector_a=payload.sector_a,
        company_b=company_b,
        sector_b=payload.sector_b,
    )


@app.post("/chat-followup")
def chat_followup(payload: FollowupRequest):
    ensure_service_ready()
    from services.chat_service import answer_followup

    if not payload.company.strip():
        raise AppDataError("company 값이 비어 있습니다.")
    if not payload.question.strip():
        raise AppDataError("question 값이 비어 있습니다.")
    company = normalize_company_name(payload.company)

    save_message(payload.session_id, "user", payload.question)
    result = answer_followup(
        session_id=payload.session_id,
        company=company,
        question=payload.question,
    )
    save_message(payload.session_id, "assistant", result.get("answer", ""))
    return result
