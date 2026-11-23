"""Tests for the per-session CV upload (agent/cv_upload.py) and the read_master_cv override."""

import pytest

from agent import cv_upload
from agent.cv_upload import CvUploadError, clean_cv_text, validate_upload
from agent.tools import reads

GOOD = ("# CV\n\nAlex Example\n\n## Skills\nPython, SQL, Flask, pytest\n\n## Experience\n"
        "Intern at Example Co, built data pipelines.\n").encode()


@pytest.fixture(autouse=True)
def _tmp_sandbox(tmp_path, monkeypatch):
    monkeypatch.setattr(cv_upload, "SANDBOX_DIR", str(tmp_path))


def test_accepts_md_and_txt():
    assert "Python" in validate_upload("cv.md", GOOD)
    assert "Python" in validate_upload("CV.TXT", GOOD)


@pytest.mark.parametrize("name", ["cv.pdf", "cv.docx", "cv", "cv.md.exe", ""])
def test_rejects_other_types(name):
    with pytest.raises(CvUploadError):
        validate_upload(name, GOOD)


def test_rejects_too_large_and_non_utf8_and_empty():
    with pytest.raises(CvUploadError):
        validate_upload("cv.md", b"a" * (cv_upload.MAX_UPLOAD_BYTES + 1))
    with pytest.raises(CvUploadError):
        validate_upload("cv.md", b"\xff\xfe\x00bad" * 20)
    with pytest.raises(CvUploadError):
        validate_upload("cv.md", b"hi")


def test_cleaning_strips_hidden_and_html():
    dirty = "Skills​: Py‍thon <script>alert(1)</script><b>SQL</b>\x07 " + "x" * 60
    out = clean_cv_text(dirty)
    assert "​" not in out and "‍" not in out
    assert "<" not in out and "\x07" not in out
    assert "Python" in out and "SQL" in out


def test_cleaning_caps_length():
    assert len(clean_cv_text("a" * 100_000)) == cv_upload.MAX_CV_CHARS


def test_sessions_are_isolated_and_ids_sanitised(tmp_path):
    p1 = cv_upload.save_session_cv("sess-1", "cv.md", GOOD)
    p2 = cv_upload.save_session_cv("sess-2", "cv.md", GOOD.replace(b"Alex", b"Bea"))
    assert p1 != p2
    assert "Alex" in p1.read_text() and "Bea" in p2.read_text()
    evil = cv_upload.session_cv_path("../../etc/passwd")
    assert tmp_path in evil.parents and ".." not in evil.parts
    with pytest.raises(CvUploadError):
        cv_upload.session_cv_path("../..")


def test_delete_removes_only_that_session():
    p1 = cv_upload.save_session_cv("a1", "cv.md", GOOD)
    p2 = cv_upload.save_session_cv("a2", "cv.md", GOOD)
    cv_upload.delete_session_cv("a1")
    assert not p1.exists() and p2.exists()


def test_read_master_cv_uses_override_and_resets():
    path = cv_upload.save_session_cv("s9", "cv.md", GOOD.replace(b"Alex", b"Zed"))
    token = reads.CV_PATH_OVERRIDE.set(path)
    try:
        assert "Zed" in reads.read_master_cv()["text"]
    finally:
        reads.CV_PATH_OVERRIDE.reset(token)
    assert "Zed" not in reads.read_master_cv()["text"]


def test_override_does_not_leak_between_contexts():
    import contextvars
    path = cv_upload.save_session_cv("s10", "cv.md", GOOD.replace(b"Alex", b"Yan"))
    ctx = contextvars.copy_context()
    ctx.run(reads.CV_PATH_OVERRIDE.set, path)
    assert "Yan" in ctx.run(reads.read_master_cv)["text"]
    assert "Yan" not in reads.read_master_cv()["text"]
