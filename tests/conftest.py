"""Test setup: load sshfleet.py as a module without requiring real netmiko."""

from __future__ import annotations

import importlib.util
import sys
import types
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent


def _install_netmiko_stub() -> None:
    if "netmiko" in sys.modules:
        return

    netmiko = types.ModuleType("netmiko")

    class _Stub:  # placeholder; tests that need real behaviour patch it
        pass

    netmiko.ConnectHandler = _Stub
    netmiko.SSHDetect = _Stub
    sys.modules["netmiko"] = netmiko

    # SNMPDetect is lazily imported from netmiko.snmp_autodetect (needs pysnmp)
    snmp_autodetect = types.ModuleType("netmiko.snmp_autodetect")
    snmp_autodetect.SNMPDetect = _Stub
    sys.modules["netmiko.snmp_autodetect"] = snmp_autodetect

    exceptions = types.ModuleType("netmiko.exceptions")

    class NetmikoAuthenticationException(Exception):
        pass

    class NetmikoTimeoutException(Exception):
        pass

    exceptions.NetmikoAuthenticationException = NetmikoAuthenticationException
    exceptions.NetmikoTimeoutException = NetmikoTimeoutException
    sys.modules["netmiko.exceptions"] = exceptions


@pytest.fixture(scope="session")
def nda():
    """Import sshfleet.py as the module ``nda`` (historic fixture name)."""
    _install_netmiko_stub()
    spec = importlib.util.spec_from_file_location("nda", REPO_ROOT / "sshfleet.py")
    module = importlib.util.module_from_spec(spec)
    sys.modules["nda"] = module  # required for dataclass introspection
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module
