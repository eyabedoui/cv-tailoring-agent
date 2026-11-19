"""
Tests for W7 snapshot and replay mode — all offline.

firecrawl.V1FirecrawlApp is monkeypatched for snapshot tests.
FakePostingClient is tested directly for replay mode.
"""
import hashlib
import json

import pytest
import firecrawl

from agent.tools.clients import FakePostingClient
from sandbox.manage import snapshot
from sandbox.seed import seed


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_KEEJOB_URL = "https://www.keejob.com/offres-emploi/42"
_MARKDOWN = """\
# Data Engineer
**Company:** StreamCo

## Requirements
- Python
- Spark

## Description
Build scalable data pipelines.
"""


def _job_id_for(url: str) -> str:
    from agent.sites import url_belongs_to_site, site_names
    h = hashlib.sha256(url.encode()).hexdigest()[:8]
    site = "ext"
    for s in site_names():
        if url_belongs_to_site(url, s):
            site = s
            break
    return f"{site}-{h}"


@pytest.fixture()
def mock_firecrawl(monkeypatch):
    class _FakeScrapeResponse:
        markdown = _MARKDOWN

    class _FakeApp:
        def __init__(self, api_key="", **kwargs):
            pass

        def scrape_url(self, url, **kwargs):
            return _FakeScrapeResponse()

    monkeypatch.setattr(firecrawl, "V1FirecrawlApp", _FakeApp)


# ---------------------------------------------------------------------------
# snapshot() — saves file
# ---------------------------------------------------------------------------

def test_snapshot_creates_file(tmp_path, mock_firecrawl):
    snapshot(url=_KEEJOB_URL, snapshots_dir=str(tmp_path / "snapshots"))
    expected_id = _job_id_for(_KEEJOB_URL)
    assert (tmp_path / "snapshots" / f"{expected_id}.json").exists()


def test_snapshot_file_contains_url(tmp_path, mock_firecrawl):
    snapshot(url=_KEEJOB_URL, snapshots_dir=str(tmp_path / "snapshots"))
    job_id = _job_id_for(_KEEJOB_URL)
    data = json.loads((tmp_path / "snapshots" / f"{job_id}.json").read_text(encoding="utf-8"))
    assert data["url"] == _KEEJOB_URL


def test_snapshot_file_contains_markdown(tmp_path, mock_firecrawl):
    snapshot(url=_KEEJOB_URL, snapshots_dir=str(tmp_path / "snapshots"))
    job_id = _job_id_for(_KEEJOB_URL)
    data = json.loads((tmp_path / "snapshots" / f"{job_id}.json").read_text(encoding="utf-8"))
    assert "Data Engineer" in data["markdown"]


def test_snapshot_file_contains_job_id(tmp_path, mock_firecrawl):
    snapshot(url=_KEEJOB_URL, snapshots_dir=str(tmp_path / "snapshots"))
    expected_id = _job_id_for(_KEEJOB_URL)
    data = json.loads((tmp_path / "snapshots" / f"{expected_id}.json").read_text(encoding="utf-8"))
    assert data["job_id"] == expected_id


def test_snapshot_id_starts_with_site(tmp_path, mock_firecrawl):
    snapshot(url=_KEEJOB_URL, snapshots_dir=str(tmp_path / "snapshots"))
    expected_id = _job_id_for(_KEEJOB_URL)
    assert expected_id.startswith("keejob-")


def test_snapshot_error_does_not_create_file(tmp_path, monkeypatch):
    """When Firecrawl returns an error, no snapshot file is created."""

    class _FakeErrorApp:
        def __init__(self, **kwargs):
            pass

        def scrape_url(self, url, **kwargs):
            raise ConnectionError("unreachable")

    monkeypatch.setattr(firecrawl, "V1FirecrawlApp", _FakeErrorApp)
    snapshot(url=_KEEJOB_URL, snapshots_dir=str(tmp_path / "snapshots"))
    snapshots_dir = tmp_path / "snapshots"
    assert not any(snapshots_dir.glob("*.json")) if snapshots_dir.exists() else True


# ---------------------------------------------------------------------------
# FakePostingClient — replay mode
# ---------------------------------------------------------------------------

def _write_snapshot(snapshots_dir, url: str, markdown: str) -> str:
    job_id = _job_id_for(url)
    snapshots_dir.mkdir(parents=True, exist_ok=True)
    data = {"url": url, "job_id": job_id, "markdown": markdown}
    (snapshots_dir / f"{job_id}.json").write_text(
        json.dumps(data), encoding="utf-8"
    )
    return job_id


def test_replay_mode_loads_snapshot(tmp_path, monkeypatch):
    monkeypatch.setenv("WEB_MODE", "replay")
    seed(postings_dir=tmp_path / "postings")
    _write_snapshot(tmp_path / "snapshots", _KEEJOB_URL, _MARKDOWN)
    client = FakePostingClient(sandbox_dir=str(tmp_path))
    result = client.fetch(_KEEJOB_URL)
    assert "error" not in result
    assert "markdown" in result
    assert "Data Engineer" in result["markdown"]


def test_replay_mode_missing_snapshot_returns_not_found(tmp_path, monkeypatch):
    monkeypatch.setenv("WEB_MODE", "replay")
    seed(postings_dir=tmp_path / "postings")
    client = FakePostingClient(sandbox_dir=str(tmp_path))
    result = client.fetch(_KEEJOB_URL)
    assert result["error"] == "NOT_FOUND"


def test_replay_mode_own_site_still_uses_postings(tmp_path, monkeypatch):
    from agent.sites import own_job_url
    monkeypatch.setenv("WEB_MODE", "replay")
    seed(postings_dir=tmp_path / "postings")
    client = FakePostingClient(sandbox_dir=str(tmp_path))
    result = client.fetch(own_job_url("job_001"))
    assert "error" not in result
    assert result["_posting"]["job_id"] == "job_001"


def test_fake_mode_external_url_returns_not_found(tmp_path, monkeypatch):
    monkeypatch.setenv("WEB_MODE", "fake")
    seed(postings_dir=tmp_path / "postings")
    client = FakePostingClient(sandbox_dir=str(tmp_path))
    result = client.fetch(_KEEJOB_URL)
    assert result["error"] == "NOT_FOUND"


def test_replay_snapshot_url_in_result(tmp_path, monkeypatch):
    monkeypatch.setenv("WEB_MODE", "replay")
    seed(postings_dir=tmp_path / "postings")
    _write_snapshot(tmp_path / "snapshots", _KEEJOB_URL, _MARKDOWN)
    client = FakePostingClient(sandbox_dir=str(tmp_path))
    result = client.fetch(_KEEJOB_URL)
    assert result["url"] == _KEEJOB_URL
