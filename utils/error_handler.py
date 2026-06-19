from fastapi import Request
from fastapi.responses import JSONResponse

from utils.logger import logger


class AppDataError(Exception):
    def __init__(self, message: str):
        self.message = message
        super().__init__(message)


class AppConfigError(Exception):
    def __init__(self, message: str):
        self.message = message
        super().__init__(message)


async def app_data_error_handler(request: Request, exc: AppDataError):
    logger.error(f"AppDataError | path={request.url.path} | message={exc.message}")
    return JSONResponse(status_code=400, content={"error": exc.message})


async def app_config_error_handler(request: Request, exc: AppConfigError):
    logger.error(f"AppConfigError | path={request.url.path} | message={exc.message}")
    return JSONResponse(status_code=503, content={"error": exc.message})


async def generic_exception_handler(request: Request, exc: Exception):
    logger.exception(f"UnhandledError | path={request.url.path} | error={repr(exc)}")
    return JSONResponse(
        status_code=500,
        content={"error": "서버 내부 오류가 발생했습니다."},
    )
