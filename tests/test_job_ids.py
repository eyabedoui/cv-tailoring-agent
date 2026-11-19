"""
Tests for agent/job_ids.py — ID generation, normalisation, validation.
"""

import pytest

from agent.job_ids import is_valid_job_id, make_job_id


# ---------------------------------------------------------------------------
# make_job_id — determinism and format
# ---------------------------------------------------------------------------

def test_make_job_id_format():
    jid = make_job_id("tanitjobs", "https://www.tanitjobs.com/jobs/123")
    assert jid.startswith("tanitjobs-")
    hex_part = jid[len("tanitjobs-"):]
    assert len(hex_part) == 8
    assert all(c in "0123456789abcdef" for c in hex_part)


def test_make_job_id_deterministic():
    url = "https://www.tanitjobs.com/jobs/456"
    id1 = make_job_id("tanitjobs", url)
    id2 = make_job_id("tanitjobs", url)
    assert id1 == id2


def test_make_job_id_different_urls_different_ids():
    id1 = make_job_id("tanitjobs", "https://www.tanitjobs.com/jobs/1")
    id2 = make_job_id("tanitjobs", "https://www.tanitjobs.com/jobs/2")
    assert id1 != id2


def test_make_job_id_different_sites_different_ids():
    url = "https://www.example.com/jobs/1"
    id1 = make_job_id("tanitjobs", url)
    id2 = make_job_id("keejob", url)
    assert id1 != id2


# ---------------------------------------------------------------------------
# make_job_id — URL normalisation
# ---------------------------------------------------------------------------

def test_normalise_strips_fragment():
    id1 = make_job_id("tanitjobs", "https://www.tanitjobs.com/job/1#section")
    id2 = make_job_id("tanitjobs", "https://www.tanitjobs.com/job/1")
    assert id1 == id2


def test_normalise_strips_utm_params():
    id1 = make_job_id("tanitjobs", "https://www.tanitjobs.com/job/1?utm_source=google")
    id2 = make_job_id("tanitjobs", "https://www.tanitjobs.com/job/1")
    assert id1 == id2


def test_normalise_strips_multiple_utm_params():
    id1 = make_job_id("tanitjobs", "https://www.tanitjobs.com/job/1?utm_source=x&utm_medium=y")
    id2 = make_job_id("tanitjobs", "https://www.tanitjobs.com/job/1")
    assert id1 == id2


def test_normalise_keeps_non_utm_params():
    id1 = make_job_id("tanitjobs", "https://www.tanitjobs.com/job/1?page=2")
    id2 = make_job_id("tanitjobs", "https://www.tanitjobs.com/job/1")
    assert id1 != id2


def test_normalise_strips_trailing_slash():
    id1 = make_job_id("tanitjobs", "https://www.tanitjobs.com/job/1/")
    id2 = make_job_id("tanitjobs", "https://www.tanitjobs.com/job/1")
    assert id1 == id2


def test_normalise_lowercase_scheme_host():
    id1 = make_job_id("tanitjobs", "HTTPS://WWW.TANITJOBS.COM/job/1")
    id2 = make_job_id("tanitjobs", "https://www.tanitjobs.com/job/1")
    assert id1 == id2


# ---------------------------------------------------------------------------
# is_valid_job_id
# ---------------------------------------------------------------------------

def test_valid_sandbox_id():
    assert is_valid_job_id("job_001") is True


def test_valid_sandbox_id_all_digits():
    assert is_valid_job_id("job_999") is True


def test_valid_site_id():
    assert is_valid_job_id("tanitjobs-a1b2c3d4") is True


def test_valid_site_id_keejob():
    assert is_valid_job_id("keejob-00000000") is True


def test_invalid_sandbox_id_one_digit():
    assert is_valid_job_id("job_1") is False


def test_invalid_sandbox_id_four_digits():
    assert is_valid_job_id("job_1234") is False


def test_invalid_no_prefix():
    assert is_valid_job_id("001") is False


def test_invalid_site_id_too_short_hex():
    assert is_valid_job_id("tanitjobs-a1b2c3") is False  # 6 chars, need 8


def test_invalid_site_id_too_long_hex():
    assert is_valid_job_id("tanitjobs-a1b2c3d4e5") is False  # 10 chars


def test_invalid_empty_string():
    assert is_valid_job_id("") is False


def test_make_job_id_result_is_valid():
    jid = make_job_id("tanitjobs", "https://www.tanitjobs.com/jobs/42")
    assert is_valid_job_id(jid) is True
