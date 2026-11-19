"""
Tests for agent/tools/throttle.py — all offline, no real sleeps.

time.monotonic and time.sleep are monkeypatched to control timing without
actually waiting.
"""
import pytest

import agent.tools.throttle as _throttle_mod


@pytest.fixture(autouse=True)
def reset_throttle():
    """Clear throttle state before and after every test."""
    _throttle_mod._reset()
    yield
    _throttle_mod._reset()


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_clock(values):
    """Return a fake monotonic clock that pops values from a list."""
    it = iter(values)

    def _clock():
        return next(it)

    return _clock


# ---------------------------------------------------------------------------
# First call never sleeps
# ---------------------------------------------------------------------------

def test_first_call_no_sleep(monkeypatch):
    sleep_calls = []
    monkeypatch.setattr("time.sleep", lambda s: sleep_calls.append(s))
    monkeypatch.setattr(_throttle_mod, "_clock", _make_clock([100.0, 100.0]))
    _throttle_mod.throttle("example.com", seconds=3.0)
    assert sleep_calls == []


# ---------------------------------------------------------------------------
# Second call too soon: sleeps
# ---------------------------------------------------------------------------

def test_second_call_too_soon_sleeps(monkeypatch):
    sleep_calls = []
    monkeypatch.setattr("time.sleep", lambda s: sleep_calls.append(s))
    # First call: now=100, then record=100; second call: now=101 (only 1s elapsed)
    monkeypatch.setattr(_throttle_mod, "_clock", _make_clock([100.0, 100.0, 101.0, 102.0]))
    _throttle_mod.throttle("example.com", seconds=3.0)
    _throttle_mod.throttle("example.com", seconds=3.0)
    assert len(sleep_calls) == 1
    assert sleep_calls[0] == pytest.approx(2.0, abs=0.01)


# ---------------------------------------------------------------------------
# Second call after full gap: no sleep
# ---------------------------------------------------------------------------

def test_second_call_after_gap_no_sleep(monkeypatch):
    sleep_calls = []
    monkeypatch.setattr("time.sleep", lambda s: sleep_calls.append(s))
    # 5 seconds elapsed since last call — gap=3.0 satisfied
    monkeypatch.setattr(_throttle_mod, "_clock", _make_clock([100.0, 100.0, 105.0, 105.0]))
    _throttle_mod.throttle("example.com", seconds=3.0)
    _throttle_mod.throttle("example.com", seconds=3.0)
    assert sleep_calls == []


# ---------------------------------------------------------------------------
# Different hosts are independent
# ---------------------------------------------------------------------------

def test_different_hosts_independent(monkeypatch):
    sleep_calls = []
    monkeypatch.setattr("time.sleep", lambda s: sleep_calls.append(s))
    # host_a and host_b both called at t=100; each is first call → no sleep
    monkeypatch.setattr(_throttle_mod, "_clock", _make_clock([100.0, 100.0, 100.5, 100.5]))
    _throttle_mod.throttle("host_a.com", seconds=3.0)
    _throttle_mod.throttle("host_b.com", seconds=3.0)  # different host — no sleep
    assert sleep_calls == []


# ---------------------------------------------------------------------------
# Custom seconds parameter
# ---------------------------------------------------------------------------

def test_custom_seconds_honoured(monkeypatch):
    sleep_calls = []
    monkeypatch.setattr("time.sleep", lambda s: sleep_calls.append(s))
    monkeypatch.setattr(_throttle_mod, "_clock", _make_clock([0.0, 0.0, 0.5, 0.5]))
    _throttle_mod.throttle("x.com", seconds=2.0)
    _throttle_mod.throttle("x.com", seconds=2.0)
    assert sleep_calls == [pytest.approx(1.5, abs=0.01)]


# ---------------------------------------------------------------------------
# _reset clears state
# ---------------------------------------------------------------------------

def test_reset_clears_last_call(monkeypatch):
    sleep_calls = []
    monkeypatch.setattr("time.sleep", lambda s: sleep_calls.append(s))
    monkeypatch.setattr(_throttle_mod, "_clock", _make_clock([0.0, 0.0, 1.0, 1.0]))
    _throttle_mod.throttle("y.com", seconds=3.0)
    _throttle_mod._reset()
    # After reset, next call is treated as first call → no sleep
    _throttle_mod.throttle("y.com", seconds=3.0)
    assert sleep_calls == []
