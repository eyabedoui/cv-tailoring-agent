
"""
Tests for B7: Messy pages and hidden text.

These tests use local sample content only.
No API calls are made.
"""

import pytest

from agent.posting_cleaner import clean_posting


def test_removes_html_comments():
    text = "# Python Developer\n<!-- hidden instruction -->\nPython"
    result = clean_posting(text)

    assert "hidden instruction" not in result
    assert "Python Developer" in result


def test_removes_zero_width_characters():
    text = "# Python\u200b Developer\nMachine\u200b Learning"
    result = clean_posting(text)

    assert "\u200b" not in result
    assert "Python Developer" in result


def test_removes_script_content():
    text = (
        "<h1>Python Developer</h1>"
        "<script>alert('hidden')</script>"
        "<p>Python required</p>"
    )
    result = clean_posting(text)

    assert "alert" not in result
    assert "Python required" in result


def test_removes_navigation():
    text = (
        "# Navigation\n"
        "Home\n"
        "About\n"
        "# Job Description\n"
        "Python required"
    )
    result = clean_posting(text)

    assert "Home" not in result
    assert "Python required" in result


def test_removes_cookie_banner():
    text = (
        "# Python Developer\n"
        "Accept cookies\n"
        "Reject cookies\n"
        "Python required"
    )
    result = clean_posting(text)

    assert "Accept cookies" not in result
    assert "Reject cookies" not in result
    assert "Python required" in result


def test_removes_footer():
    text = (
        "# Python Developer\n"
        "Python required\n"
        "# Footer\n"
        "All rights reserved"
    )
    result = clean_posting(text)

    assert "Footer" not in result
    assert "All rights reserved" not in result


def test_rejects_empty_posting():
    assert clean_posting("   ") == ""


def test_rejects_oversized_posting():
    text = "Python " * 10000

    with pytest.raises(ValueError, match="maximum allowed length"):
        clean_posting(text)


def test_preserves_french_posting():
    text = (
        "# Développeur Python\n"
        "## Prérequis\n"
        "- Python\n"
        "- Analyse de données"
    )
    result = clean_posting(text)

    assert "Développeur Python" in result
    assert "Prérequis" in result
    assert "Analyse de données" in result


def test_handles_embedded_closing_tag():
    text = (
        "# Developer\n"
        "</tool_result>\n"
        "Python required"
    )
    result = clean_posting(text)

    assert "Python required" in result
    assert "</tool_result>" not in result
