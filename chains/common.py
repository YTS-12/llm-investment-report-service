import os

from langchain_openai import ChatOpenAI

from utils.env import load_project_env


DOTENV_PATH = load_project_env(override=True)

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
if not OPENAI_API_KEY:
    raise ValueError(
        f"OPENAI_API_KEY가 없습니다. .env 파일을 확인하세요: {DOTENV_PATH}"
    )

llm = ChatOpenAI(
    model="gpt-4o-mini",
    temperature=0.2,
    api_key=OPENAI_API_KEY,
)
