import os
import time
from typing import Callable

import meilisearch
import requests

from utils.env import load_project_env


DOTENV_PATH = load_project_env(override=False)

REQUEST_TIMEOUT = 5
CACHE_TTL_SECONDS = 180

_cache: dict = {"checked_at": 0.0, "status": None}


def _dart_key() -> str:
    return os.getenv("DART_API_KEY") or os.getenv("OPEN_DART_API_KEY") or ""


def _has_required_values() -> dict[str, bool]:
    return {
        "OPENAI_API_KEY": bool(os.getenv("OPENAI_API_KEY")),
        "NAVER_CLIENT_ID": bool(os.getenv("NAVER_CLIENT_ID")),
        "NAVER_CLIENT_SECRET": bool(os.getenv("NAVER_CLIENT_SECRET")),
        "ECOS_API_KEY": bool(os.getenv("ECOS_API_KEY")),
        "DART_API_KEY": bool(_dart_key()),
        "MEILI_HOST": bool(os.getenv("MEILI_HOST")),
        "MEILI_MASTER_KEY": bool(os.getenv("MEILI_MASTER_KEY")),
    }


def _probe_openai() -> tuple[bool, str]:
    response = requests.get(
        "https://api.openai.com/v1/models",
        headers={"Authorization": f"Bearer {os.getenv('OPENAI_API_KEY', '')}"},
        timeout=REQUEST_TIMEOUT,
    )
    if response.status_code == 200:
        return True, "ok"
    return False, f"http_{response.status_code}"


def _probe_naver_news() -> tuple[bool, str]:
    response = requests.get(
        "https://openapi.naver.com/v1/search/news.json",
        headers={
            "X-Naver-Client-Id": os.getenv("NAVER_CLIENT_ID", ""),
            "X-Naver-Client-Secret": os.getenv("NAVER_CLIENT_SECRET", ""),
        },
        params={"query": "삼성전자", "display": 1, "sort": "sim"},
        timeout=REQUEST_TIMEOUT,
    )
    if response.status_code == 200:
        return True, "ok"
    return False, f"http_{response.status_code}"


def _probe_ecos() -> tuple[bool, str]:
    response = requests.get(
        (
            "https://ecos.bok.or.kr/api/StatisticTableList/"
            f"{os.getenv('ECOS_API_KEY', '')}/json/kr/1/1/"
        ),
        timeout=REQUEST_TIMEOUT,
    )
    if response.status_code != 200:
        return False, f"http_{response.status_code}"

    payload = response.json()
    if "StatisticTableList" in payload:
        return True, "ok"
    if "RESULT" in payload:
        return False, str(payload["RESULT"].get("CODE", "ecos_error"))
    return False, "unexpected_payload"


def _probe_dart() -> tuple[bool, str]:
    response = requests.get(
        "https://opendart.fss.or.kr/api/company.json",
        params={"crtfc_key": _dart_key(), "corp_code": "00000000"},
        timeout=REQUEST_TIMEOUT,
    )
    if response.status_code != 200:
        return False, f"http_{response.status_code}"

    payload = response.json()
    status = str(payload.get("status", ""))
    if status == "000":
        return True, "ok"
    if status in {"013", "020"}:
        return True, status
    return False, status or "unexpected_payload"


def _probe_meilisearch() -> tuple[bool, str]:
    client = meilisearch.Client(
        os.getenv("MEILI_HOST", ""),
        os.getenv("MEILI_MASTER_KEY", ""),
    )
    response = client.get_indexes({"limit": 1})
    if isinstance(response, dict) and "results" in response:
        return True, "ok"
    return False, "unexpected_payload"


def _run_probe(probe: Callable[[], tuple[bool, str]]) -> tuple[bool, str]:
    try:
        return probe()
    except requests.RequestException as exc:
        return False, type(exc).__name__
    except ValueError:
        return False, "invalid_json"
    except Exception as exc:
        return False, type(exc).__name__


def _build_status() -> dict:
    required = _has_required_values()
    missing = [name for name, ok in required.items() if not ok]

    checks = {
        "OPENAI_API_KEY": (False, "missing"),
        "NAVER_CLIENT_ID": (False, "missing"),
        "ECOS_API_KEY": (False, "missing"),
        "DART_API_KEY": (False, "missing"),
        "MEILI_HOST": (False, "missing"),
    }

    if not missing:
        checks = {
            "OPENAI_API_KEY": _run_probe(_probe_openai),
            "NAVER_CLIENT_ID": _run_probe(_probe_naver_news),
            "ECOS_API_KEY": _run_probe(_probe_ecos),
            "DART_API_KEY": _run_probe(_probe_dart),
            "MEILI_HOST": _run_probe(_probe_meilisearch),
        }

    failed_checks = [name for name, result in checks.items() if not result[0]]
    ready = not missing and not failed_checks

    if ready:
        message = "서비스 실행에 필요한 설정과 외부 연결이 모두 준비되었습니다."
    elif missing:
        message = (
            "서비스 실행에 필요한 설정이 완료되지 않았습니다. "
            f"누락 항목: {', '.join(missing)}"
        )
    else:
        message = (
            "설정은 존재하지만 일부 외부 서비스 연결을 확인하지 못했습니다. "
            f"실패 항목: {', '.join(failed_checks)}"
        )

    return {
        "ready": ready,
        "missing": missing,
        "failed_checks": failed_checks,
        "check_details": {name: detail for name, (_, detail) in checks.items()},
        "message": message,
    }


def get_config_status(force_refresh: bool = False) -> dict:
    now = time.time()
    cached = _cache.get("status")
    if (
        not force_refresh
        and cached is not None
        and now - _cache.get("checked_at", 0.0) < CACHE_TTL_SECONDS
    ):
        return cached

    status = _build_status()
    _cache["status"] = status
    _cache["checked_at"] = now
    return status
