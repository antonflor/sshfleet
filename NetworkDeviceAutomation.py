#!/usr/bin/env python3
"""Bulk-execute commands across a list of network devices via SSH (netmiko).

Reads a devices file (one host per line, optionally `name ip`) and a commands
file (one command per line), pings each device, optionally autodetects its
type via SNMP/SSH, runs the commands, and writes a JSON session report plus
per-device log files.
"""

from __future__ import annotations

import argparse
import json
import logging
import os
import platform
import shutil
import subprocess
import sys
import time
import warnings
from contextlib import contextmanager
from dataclasses import dataclass, field, asdict
from datetime import datetime
from getpass import getpass
from pathlib import Path
from typing import Iterable, Iterator, List, Optional, Sequence

from netmiko import ConnectHandler, SSHDetect, SNMPDetect
from netmiko.exceptions import NetmikoAuthenticationException, NetmikoTimeoutException

warnings.filterwarnings("ignore", category=DeprecationWarning, module=r".*paramiko.*")

# SIGPIPE is POSIX-only; SIGINT exists everywhere but the default handler is
# already what we want, so we only adjust what's actually needed per-platform.
if hasattr(__import__("signal"), "SIGPIPE"):
    import signal

    signal.signal(signal.SIGPIPE, signal.SIG_DFL)


SESSION_TIMESTAMP = datetime.now().strftime("%Y%m%d_%H%M%S")
DEFAULT_SESSION_LOG = Path.cwd() / f"any_automate.log.{SESSION_TIMESTAMP}"

SEP_MAJOR = "=" * 50
SEP_MINOR = "=" * 5

logger = logging.getLogger("network_automation")


# --------------------------------------------------------------------------- #
# Data model
# --------------------------------------------------------------------------- #


@dataclass
class DeviceJob:
    host: str
    username: str
    password: str = field(repr=False)
    commands: List[str] = field(default_factory=list)
    reachable: bool = False
    device_type: Optional[str] = None
    error: Optional[str] = None


@dataclass
class DeviceResult:
    device: str
    complete: bool
    error: str = ""

    def to_dict(self) -> dict:
        return asdict(self)


# --------------------------------------------------------------------------- #
# Logging
# --------------------------------------------------------------------------- #


def _device_logger(host: str) -> logging.Logger:
    """Per-device logger that appends to ``<host>.log`` in the cwd."""
    name = f"network_automation.device.{host}"
    log = logging.getLogger(name)
    if not log.handlers:
        handler = logging.FileHandler(f"{host}.log")
        handler.setFormatter(
            logging.Formatter("%(asctime)s - %(name)s - %(levelname)s - %(message)s")
        )
        log.addHandler(handler)
        log.setLevel(logging.INFO)
        log.propagate = False
    return log


def configure_root_logging(verbose: bool) -> None:
    level = logging.DEBUG if verbose else logging.INFO
    logging.basicConfig(
        level=level,
        format="%(asctime)s - %(levelname)s - %(message)s",
    )


# --------------------------------------------------------------------------- #
# Reachability
# --------------------------------------------------------------------------- #


def ping_check(host: str, count: int = 3, timeout: int = 2) -> bool:
    """Return True if ``host`` responds to ICMP, False otherwise.

    Cross-platform: uses ``-n`` on Windows and ``-c`` elsewhere.
    """
    if shutil.which("ping") is None:
        logger.warning("ping binary not found; assuming %s reachable", host)
        return True

    if platform.system().lower().startswith("win"):
        cmd = ["ping", "-n", str(count), "-w", str(timeout * 1000), host]
    else:
        cmd = ["ping", "-c", str(count), "-W", str(timeout), host]

    try:
        result = subprocess.run(
            cmd,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            check=False,
            timeout=count * timeout + 5,
        )
        return result.returncode == 0
    except subprocess.TimeoutExpired:
        return False


# --------------------------------------------------------------------------- #
# Device type detection
# --------------------------------------------------------------------------- #


def detect_device_type(
    host: str,
    username: str,
    password: str,
    snmp_community: Optional[str] = None,
    attempts: int = 3,
    backoff: float = 1.0,
) -> Optional[str]:
    """Try SNMP first (if community given), then SSH autodetect."""
    last_error: Optional[str] = None

    for attempt in range(1, attempts + 1):
        if snmp_community:
            try:
                guess = SNMPDetect(
                    hostname=host,
                    community=snmp_community,
                    snmp_version="v2c",
                ).autodetect()
                if guess:
                    return guess
            except Exception as exc:  # noqa: BLE001 - netmiko raises broad types
                last_error = f"SNMP: {exc}"

        try:
            guess = SSHDetect(
                device_type="autodetect",
                host=host,
                username=username,
                password=password,
            ).autodetect()
            if guess:
                return guess
        except Exception as exc:  # noqa: BLE001
            last_error = f"SSH: {exc}"

        if attempt < attempts:
            time.sleep(backoff * attempt)

    if last_error:
        _device_logger(host).error("Device-type detection failed: %s", last_error)
    return None


# --------------------------------------------------------------------------- #
# File parsing
# --------------------------------------------------------------------------- #


def parse_devices_file(path: Path) -> List[str]:
    """One host per line. Lines may be ``hostname ip`` (ip wins) or ``ip``.

    Blank lines and ``#`` comments are skipped.
    """
    hosts: List[str] = []
    for raw in path.read_text().splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        parts = line.split()
        hosts.append(parts[1] if len(parts) > 1 else parts[0])
    return hosts


def parse_commands_file(path: Path) -> List[str]:
    return [
        line.strip()
        for line in path.read_text().splitlines()
        if line.strip() and not line.lstrip().startswith("#")
    ]


# --------------------------------------------------------------------------- #
# Command execution
# --------------------------------------------------------------------------- #


@contextmanager
def open_connection(
    host: str, username: str, password: str, device_type: str
) -> Iterator["ConnectHandler"]:
    conn = ConnectHandler(
        device_type=device_type,
        host=host,
        username=username,
        password=password,
    )
    try:
        yield conn
    finally:
        try:
            conn.disconnect()
        except Exception:  # noqa: BLE001 - cleanup must not raise
            pass


def _is_show_command(cmd: str) -> bool:
    head = cmd.strip().split(" ", 1)[0].lower()
    return head in {"show", "display", "get"}


def run_commands(
    conn: "ConnectHandler",
    commands: Sequence[str],
    config_mode: bool,
) -> str:
    """Run commands either in exec (default) or config mode.

    In default mode, show-style commands use ``send_command`` and anything
    else is rejected unless ``config_mode`` is set, removing the original
    ``'do ' + c`` Cisco-only hack.
    """
    if config_mode:
        return conn.send_config_set(list(commands))

    chunks: List[str] = []
    for cmd in commands:
        if not _is_show_command(cmd):
            raise ValueError(
                f"Refusing to run non-show command {cmd!r} without --config"
            )
        chunks.append(f"--- {cmd} ---\n{conn.send_command(cmd)}")
    return "\n".join(chunks)


def _format_block(title: str, body: str) -> str:
    indented = "\n   ".join(body.splitlines()) if body else ""
    return f"{title}:\n   {indented}" if indented else f"{title}:"


def execute_job(job: DeviceJob, config_mode: bool) -> DeviceResult:
    dev_log = _device_logger(job.host)
    logger.info("%s - processing", job.host)
    dev_log.info("Processing device")

    if job.error:
        logger.error("%s - %s", job.host, job.error)
        dev_log.error(job.error)
        return DeviceResult(device=job.host, complete=False, error=job.error)

    if not job.device_type:
        msg = "Unable to determine device type"
        dev_log.error(msg)
        return DeviceResult(device=job.host, complete=False, error=msg)

    try:
        with open_connection(
            job.host, job.username, job.password, job.device_type
        ) as conn:
            output = run_commands(conn, job.commands, config_mode=config_mode)
    except (NetmikoAuthenticationException, NetmikoTimeoutException) as exc:
        dev_log.error("Connection failed: %s", exc)
        return DeviceResult(device=job.host, complete=False, error=str(exc))
    except Exception as exc:  # noqa: BLE001
        dev_log.error("Execution failed: %s", exc)
        return DeviceResult(device=job.host, complete=False, error=str(exc))

    cmd_print = "\n - ".join([""] + list(job.commands))
    summary = (
        f"Device:\n - {job.host}\n{SEP_MINOR}\n"
        f"Commands:{cmd_print}\n{SEP_MINOR}\n"
        f"{_format_block('Output', output)}"
    )
    print(SEP_MINOR)
    print(summary)
    print(f"{SEP_MINOR}\n{job.host} - Done\n{SEP_MAJOR}")
    dev_log.info("Results:\n%s", summary)

    return DeviceResult(device=job.host, complete=True)


# --------------------------------------------------------------------------- #
# Orchestration
# --------------------------------------------------------------------------- #


def build_jobs(
    hosts: Iterable[str],
    commands: Sequence[str],
    username: str,
    password: str,
    snmp_community: Optional[str],
) -> List[DeviceJob]:
    jobs: List[DeviceJob] = []
    for host in hosts:
        reachable = ping_check(host)
        if not reachable:
            jobs.append(
                DeviceJob(
                    host=host,
                    username=username,
                    password=password,
                    commands=list(commands),
                    reachable=False,
                    error="Host unreachable",
                )
            )
            continue

        device_type = detect_device_type(host, username, password, snmp_community)
        jobs.append(
            DeviceJob(
                host=host,
                username=username,
                password=password,
                commands=list(commands),
                reachable=True,
                device_type=device_type,
                error=None if device_type else "Unable to determine device type",
            )
        )
    return jobs


def confirm(prompt: str) -> bool:
    answer = input(prompt).strip().lower()
    return answer in {"y", "yes"}


def parse_args(argv: Optional[Sequence[str]] = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run a list of commands across a list of network devices."
    )
    parser.add_argument("--user", help="SSH username (prompted if omitted)")
    parser.add_argument(
        "--devices-file", type=Path, help="Path to devices list (prompted if omitted)"
    )
    parser.add_argument(
        "--commands-file", type=Path, help="Path to commands list (prompted if omitted)"
    )
    parser.add_argument(
        "--snmp-community",
        default=os.environ.get("SNMP_COMMUNITY"),
        help="SNMP v2c community for device-type detection "
        "(or set SNMP_COMMUNITY env var)",
    )
    parser.add_argument(
        "--config",
        action="store_true",
        help="Run commands in config mode (otherwise only show-style commands allowed)",
    )
    parser.add_argument(
        "--yes",
        action="store_true",
        help="Skip the interactive 'Proceed?' confirmation prompt",
    )
    parser.add_argument(
        "--session-log",
        type=Path,
        default=DEFAULT_SESSION_LOG,
        help="Where to write the JSON session summary",
    )
    parser.add_argument("--verbose", "-v", action="store_true")
    return parser.parse_args(argv)


def _prompt_path(label: str, value: Optional[Path]) -> Path:
    if value is not None:
        path = value
    else:
        path = Path(input(f"{label}: ").strip())
    if not path.is_file():
        raise FileNotFoundError(f"{label} not found: {path}")
    return path


def main(argv: Optional[Sequence[str]] = None) -> int:
    args = parse_args(argv)
    configure_root_logging(args.verbose)

    username = args.user or input("User: ")
    password = getpass("Password: ")

    devices_path = _prompt_path("Devices File", args.devices_file)
    commands_path = _prompt_path("Commands File", args.commands_file)

    hosts = parse_devices_file(devices_path)
    commands = parse_commands_file(commands_path)

    if not hosts:
        logger.error("No devices to process")
        return 1
    if not commands:
        logger.error("No commands to run")
        return 1

    cmd_list = "\n        - ".join([""] + commands)
    print(
        f"\n{SEP_MAJOR}\nTotal devices: {len(hosts)}"
        f"\nCommand(s):{cmd_list}\n{SEP_MAJOR}\n"
    )
    if not args.yes and not confirm("Proceed? [y/n]: "):
        print("Exiting.. ")
        return 0

    print("=" * 75)
    start = datetime.now()

    jobs = build_jobs(hosts, commands, username, password, args.snmp_community)
    results = [execute_job(job, config_mode=args.config) for job in jobs]

    end = datetime.now()
    completed = [r for r in results if r.complete]
    failed = [r for r in results if not r.complete]

    print(f"Start Time: {start}\nEnd Time: {end}\nTotal Time: {end - start}")
    print("=" * 25)
    print(
        f"Total in: {len(hosts)}\nTotal Processed: {len(results)}"
        f"\nTotal Completed: {len(completed)}\nTotal Failed: {len(failed)}"
        f"\nErrors: {json.dumps([r.to_dict() for r in failed], indent=4)}"
    )

    args.session_log.write_text(
        json.dumps([r.to_dict() for r in results], indent=2)
    )
    return 0 if not failed else 2


if __name__ == "__main__":
    sys.exit(main())
