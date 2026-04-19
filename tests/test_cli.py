from __future__ import annotations


def test_parse_args_defaults(nda):
    ns = nda.parse_args([])
    assert ns.user is None
    assert ns.config is False
    assert ns.yes is False
    assert ns.verbose is False


def test_parse_args_full(nda, tmp_path):
    devs = tmp_path / "d.txt"
    cmds = tmp_path / "c.txt"
    devs.write_text("10.0.0.1\n")
    cmds.write_text("show version\n")

    ns = nda.parse_args(
        [
            "--user", "admin",
            "--devices-file", str(devs),
            "--commands-file", str(cmds),
            "--snmp-community", "public",
            "--config",
            "--yes",
            "--verbose",
        ]
    )
    assert ns.user == "admin"
    assert ns.devices_file == devs
    assert ns.commands_file == cmds
    assert ns.snmp_community == "public"
    assert ns.config is True
    assert ns.yes is True
    assert ns.verbose is True


def test_device_result_to_dict_round_trip(nda):
    r = nda.DeviceResult(device="10.0.0.1", complete=False, error="boom")
    assert r.to_dict() == {
        "device": "10.0.0.1",
        "complete": False,
        "error": "boom",
    }


def test_confirm_accepts_y_yes(nda, monkeypatch):
    monkeypatch.setattr("builtins.input", lambda _: "Y")
    assert nda.confirm("?") is True
    monkeypatch.setattr("builtins.input", lambda _: "yes")
    assert nda.confirm("?") is True
    monkeypatch.setattr("builtins.input", lambda _: "n")
    assert nda.confirm("?") is False
    monkeypatch.setattr("builtins.input", lambda _: "")
    assert nda.confirm("?") is False
