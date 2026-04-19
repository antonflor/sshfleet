from __future__ import annotations

import subprocess
from types import SimpleNamespace


def test_ping_check_returns_true_on_zero_exit(nda, monkeypatch):
    captured = {}

    def fake_run(cmd, **kwargs):
        captured["cmd"] = cmd
        return SimpleNamespace(returncode=0)

    monkeypatch.setattr(nda.subprocess, "run", fake_run)
    monkeypatch.setattr(nda.shutil, "which", lambda _: "/usr/bin/ping")

    assert nda.ping_check("10.0.0.1") is True
    assert "10.0.0.1" in captured["cmd"]


def test_ping_check_returns_false_on_nonzero_exit(nda, monkeypatch):
    monkeypatch.setattr(
        nda.subprocess, "run", lambda *a, **kw: SimpleNamespace(returncode=1)
    )
    monkeypatch.setattr(nda.shutil, "which", lambda _: "/usr/bin/ping")
    assert nda.ping_check("10.0.0.1") is False


def test_ping_check_handles_timeout(nda, monkeypatch):
    def boom(*a, **kw):
        raise subprocess.TimeoutExpired(cmd="ping", timeout=5)

    monkeypatch.setattr(nda.subprocess, "run", boom)
    monkeypatch.setattr(nda.shutil, "which", lambda _: "/usr/bin/ping")
    assert nda.ping_check("10.0.0.1") is False


def test_ping_check_assumes_reachable_when_ping_missing(nda, monkeypatch):
    monkeypatch.setattr(nda.shutil, "which", lambda _: None)
    assert nda.ping_check("10.0.0.1") is True
