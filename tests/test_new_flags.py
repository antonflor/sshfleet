"""Tests for the v2 QoL flags: --version, --device-type, --no-ping,
--dry-run, --output-dir, and the fail-before-credentials main() flow."""

from __future__ import annotations

import pytest


def test_parse_args_new_defaults(nda):
    ns = nda.parse_args([])
    assert ns.device_type is None
    assert ns.no_ping is False
    assert ns.dry_run is False
    assert ns.session_log is None


def test_version_flag_exits_cleanly(nda, capsys):
    with pytest.raises(SystemExit) as exc:
        nda.parse_args(["--version"])
    assert exc.value.code == 0
    assert nda.__version__ in capsys.readouterr().out


def test_build_jobs_device_type_override_skips_detection(nda, monkeypatch):
    def boom(*a, **kw):
        raise AssertionError("detection should not run")

    monkeypatch.setattr(nda, "detect_device_type", boom)
    monkeypatch.setattr(nda, "ping_check", boom)

    jobs = nda.build_jobs(
        ["10.0.0.1", "10.0.0.2"],
        ["show version"],
        "u",
        "p",
        None,
        device_type="cisco_ios",
        skip_ping=True,
    )
    assert [j.device_type for j in jobs] == ["cisco_ios", "cisco_ios"]
    assert all(j.reachable and j.error is None for j in jobs)


def test_build_jobs_no_ping_still_detects(nda, monkeypatch):
    monkeypatch.setattr(
        nda, "ping_check", lambda *a, **kw: pytest.fail("ping should be skipped")
    )
    monkeypatch.setattr(nda, "detect_device_type", lambda *a, **kw: "arista_eos")

    jobs = nda.build_jobs(["10.0.0.1"], ["show version"], "u", "p", None, skip_ping=True)
    assert jobs[0].device_type == "arista_eos"


def _write_inputs(tmp_path, commands="show version\n"):
    devs = tmp_path / "devices.txt"
    cmds = tmp_path / "commands.txt"
    devs.write_text("10.0.0.1\n")
    cmds.write_text(commands)
    return devs, cmds


def test_main_dry_run_needs_no_credentials(nda, tmp_path, monkeypatch, capsys):
    monkeypatch.setattr(
        "builtins.input", lambda *_: pytest.fail("must not prompt in dry run")
    )
    devs, cmds = _write_inputs(tmp_path)
    rc = nda.main(
        ["--devices-file", str(devs), "--commands-file", str(cmds), "--dry-run"]
    )
    assert rc == 0
    assert "Dry run" in capsys.readouterr().out


def test_main_rejects_non_show_commands_before_credentials(nda, tmp_path, monkeypatch):
    monkeypatch.setattr(
        "builtins.input", lambda *_: pytest.fail("must not prompt on invalid input")
    )
    devs, cmds = _write_inputs(tmp_path, commands="reload\n")
    rc = nda.main(["--devices-file", str(devs), "--commands-file", str(cmds), "--yes"])
    assert rc == 1


def test_main_missing_devices_file_returns_1(nda, tmp_path):
    _, cmds = _write_inputs(tmp_path)
    rc = nda.main(
        [
            "--devices-file", str(tmp_path / "nope.txt"),
            "--commands-file", str(cmds),
            "--yes",
        ]
    )
    assert rc == 1


def test_main_end_to_end_writes_outputs_to_output_dir(nda, tmp_path, monkeypatch):
    devs, cmds = _write_inputs(tmp_path)
    out_dir = tmp_path / "logs"
    monkeypatch.setenv("SSHFLEET_PASSWORD", "secret")
    monkeypatch.setattr(
        nda,
        "run_jobs",
        lambda jobs, config_mode, concurrency: [
            nda.DeviceResult(device=j.host, complete=True) for j in jobs
        ],
    )
    monkeypatch.setattr(
        nda,
        "build_jobs",
        lambda hosts, commands, username, password, snmp, **kw: [
            nda.DeviceJob(
                host=h,
                username=username,
                password=password,
                commands=list(commands),
            )
            for h in hosts
        ],
    )

    rc = nda.main(
        [
            "--user", "admin",
            "--devices-file", str(devs),
            "--commands-file", str(cmds),
            "--output-dir", str(out_dir),
            "--yes",
        ]
    )
    assert rc == 0
    session_files = list(out_dir.glob("session_*.json"))
    assert len(session_files) == 1
    assert '"complete": true' in session_files[0].read_text()
