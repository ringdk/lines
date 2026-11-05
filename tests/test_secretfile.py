"""secrets.age: round trip, refusals, and no secret in the logs (rule 6)."""

from __future__ import annotations

import logging

import pytest

from lines import secretfile


def test_round_trip(tmp_path):
    path = tmp_path / "secrets.age"
    secretfile.save(path, {"A": "one", "B": "two=2"}, "pass")
    assert secretfile.load(path, "pass") == {"A": "one", "B": "two=2"}
    assert b"one" not in path.read_bytes()


def test_a_wrong_passphrase_is_refused(tmp_path):
    path = tmp_path / "secrets.age"
    secretfile.save(path, {"A": "one"}, "pass")
    with pytest.raises(secretfile.SecretsError):
        secretfile.load(path, "nope")


def test_a_line_break_is_never_written(tmp_path):
    with pytest.raises(secretfile.SecretsError):
        secretfile.save(tmp_path / "secrets.age", {"A": "one\nB=two"}, "pass")


def test_nothing_falls_back_to_the_environment(monkeypatch):
    secretfile.use({})
    monkeypatch.setenv(secretfile.APP_KEY, "from-the-environment")
    assert secretfile.get(secretfile.APP_KEY) == ""


def test_the_passphrase_comes_from_the_credential(tmp_path, monkeypatch):
    monkeypatch.delenv(secretfile.PASSPHRASE_ENV, raising=False)
    (tmp_path / secretfile.CREDENTIAL_NAME).write_text("from-systemd\n")
    monkeypatch.setenv("CREDENTIALS_DIRECTORY", str(tmp_path))
    assert secretfile.resolve_passphrase() == "from-systemd"


def test_loaded_secrets_are_redacted_from_logs(caplog):
    secretfile.use({secretfile.APP_KEY: "a-very-secret-value"})
    try:
        logger = logging.getLogger("lines.test")
        with caplog.at_level(logging.INFO):
            caplog.handler.addFilter(secretfile._redactor)
            logger.info("the key is %s", "a-very-secret-value")
        assert "a-very-secret-value" not in caplog.text and "[REDACTED]" in caplog.text
    finally:
        secretfile.use({})
