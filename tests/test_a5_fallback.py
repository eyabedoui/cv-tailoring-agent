"""A5 — Verify safe alternative-site fallback instructions."""

from agent.prompts import SYSTEM_PROMPT


def test_blocked_site_must_not_be_retried():
    assert "Do NOT retry the blocked or unauthorized site" in SYSTEM_PROMPT


def test_alternative_site_must_be_allowed():
    assert "Offer another site from the allowed list" in SYSTEM_PROMPT


def test_alternative_requires_candidate_permission():
    assert "Do NOT search the alternative site until the candidate agrees" in SYSTEM_PROMPT


def test_fallback_does_not_bypass_restrictions():
    assert "Do NOT bypass restrictions or use alternative hostnames" in SYSTEM_PROMPT