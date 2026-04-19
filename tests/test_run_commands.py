from __future__ import annotations

import pytest


class FakeConn:
    def __init__(self):
        self.sent_commands: list[str] = []
        self.sent_config: list[str] | None = None

    def send_command(self, cmd: str) -> str:
        self.sent_commands.append(cmd)
        return f"<output of {cmd}>"

    def send_config_set(self, cmds: list[str]) -> str:
        self.sent_config = list(cmds)
        return "config applied"


def test_run_commands_show_uses_send_command(nda):
    conn = FakeConn()
    out = nda.run_commands(conn, ["show version", "show clock"], config_mode=False)
    assert conn.sent_commands == ["show version", "show clock"]
    assert conn.sent_config is None
    assert "show version" in out and "<output of show version>" in out


def test_run_commands_rejects_non_show_in_exec_mode(nda):
    conn = FakeConn()
    with pytest.raises(ValueError, match="--config"):
        nda.run_commands(conn, ["interface Gi0/1"], config_mode=False)
    assert conn.sent_commands == []


def test_run_commands_config_mode_uses_send_config_set(nda):
    conn = FakeConn()
    out = nda.run_commands(
        conn,
        ["interface Gi0/1", "description test"],
        config_mode=True,
    )
    assert conn.sent_config == ["interface Gi0/1", "description test"]
    assert out == "config applied"
