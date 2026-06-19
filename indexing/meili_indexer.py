from typing import List, Dict, Any

from meilisearch.errors import MeilisearchApiError

from indexing.meili_client import client
from indexing.meili_schema import INDEX_CONFIG

def ensure_index(index_name: str):
    config = INDEX_CONFIG[index_name]
    index = client.index(index_name)

    # 인덱스 생성 시도
    try:
        task = client.create_index(index_name, {"primaryKey": config["primary_key"]})
        task_uid = task.task_uid if hasattr(task, "task_uid") else task["taskUid"]
        client.wait_for_task(task_uid)
    except Exception:
        # 이미 존재하면 그냥 진행
        pass

    index = client.index(index_name)

    # 필터 설정
    task = index.update_filterable_attributes(config["filterable_attributes"])
    task_uid = task.task_uid if hasattr(task, "task_uid") else task["taskUid"]
    client.wait_for_task(task_uid)

    # 검색 필드 설정
    task = index.update_searchable_attributes(config["searchable_attributes"])
    task_uid = task.task_uid if hasattr(task, "task_uid") else task["taskUid"]
    client.wait_for_task(task_uid)

    return index


def add_documents(index_name: str, documents: List[Dict[str, Any]]):
    config = INDEX_CONFIG[index_name]
    index = ensure_index(index_name)

    task = index.add_documents(documents, primary_key=config["primary_key"])
    task_uid = task.task_uid if hasattr(task, "task_uid") else task["taskUid"]
    result = client.wait_for_task(task_uid)
    return result


def search_documents(index_name: str, query: str, limit: int = 5):
    index = client.index(index_name)
    try:
        return index.search(query, {"limit": limit})
    except MeilisearchApiError as exc:
        # 최초 실행 등으로 아직 인덱스가 생성되지 않은 경우는
        # '검색 결과 없음'으로 처리한다(첫 보고서 저장 시 인덱스가 생성됨).
        if getattr(exc, "code", "") == "index_not_found" or "index_not_found" in str(exc):
            return {"hits": []}
        raise
