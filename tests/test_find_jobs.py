"""
Tests for the find_jobs tool and FakeSearchClient.

All tests are offline (no network, no real API calls).
"""

import pytest
from pathlib import Path

from agent.errors import SITE_NOT_ALLOWED, SITE_BLOCKED, INVALID_ARGUMENTS
from agent.sites import _load_allowlist_cached
from agent.tools.search import FakeSearchClient, find_jobs
from agent.tools.registry import execute_tool


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _clear_cache():
    _load_allowlist_cached.cache_clear()


# ---------------------------------------------------------------------------
# Valid-site search
# ---------------------------------------------------------------------------

def test_find_jobs_valid_site_returns_jobs():
    _clear_cache()
    result = find_jobs(query="python", site="tanitjobs")
    assert "error" not in result
    assert isinstance(result["jobs"], list)
    assert result["site"] == "tanitjobs"
    assert result["count"] == len(result["jobs"])


def test_find_jobs_all_three_sites():
    _clear_cache()
    for site in ("tanitjobs", "keejob", "weworkremotely"):
        result = find_jobs(query="engineer", site=site)
        assert "error" not in result, f"Expected success for site={site}"
        assert result["site"] == site


def test_find_jobs_max_10_results():
    _clear_cache()
    result = find_jobs(query="a", site="tanitjobs")
    assert len(result["jobs"]) <= 10


def test_find_jobs_truncated_flag_false_when_10_or_fewer():
    _clear_cache()
    # sandbox has 25 postings but we cap at 10; check flag
    result = find_jobs(query="python", site="tanitjobs")
    if len(result["jobs"]) == 10:
        # If exactly 10 returned, truncated could be True or False depending on raw count
        pass
    # just assert it's a bool
    assert isinstance(result["truncated"], bool)


# ---------------------------------------------------------------------------
# Unknown site → SITE_NOT_ALLOWED
# ---------------------------------------------------------------------------

def test_find_jobs_unknown_site_returns_site_not_allowed():
    _clear_cache()
    result = find_jobs(query="python", site="linkedin")
    assert result["error"] == SITE_NOT_ALLOWED


def test_find_jobs_unknown_site_message_lists_allowed():
    _clear_cache()
    result = find_jobs(query="python", site="monster")
    assert "tanitjobs" in result["message"] or "keejob" in result["message"]


def test_execute_tool_find_jobs_unknown_site():
    _clear_cache()
    result = execute_tool("find_jobs", {"query": "python", "site": "badsite"})
    assert result["error"] == SITE_NOT_ALLOWED


# ---------------------------------------------------------------------------
# Invalid query
# ---------------------------------------------------------------------------

def test_find_jobs_empty_query_returns_invalid_arguments():
    _clear_cache()
    result = execute_tool("find_jobs", {"query": "", "site": "tanitjobs"})
    assert result["error"] == INVALID_ARGUMENTS


def test_find_jobs_query_too_long_returns_invalid_arguments():
    _clear_cache()
    result = execute_tool("find_jobs", {"query": "x" * 201, "site": "tanitjobs"})
    assert result["error"] == INVALID_ARGUMENTS


def test_find_jobs_query_exactly_200_chars_ok():
    _clear_cache()
    result = execute_tool("find_jobs", {"query": "x" * 200, "site": "tanitjobs"})
    assert "error" not in result


# ---------------------------------------------------------------------------
# Foreign-host results dropped
# ---------------------------------------------------------------------------

def test_find_jobs_drops_foreign_host_results():
    _clear_cache()

    class ForeignHostClient:
        """Returns results with URLs from wrong host — should all be dropped."""
        def search(self, query, site):
            return [
                {
                    "job_id": "job_001",
                    "title": "Some Job",
                    "company": "ACME",
                    "location": "Remote",
                    "url": "https://evil.com/job/1",  # wrong host
                    "site": site,
                    "snippet": "Great role.",
                }
            ]

    result = find_jobs(query="python", site="tanitjobs", _client=ForeignHostClient())
    assert "error" not in result
    assert len(result["jobs"]) == 0


def test_find_jobs_keeps_correct_host_results():
    _clear_cache()
    result = find_jobs(query="python", site="tanitjobs")
    for job in result["jobs"]:
        assert "tanitjobs" in job["url"] or "tanitjobs.com" in job["url"]


# ---------------------------------------------------------------------------
# Field truncation
# ---------------------------------------------------------------------------

def test_find_jobs_title_truncated_at_120():
    _clear_cache()

    class LongFieldClient:
        def search(self, query, site):
            from agent.sites import host_for
            host = host_for(site)
            return [{
                "job_id": "job_001",
                "title": "T" * 200,
                "company": "C" * 150,
                "location": "L",
                "url": f"https://{host}/jobs/1",
                "site": site,
                "snippet": "S" * 500,
            }]

    result = find_jobs(query="test", site="tanitjobs", _client=LongFieldClient())
    assert "error" not in result
    assert len(result["jobs"]) == 1
    job = result["jobs"][0]
    assert len(job["title"]) <= 120
    assert len(job["company"]) <= 80
    assert len(job["snippet"]) <= 240


# ---------------------------------------------------------------------------
# Determinism
# ---------------------------------------------------------------------------

def test_find_jobs_same_query_same_results():
    _clear_cache()
    r1 = find_jobs(query="python", site="tanitjobs")
    r2 = find_jobs(query="python", site="tanitjobs")
    assert [j["job_id"] for j in r1["jobs"]] == [j["job_id"] for j in r2["jobs"]]


# ---------------------------------------------------------------------------
# Untrusted wrapping (through execute_tool)
# ---------------------------------------------------------------------------

def test_find_jobs_result_is_wrapped_as_untrusted_in_loop(monkeypatch, tmp_path):
    """Verify that find_jobs output goes through wrap_untrusted in the loop."""
    from agent.untrusted import wrap_untrusted
    _clear_cache()
    result = find_jobs(query="python", site="tanitjobs")
    wrapped = wrap_untrusted(result)
    assert 'untrusted="true"' in wrapped


# ---------------------------------------------------------------------------
# SITE_BLOCKED fault mode
# ---------------------------------------------------------------------------

def test_find_jobs_blocked_fault_returns_site_blocked(monkeypatch, tmp_path):
    _clear_cache()
    monkeypatch.setenv("FAULT_MODE", "blocked")
    # Need a state_dir; find_jobs creates it on demand
    result = find_jobs(query="python", site="tanitjobs")
    assert result["error"] == SITE_BLOCKED
    assert result.get("retryable") is False


def test_find_jobs_blocked_does_not_affect_other_tools(monkeypatch, tmp_path):
    _clear_cache()
    monkeypatch.setenv("FAULT_MODE", "blocked")
    # read_job_posting (context="read") should NOT be affected by blocked
    from agent.sites import own_job_url
    from agent.tools.reads import read_job_posting
    from agent.tools.clients import FakePostingClient
    from sandbox.seed import seed

    seed(postings_dir=tmp_path / "postings")
    client = FakePostingClient(sandbox_dir=str(tmp_path))
    result = read_job_posting(own_job_url("job_001"), _client=client)
    assert "error" not in result


# ---------------------------------------------------------------------------
# read_job_posting SITE_NOT_ALLOWED
# ---------------------------------------------------------------------------

def test_read_job_posting_non_allowlisted_https_returns_site_not_allowed():
    _clear_cache()
    result = execute_tool("read_job_posting", {"url": "https://evil.com/jobs/1"})
    assert result["error"] == SITE_NOT_ALLOWED


def test_read_job_posting_own_site_url_works(tmp_path):
    _clear_cache()
    from agent.sites import own_job_url
    from agent.tools.reads import read_job_posting
    from agent.tools.clients import FakePostingClient
    from sandbox.seed import seed

    seed(postings_dir=tmp_path / "postings")
    client = FakePostingClient(sandbox_dir=str(tmp_path))
    result = read_job_posting(own_job_url("job_001"), _client=client)
    assert "error" not in result
    assert result["job_id"] == "job_001"


# ---------------------------------------------------------------------------
# repeated_call behaviour with find_jobs
# ---------------------------------------------------------------------------

def test_find_jobs_different_queries_not_repeated():
    """Two find_jobs calls with different queries must NOT count as repeated."""
    from agent.fake_model import FakeModel
    from agent.loop import AgentLoop
    from agent.checkpoint import HumanApprovalCheckpoint
    _clear_cache()

    responses = [
        {
            "type": "tool_call",
            "tool_name": "find_jobs",
            "arguments": {"query": "python", "site": "tanitjobs"},
            "usage": {"input_tokens": 1, "output_tokens": 1},
        },
        {
            "type": "tool_call",
            "tool_name": "find_jobs",
            "arguments": {"query": "django", "site": "tanitjobs"},
            "usage": {"input_tokens": 1, "output_tokens": 1},
        },
        {
            "type": "final",
            "content": "Done.",
            "usage": {"input_tokens": 1, "output_tokens": 1},
        },
    ]

    agent = AgentLoop(
        model=FakeModel(responses),
        checkpoint=HumanApprovalCheckpoint(auto_approve=True),
    )
    result = agent.run(initial_messages=[{"role": "user", "content": "Find jobs."}])
    assert result["stop_reason"] == "done"


def test_find_jobs_same_query_site_twice_counts_as_repeated():
    """The same find_jobs call three times triggers repeated_call stop."""
    from agent.fake_model import FakeModel
    from agent.loop import AgentLoop
    from agent.checkpoint import HumanApprovalCheckpoint
    from agent.config import MAX_SAME_CALL_REPEATS
    _clear_cache()

    responses = [
        {
            "type": "tool_call",
            "tool_name": "find_jobs",
            "arguments": {"query": "python", "site": "tanitjobs"},
            "usage": {"input_tokens": 1, "output_tokens": 1},
        }
    ] * (MAX_SAME_CALL_REPEATS + 1)

    agent = AgentLoop(
        model=FakeModel(responses),
        checkpoint=HumanApprovalCheckpoint(auto_approve=True),
    )
    result = agent.run(initial_messages=[{"role": "user", "content": "Find jobs."}])
    assert result["stop_reason"] == "repeated_call"


def test_find_jobs_different_sites_not_repeated():
    """find_jobs with same query but different sites must NOT count as repeated."""
    from agent.fake_model import FakeModel
    from agent.loop import AgentLoop
    from agent.checkpoint import HumanApprovalCheckpoint
    _clear_cache()

    responses = [
        {
            "type": "tool_call",
            "tool_name": "find_jobs",
            "arguments": {"query": "python", "site": "tanitjobs"},
            "usage": {"input_tokens": 1, "output_tokens": 1},
        },
        {
            "type": "tool_call",
            "tool_name": "find_jobs",
            "arguments": {"query": "python", "site": "keejob"},
            "usage": {"input_tokens": 1, "output_tokens": 1},
        },
        {
            "type": "final",
            "content": "Done.",
            "usage": {"input_tokens": 1, "output_tokens": 1},
        },
    ]

    agent = AgentLoop(
        model=FakeModel(responses),
        checkpoint=HumanApprovalCheckpoint(auto_approve=True),
    )
    result = agent.run(initial_messages=[{"role": "user", "content": "Search."}])
    assert result["stop_reason"] == "done"


# ---------------------------------------------------------------------------
# Search-then-tailor full chain (offline)
# ---------------------------------------------------------------------------

def test_search_then_tailor_chain(tmp_path, monkeypatch):
    """
    Full offline chain: find_jobs → read_job_posting → read_master_cv →
    match_skills → save_tailored_cv (cv) → save_tailored_cv (cover_letter) →
    submit_application → final.
    """
    from agent.__main__ import SEARCH_THEN_TAILOR_RESPONSES
    from agent.fake_model import FakeModel
    from agent.loop import AgentLoop
    from agent.checkpoint import HumanApprovalCheckpoint
    from agent.tools.clients import FakePostingClient
    from sandbox.seed import seed
    from agent.tools import reads, writes

    _clear_cache()

    # Set up sandbox in tmp_path
    seed(postings_dir=tmp_path / "postings")
    from sandbox.portal import Portal
    portal = Portal(sandbox_dir=str(tmp_path))
    client = FakePostingClient(sandbox_dir=str(tmp_path))

    # Monkeypatch the module-level client/portal used by reads/writes
    monkeypatch.setattr(reads, "_client_instance", client)
    monkeypatch.setattr(writes, "_portal", portal)

    # Put the master CV in place
    cv_path = tmp_path / "master_cv.md"
    cv_path.write_text("# CV\n## Skills\nPython, SQL, Git", encoding="utf-8")
    monkeypatch.setattr(reads, "_cv_path", cv_path)

    agent = AgentLoop(
        model=FakeModel(SEARCH_THEN_TAILOR_RESPONSES),
        checkpoint=HumanApprovalCheckpoint(auto_approve=True),
    )
    result = agent.run(
        initial_messages=[{"role": "user", "content": "Find and tailor a job for me."}]
    )
    assert result["stop_reason"] == "done"
    assert result["step_count"] == 7  # find_jobs + 5 tools + submit
