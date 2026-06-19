"""대화기록 저장(SQLite) 단위테스트 — 임시 DB 사용."""


def test_memory_roundtrip(tmp_path, monkeypatch):
    import services.memory_service as mem

    monkeypatch.setattr(mem, "MEMORY_DB", tmp_path / "test_mem.db")

    mem.save_message("s1", "user", "안녕")
    mem.save_message("s1", "assistant", "반가워요")
    mem.save_message("s2", "user", "다른 세션")

    assert mem.load_messages("s1") == [
        {"role": "user", "content": "안녕"},
        {"role": "assistant", "content": "반가워요"},
    ]
    assert mem.load_messages("s2") == [{"role": "user", "content": "다른 세션"}]
    assert mem.load_messages("없는세션") == []


def test_append_is_incremental(tmp_path, monkeypatch):
    # 저장이 누적되는지(이전 기록을 덮어쓰지 않는지) 확인
    import services.memory_service as mem

    monkeypatch.setattr(mem, "MEMORY_DB", tmp_path / "test_mem2.db")

    for i in range(5):
        mem.save_message("sess", "user", f"메시지{i}")

    msgs = mem.load_messages("sess")
    assert len(msgs) == 5
    assert [m["content"] for m in msgs] == [f"메시지{i}" for i in range(5)]
