# data_collectors/naver_news_api.py
import os

import requests

from utils.env import load_project_env
from utils.retry import with_retries


DOTENV_PATH = load_project_env(override=True)

NAVER_CLIENT_ID = os.getenv("NAVER_CLIENT_ID")
NAVER_CLIENT_SECRET = os.getenv("NAVER_CLIENT_SECRET")


@with_retries(
    max_attempts=3,
    base_delay=1.0,
    retry_on=(requests.ConnectionError, requests.Timeout),
)
def search_news(query: str, display: int = 10, sort: str = "date"):
    url = "https://openapi.naver.com/v1/search/news.json"
    headers = {
        "X-Naver-Client-Id": NAVER_CLIENT_ID,
        "X-Naver-Client-Secret": NAVER_CLIENT_SECRET,
    }
    params = {
        "query": query,
        "display": display,
        "sort": sort,
    }
    res = requests.get(url, headers=headers, params=params, timeout=20)
    res.raise_for_status()
    return res.json()
