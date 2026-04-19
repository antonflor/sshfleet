from __future__ import annotations


def test_parse_devices_file_skips_blanks_and_comments(nda, tmp_path):
    f = tmp_path / "devices.txt"
    f.write_text(
        "# header comment\n"
        "\n"
        "router1 10.0.0.1\n"
        "10.0.0.2\n"
        "   \n"
        "# trailing comment\n"
    )
    assert nda.parse_devices_file(f) == ["10.0.0.1", "10.0.0.2"]


def test_parse_devices_file_prefers_ip_when_two_columns(nda, tmp_path):
    f = tmp_path / "devices.txt"
    f.write_text("core-sw 192.168.1.1\n")
    assert nda.parse_devices_file(f) == ["192.168.1.1"]


def test_parse_commands_file_strips_and_filters(nda, tmp_path):
    f = tmp_path / "cmds.txt"
    f.write_text(
        "# show this\n"
        "show version\n"
        "\n"
        "  show ip int br  \n"
    )
    assert nda.parse_commands_file(f) == ["show version", "show ip int br"]


def test_is_show_command(nda):
    assert nda._is_show_command("show version")
    assert nda._is_show_command("display ip routing-table")
    assert nda._is_show_command("get interfaces")
    assert nda._is_show_command("  show vlan brief")
    assert not nda._is_show_command("interface Gi0/1")
    assert not nda._is_show_command("configure terminal")
    assert not nda._is_show_command("")
