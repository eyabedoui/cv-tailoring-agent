"""
Tests for agent/chat_checkpoint.py: queue-based approval checkpoint.
"""

import threading
import time
import pytest

from agent.chat_checkpoint import ChatCheckpoint


def _make_cp(timeout=5):
    reviews = []
    cp = ChatCheckpoint(present_fn=reviews.append, timeout_seconds=timeout)
    return cp, reviews


def _request_in_thread(cp):
    """Run request_approval in a background thread; return a list that holds the result."""
    result = []

    def run():
        result.append(
            cp.request_approval(
                job_title="Engineer",
                company="ACME",
                job_id="job_001",
                master_cv="# Master CV",
                tailored_cv="# Tailored CV",
                cover_letter="Dear Hiring Manager,",
            )
        )

    t = threading.Thread(target=run, daemon=True)
    t.start()
    return t, result


# ---------------------------------------------------------------------------
# Approve and reject
# ---------------------------------------------------------------------------

def test_approve_returns_true():
    cp, _ = _make_cp()
    t, result = _request_in_thread(cp)
    time.sleep(0.05)
    cp.submit_decision(True)
    t.join(timeout=2)
    assert result == [True]
    assert cp.timed_out is False


def test_reject_returns_false():
    cp, _ = _make_cp()
    t, result = _request_in_thread(cp)
    time.sleep(0.05)
    cp.submit_decision(False)
    t.join(timeout=2)
    assert result == [False]
    assert cp.timed_out is False


def test_last_review_text_set():
    cp, reviews = _make_cp(timeout=0.05)
    cp.request_approval(
        job_title="Dev", company="Corp", job_id="job_002",
        master_cv="# CV", tailored_cv="# CV2", cover_letter="Dear ...",
    )
    assert cp.last_review_text is not None
    assert "Dev" in cp.last_review_text
    assert "Corp" in cp.last_review_text


def test_present_fn_called_with_review_text():
    reviews = []
    cp = ChatCheckpoint(present_fn=reviews.append, timeout_seconds=0.05)
    cp.request_approval(
        job_title="Analyst", company="Firm", job_id="job_003",
        master_cv="# CV", tailored_cv="# TCV", cover_letter="Hello,",
    )
    assert len(reviews) == 1
    assert "Analyst" in reviews[0]


# ---------------------------------------------------------------------------
# Timeout
# ---------------------------------------------------------------------------

def test_timeout_returns_false():
    cp, _ = _make_cp(timeout=0.05)
    t, result = _request_in_thread(cp)
    t.join(timeout=2)
    assert result == [False]
    assert cp.timed_out is True


# ---------------------------------------------------------------------------
# TypeError for non-bool
# ---------------------------------------------------------------------------

def test_string_raises_type_error():
    cp, _ = _make_cp()
    with pytest.raises(TypeError):
        cp.submit_decision("yes")


def test_none_raises_type_error():
    cp, _ = _make_cp()
    with pytest.raises(TypeError):
        cp.submit_decision(None)


def test_int_raises_type_error():
    cp, _ = _make_cp()
    with pytest.raises(TypeError):
        cp.submit_decision(1)


def test_zero_raises_type_error():
    cp, _ = _make_cp()
    with pytest.raises(TypeError):
        cp.submit_decision(0)


# ---------------------------------------------------------------------------
# Late decision ignored
# ---------------------------------------------------------------------------

def test_late_decision_ignored_after_timeout():
    cp, _ = _make_cp(timeout=0.05)
    t, result = _request_in_thread(cp)
    t.join(timeout=2)
    assert result == [False]  # Timed out

    # Submit a late decision — should not raise
    cp.submit_decision(True)


def test_late_decision_before_any_request_ignored():
    cp, _ = _make_cp()
    cp.submit_decision(True)  # No pending request; should be a no-op


# ---------------------------------------------------------------------------
# Two consecutive requests don't leak
# ---------------------------------------------------------------------------

def test_two_requests_no_leak():
    cp, _ = _make_cp()

    # First request: reject
    t1, r1 = _request_in_thread(cp)
    time.sleep(0.05)
    cp.submit_decision(False)
    t1.join(timeout=2)
    assert r1 == [False]

    # Second request: approve
    t2, r2 = _request_in_thread(cp)
    time.sleep(0.05)
    cp.submit_decision(True)
    t2.join(timeout=2)
    assert r2 == [True]
