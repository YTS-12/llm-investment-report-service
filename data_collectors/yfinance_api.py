import requests

from utils.logger import logger
from utils.retry import RateLimitError, with_retries


RANGE_TO_INTERVAL = {
    "5d": "1d",
    "1mo": "1d",
    "3mo": "1d",
    "6mo": "1d",
    "1y": "1wk",
}


@with_retries(
    max_attempts=3,
    base_delay=1.0,
    retry_on=(RateLimitError, requests.ConnectionError, requests.Timeout),
)
def _yahoo_get(url: str, params: dict) -> dict:
    response = requests.get(url, params=params, timeout=20)
    if response.status_code == 429:
        # 429(요청 과다)는 일시적이므로 재시도 대상으로 올린다.
        raise RateLimitError(f"429 Too Many Requests | url={url}")
    response.raise_for_status()
    return response.json()


def get_price_history(ticker: str, period: str = "6mo") -> list[dict]:
    interval = RANGE_TO_INTERVAL.get(period, "1d")
    try:
        payload = _yahoo_get(
            f"https://query1.finance.yahoo.com/v8/finance/chart/{ticker}",
            {"range": period, "interval": interval},
        )
    except Exception as exc:
        logger.warning(
            "Yahoo price history failed after retries | ticker=%s | error=%s",
            ticker,
            repr(exc),
        )
        return []

    result = payload.get("chart", {}).get("result", [])
    if not result:
        return []

    chart = result[0]
    timestamps = chart.get("timestamp", [])
    quotes = chart.get("indicators", {}).get("quote", [{}])[0]

    rows = []
    for index, ts in enumerate(timestamps):
        rows.append(
            {
                "Date": ts,
                "Open": _safe_pick(quotes.get("open", []), index),
                "High": _safe_pick(quotes.get("high", []), index),
                "Low": _safe_pick(quotes.get("low", []), index),
                "Close": _safe_pick(quotes.get("close", []), index),
                "Volume": _safe_pick(quotes.get("volume", []), index),
            }
        )
    return rows


def get_basic_info(ticker: str) -> dict:
    try:
        payload = _yahoo_get(
            "https://query1.finance.yahoo.com/v7/finance/quote",
            {"symbols": ticker},
        )
    except Exception as exc:
        logger.warning(
            "Yahoo basic info failed after retries | ticker=%s | error=%s",
            ticker,
            repr(exc),
        )
        return {}

    items = payload.get("quoteResponse", {}).get("result", [])
    return items[0] if items else {}


def _safe_pick(values: list, index: int):
    if index >= len(values):
        return None
    return values[index]
