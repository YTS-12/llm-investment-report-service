import sqlite3
from contextlib import closing
from pathlib import Path
from typing import List, Dict, Any

# 대화기록은 세션별 JSON 전체 재작성(동시성·내구성 취약) 대신 SQLite에 누적한다.
MEMORY_DB = Path(__file__).resolve().parents[1] / "memory_store.db"


def _connect() -> sqlite3.Connection:
    MEMORY_DB.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(MEMORY_DB)
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS messages (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            session_id TEXT NOT NULL,
            role TEXT NOT NULL,
            content TEXT NOT NULL,
            created_at TEXT NOT NULL DEFAULT (datetime('now'))
        )
        """
    )
    conn.execute("CREATE INDEX IF NOT EXISTS idx_messages_session ON messages(session_id)")
    conn.commit()
    return conn


def save_message(session_id: str, role: str, content: str) -> None:
    """대화 1건 추가. 전체 파일 재작성 없이 INSERT만 수행한다."""
    with closing(_connect()) as conn:
        conn.execute(
            "INSERT INTO messages (session_id, role, content) VALUES (?, ?, ?)",
            (session_id, role, content),
        )
        conn.commit()


def load_messages(session_id: str) -> List[Dict[str, Any]]:
    with closing(_connect()) as conn:
        rows = conn.execute(
            "SELECT role, content FROM messages WHERE session_id = ? ORDER BY id",
            (session_id,),
        ).fetchall()
    return [{"role": role, "content": content} for role, content in rows]
