import os

import meilisearch

from utils.env import load_project_env


DOTENV_PATH = load_project_env(override=True)

MEILI_HOST = os.getenv("MEILI_HOST")
MEILI_MASTER_KEY = os.getenv("MEILI_MASTER_KEY")

if not MEILI_HOST:
    raise ValueError(f"MEILI_HOST가 없습니다. .env 파일을 확인하세요: {DOTENV_PATH}")
if not MEILI_MASTER_KEY:
    raise ValueError(
        f"MEILI_MASTER_KEY가 없습니다. .env 파일을 확인하세요: {DOTENV_PATH}"
    )

client = meilisearch.Client(MEILI_HOST, MEILI_MASTER_KEY)
