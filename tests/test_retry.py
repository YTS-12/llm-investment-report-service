"""재시도 헬퍼(utils.retry) 단위테스트 (실제 대기 없음: base_delay=0)."""
import pytest

from utils.retry import with_retries


def test_succeeds_first_try():
    calls = {"n": 0}

    @with_retries(max_attempts=3, base_delay=0)
    def f():
        calls["n"] += 1
        return "ok"

    assert f() == "ok"
    assert calls["n"] == 1


def test_retries_then_succeeds():
    calls = {"n": 0}

    @with_retries(max_attempts=3, base_delay=0, retry_on=(ValueError,))
    def f():
        calls["n"] += 1
        if calls["n"] < 3:
            raise ValueError("transient")
        return "ok"

    assert f() == "ok"
    assert calls["n"] == 3


def test_exhausts_then_raises():
    calls = {"n": 0}

    @with_retries(max_attempts=2, base_delay=0, retry_on=(ValueError,))
    def f():
        calls["n"] += 1
        raise ValueError("always")

    with pytest.raises(ValueError):
        f()
    assert calls["n"] == 2  # max_attempts번 시도 후 포기


def test_should_retry_false_stops_immediately():
    calls = {"n": 0}

    @with_retries(
        max_attempts=5,
        base_delay=0,
        retry_on=(Exception,),
        should_retry=lambda exc: False,
    )
    def f():
        calls["n"] += 1
        raise RuntimeError("permanent")

    with pytest.raises(RuntimeError):
        f()
    assert calls["n"] == 1  # should_retry=False → 재시도 없이 즉시 중단


def test_only_retries_listed_exceptions():
    calls = {"n": 0}

    @with_retries(max_attempts=4, base_delay=0, retry_on=(ValueError,))
    def f():
        calls["n"] += 1
        raise KeyError("not in retry_on")

    with pytest.raises(KeyError):
        f()
    assert calls["n"] == 1  # retry_on에 없는 예외는 재시도하지 않음
