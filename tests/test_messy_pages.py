
"""
B7: Saved messy-page fixture integration tests.

Tests the actual job-posting parser using local fixtures.
No Firecrawl, OpenAI, or Groq API calls are made.
"""

from pathlib import Path

import pytest

from agent.posting_cleaner import clean_posting
from agent.tools.reads import parse_posting, read_job_posting


FIXTURE_DIR = (
    Path(__file__).parent / "fixtures" / "messy_pages"
)

TEST_URL = "https://example.com/jobs/test-posting"


def load_fixture(filename):
    """Load a saved messy-page fixture."""
    return (FIXTURE_DIR / filename).read_text(encoding="utf-8")


class FakeMarkdownClient:
    """Simulate a client returning scraped Markdown."""

    def __init__(self, markdown):
        self.markdown = markdown

    def fetch(self, url):
        return {
            "url": url,
            "markdown": self.markdown,
        }


@pytest.mark.parametrize(
    "filename, forbidden",
    [
        ("01_html_comments.md", "Hidden instruction"),
        ("02_zero_width.md", "\u200b"),
        ("03_scripts.html", "alert("),
        ("04_navigation.md", "About\n"),
        ("05_cookies.md", "Accept cookies"),
        ("06_footer.md", "All rights reserved"),
        ("10_closing_tag.md", "</tool_result>"),
        ("11_advertisement.md", "Buy our products today"),
        ("12_hidden_html.html", "Ignore previous instructions"),
    ],
)
def test_saved_fixture_removes_unwanted_content(filename, forbidden):
    """Unwanted page content must not reach the parser output."""

    markdown = load_fixture(filename)

    posting = parse_posting(markdown, TEST_URL)

    combined = (
        posting["title"]
        + "\n"
        + posting["company"]
        + "\n"
        + "\n".join(posting["requirements"])
        + "\n"
        + posting["text"]
    )

    assert forbidden not in combined


def test_saved_empty_page():
    """Empty pages must remain empty after cleaning."""

    markdown = load_fixture("07_empty.md")

    assert clean_posting(markdown) == ""


def test_saved_oversized_page():
    """Oversized content must be rejected before parsing."""

    markdown = load_fixture("08_oversized.md")

    with pytest.raises(ValueError, match="maximum allowed length"):
        parse_posting(markdown, TEST_URL)


def test_saved_french_page():
    """French job information must remain readable."""

    markdown = load_fixture("09_french.md")

    posting = parse_posting(markdown, TEST_URL)

    assert posting["title"] == "Développeur Python"
    assert "Python" in posting["requirements"]
    assert "Analyse de données" in posting["requirements"]
    assert "Développement" in posting["text"]


def test_read_job_posting_uses_cleaner():
    """The real read tool must clean client-provided Markdown."""

    markdown = load_fixture("01_html_comments.md")

    client = FakeMarkdownClient(markdown)

    # Use an allowed own-site URL so no external request is needed.
    from agent.sites import own_job_url

    result = read_job_posting(
        own_job_url("job_001"),
        _client=client,
    )

    assert "error" not in result
    assert "Hidden instruction" not in result["text"]
    assert result["title"] == "Python Developer"


def test_read_job_posting_rejects_oversized_page():
    """The read tool should return a structured error, not crash."""

    markdown = load_fixture("08_oversized.md")

    client = FakeMarkdownClient(markdown)

    from agent.sites import own_job_url

    result = read_job_posting(
        own_job_url("job_001"),
        _client=client,
    )

    assert result["error"] == "EMPTY_POSTING"
