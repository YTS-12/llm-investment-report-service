import time
from functools import wraps

from utils.logger import logger


class RateLimitError(Exception):
    """외부 API가 429(요청 과다)를 반환했을 때 발생시키는 예외."""


def with_retries(max_attempts=3, base_delay=1.0, retry_on=(Exception,), should_retry=None):
    """일시적 외부 실패를 지수 백오프로 재시도하는 데코레이터.

    - max_attempts: 최대 시도 횟수(첫 시도 포함). 3이면 최대 2번 재시도.
    - base_delay: 첫 재시도 대기(초). 이후 2배씩 증가(지수 백오프).
    - retry_on: 재시도 대상 예외 튜플.
    - should_retry(exc): 주어지면 False일 때 즉시 중단(영구 오류 구분용).

    재시도를 모두 소진하면 마지막 예외를 그대로 올린다.
    """
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            attempt = 1
            while True:
                try:
                    return func(*args, **kwargs)
                except retry_on as exc:
                    if (should_retry is not None and not should_retry(exc)) or attempt >= max_attempts:
                        raise
                    delay = base_delay * (2 ** (attempt - 1))
                    logger.warning(
                        "retry | func=%s | attempt=%d/%d | wait=%.1fs | error=%s",
                        getattr(func, "__name__", "?"),
                        attempt,
                        max_attempts,
                        delay,
                        repr(exc),
                    )
                    if delay > 0:
                        time.sleep(delay)
                    attempt += 1
        return wrapper
    return decorator
