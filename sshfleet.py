#!/usr/bin/env python3
"""sshfleet — bulk-execute commands across a fleet of network devices via SSH (netmiko).

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
from concurrent.futures import ThreadPoolExecutor, as_completed
from contextlib import contextmanager
from dataclasses import dataclass, field, asdict
from functools import lru_cache
from datetime import datetime
from getpass import getpass
from pathlib import Path
from typing import Iterable, Iterator, List, Optional, Sequence

from netmiko import ConnectHandler, SSHDetect
from netmiko.exceptions import NetmikoAuthenticationException, NetmikoTimeoutException

__version__ = "2.0.0"

warnings.filterwarnings("ignore", category=DeprecationWarning, module=r".*paramiko.*")

# SIGPIPE is POSIX-only; SIGINT exists everywhere but the default handler is
# already what we want, so we only adjust what's actually needed per-platform.
if hasattr(__import__("signal"), "SIGPIPE"):
    import signal

    signal.signal(signal.SIGPIPE, signal.SIG_DFL)


SESSION_TIMESTAMP = datetime.now().strftime("%Y%m%d_%H%M%S")

SEP_MAJOR = "=" * 50
SEP_MINOR = "=" * 5

logger = logging.getLogger("sshfleet")


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
    log_dir: Path = field(default_factory=Path.cwd)


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


def _device_logger(host: str, log_dir: Optional[Path] = None) -> logging.Logger:
    """Per-device logger that appends to ``<host>.log`` in ``log_dir`` (cwd default)."""
    name = f"sshfleet.device.{host}"
    log = logging.getLogger(name)
    if not log.handlers:
        handler = logging.FileHandler((log_dir or Path.cwd()) / f"{host}.log")
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


@lru_cache(maxsize=None)
def _snmp_detect_cls():
    """SNMPDetect is optional: it moved out of netmiko's top level and needs pysnmp."""
    try:
        from netmiko.snmp_autodetect import SNMPDetect

        return SNMPDetect
    except ImportError:
        logger.warning(
            "SNMP detection unavailable (install the 'pysnmp' extra: "
            "pip install sshfleet[snmp]); falling back to SSH autodetect"
        )
        return None


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
        snmp_detect = _snmp_detect_cls() if snmp_community else None
        if snmp_detect is not None:
            try:
                guess = snmp_detect(
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
    dev_log = _device_logger(job.host, job.log_dir)
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
    device_type: Optional[str] = None,
    skip_ping: bool = False,
    log_dir: Optional[Path] = None,
) -> List[DeviceJob]:
    """``device_type`` skips autodetection; ``skip_ping`` skips reachability checks."""
    log_dir = log_dir or Path.cwd()
    jobs: List[DeviceJob] = []
    for host in hosts:
        if not skip_ping and not ping_check(host):
            jobs.append(
                DeviceJob(
                    host=host,
                    username=username,
                    password=password,
                    commands=list(commands),
                    reachable=False,
                    error="Host unreachable",
                    log_dir=log_dir,
                )
            )
            continue

        dtype = device_type or detect_device_type(
            host, username, password, snmp_community
        )
        jobs.append(
            DeviceJob(
                host=host,
                username=username,
                password=password,
                commands=list(commands),
                reachable=True,
                device_type=dtype,
                error=None if dtype else "Unable to determine device type",
                log_dir=log_dir,
            )
        )
    return jobs


def confirm(prompt: str) -> bool:
    answer = input(prompt).strip().lower()
    return answer in {"y", "yes"}


def run_jobs(
    jobs: Sequence[DeviceJob],
    config_mode: bool,
    concurrency: int,
) -> List[DeviceResult]:
    """Execute ``jobs``. ``concurrency=1`` preserves sequential behaviour.

    When running concurrently, results are returned in the same order as
    ``jobs`` so the session summary stays deterministic.
    """
    if concurrency < 1:
        raise ValueError("concurrency must be >= 1")
    if concurrency == 1 or len(jobs) <= 1:
        return [execute_job(job, config_mode=config_mode) for job in jobs]

    results: List[Optional[DeviceResult]] = [None] * len(jobs)
    with ThreadPoolExecutor(max_workers=concurrency) as pool:
        futures = {
            pool.submit(execute_job, job, config_mode): idx
            for idx, job in enumerate(jobs)
        }
        for fut in as_completed(futures):
            idx = futures[fut]
            results[idx] = fut.result()
    return [r for r in results if r is not None]


def parse_args(argv: Optional[Sequence[str]] = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run a list of commands across a list of network devices."
    )
    parser.add_argument(
        "--version", action="version", version=f"%(prog)s {__version__}"
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
        "--device-type",
        help="Netmiko device type for every host (e.g. cisco_ios); "
        "skips SNMP/SSH autodetection entirely",
    )
    parser.add_argument(
        "--config",
        action="store_true",
        help="Run commands in config mode (otherwise only show-style commands allowed)",
    )
    parser.add_argument(
        "--no-ping",
        action="store_true",
        help="Skip the ICMP reachability check before connecting",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print the execution plan and exit without connecting to anything",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path.cwd(),
        help="Directory for per-device logs and the session summary (default: cwd)",
    )
    parser.add_argument(
        "--yes",
        action="store_true",
        help="Skip the interactive 'Proceed?' confirmation prompt",
    )
    parser.add_argument(
        "--session-log",
        type=Path,
        help="Where to write the JSON session summary "
        "(default: <output-dir>/session_<timestamp>.json)",
    )
    parser.add_argument(
        "--concurrency",
        type=int,
        default=1,
        help="Number of devices to process in parallel (default: 1)",
    )
    parser.add_argument("--verbose", "-v", action="store_true")
    args = parser.parse_args(argv)
    if args.concurrency < 1:
        parser.error("--concurrency must be >= 1")
    return args


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

    # Validate all inputs before prompting for credentials so a typo'd path
    # or a disallowed command never costs the user a password prompt.
    try:
        devices_path = _prompt_path("Devices File", args.devices_file)
        commands_path = _prompt_path("Commands File", args.commands_file)
    except FileNotFoundError as exc:
        logger.error("%s", exc)
        return 1

    hosts = parse_devices_file(devices_path)
    commands = parse_commands_file(commands_path)

    if not hosts:
        logger.error("No devices to process")
        return 1
    if not commands:
        logger.error("No commands to run")
        return 1

    if not args.config:
        disallowed = [c for c in commands if not _is_show_command(c)]
        if disallowed:
            logger.error(
                "Non-show command(s) not allowed without --config: %s",
                ", ".join(repr(c) for c in disallowed),
            )
            return 1

    mode = "config" if args.config else "read-only"
    cmd_list = "\n        - ".join([""] + commands)
    print(
        f"\n{SEP_MAJOR}\nTotal devices: {len(hosts)}"
        f"\nMode: {mode}\nConcurrency: {args.concurrency}"
        f"\nCommand(s):{cmd_list}\n{SEP_MAJOR}\n"
    )
    if args.dry_run:
        print("Dry run - nothing executed.")
        return 0
    if not args.yes and not confirm("Proceed? [y/n]: "):
        print("Exiting.. ")
        return 0

    username = args.user or input("User: ")
    password = os.environ.get("SSHFLEET_PASSWORD") or getpass("Password: ")

    output_dir = args.output_dir
    output_dir.mkdir(parents=True, exist_ok=True)
    session_log = args.session_log or output_dir / f"session_{SESSION_TIMESTAMP}.json"

    print("=" * 75)
    start = datetime.now()

    jobs = build_jobs(
        hosts,
        commands,
        username,
        password,
        args.snmp_community,
        device_type=args.device_type,
        skip_ping=args.no_ping,
        log_dir=output_dir,
    )
    results = run_jobs(jobs, config_mode=args.config, concurrency=args.concurrency)

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

    session_log.write_text(json.dumps([r.to_dict() for r in results], indent=2))
    return 0 if not failed else 2


if __name__ == "__main__":
    sys.exit(main())
