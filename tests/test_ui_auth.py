"""Tests for the chat login helper (no Chainlit needed)."""

from ui.logic import check_credentials


def test_correct_credentials_accepted():
    assert check_credentials("demo", "s3cret", "demo", "s3cret") is True


def test_wrong_password_rejected():
    assert check_credentials("demo", "wrong", "demo", "s3cret") is False


def test_wrong_username_rejected():
    assert check_credentials("other", "s3cret", "demo", "s3cret") is False


def test_unset_expected_values_reject_everything():
    assert check_credentials("", "", None, None) is False
    assert check_credentials("demo", "s3cret", "", "") is False


def test_empty_attempt_rejected():
    assert check_credentials("", "", "demo", "s3cret") is False
    assert check_credentials(None, None, "demo", "s3cret") is False
