# Project status

**Version:** 2.0.0 · **Last updated:** 2026-09-05

## Where things stand

sshfleet is feature-complete for its intended scope and packaged for
installation. CI is green across Python 3.9–3.13 (lint, 31 unit tests, and a
`pip install .` smoke test that verifies the console command works against a
real netmiko install).

### Done

- **Packaging** — `pyproject.toml`; installs via `pipx`/`pip` and exposes the
  `sshfleet` console command. Optional `sshfleet[snmp]` extra pulls in pysnmp.
- **Renamed** from NetworkDeviceAutomation to sshfleet (module, package,
  command, docs, CI).
- **Safety defaults** — read-only unless `--config` is passed; inventory,
  command list, and command safety are all validated *before* any credential
  prompt, so a typo never costs a password entry.
- **Quality-of-life flags** — `--dry-run`, `--device-type` (skips slow
  autodetection), `--no-ping`, `--output-dir`, `--version`, plus the
  `SSHFLEET_PASSWORD` environment variable for scripted runs.
- **Output** — per-device logs plus a `session_<timestamp>.json` summary,
  both written to `--output-dir`. Exit codes are cron/CI friendly (0 / 1 / 2).
- **SNMP is optional** — `SNMPDetect` is imported lazily and degrades to SSH
  autodetect with a warning when pysnmp is absent, instead of failing at
  import time.

### Not yet validated

**sshfleet has not been exercised against real hardware in this round of
work.** Every test stubs netmiko out, which is what keeps the suite fast and
dependency-free, but it means the following paths are unproven in the field:

- SNMP detection against a live agent (needs the `snmp` extra installed)
- `--config` mode / `send_config_set` on actual devices
- Enable-mode and pager behaviour across vendors
- Concurrency against a large inventory (thread pool sizing, device-side
  session limits)

Treat the first real run as a test: single device, read-only, `--dry-run`
first.

## Next up

- [ ] Validate against real devices — read-only on one host, then a small
      batch, then `--concurrency`
- [ ] Add screenshots to `docs/` and reference them from the README
      (`--dry-run` plan output and a finished parallel run are the two that
      show the tool off best)
- [ ] Optional: publish to PyPI — the name is free and packaging is ready
- [ ] Possible additions, unscheduled: `--key-file` (SSH key auth),
      `--timeout`, YAML inventory support

## Scope

Deliberately narrow: run a list of commands across an inventory of *network
devices* — switches, routers, firewalls, anything netmiko speaks. It is not a
general server-configuration tool; for Linux fleet management, key
distribution, and orchestration, use Ansible/Fabric/pssh. See the Scope
section of the [README](../README.md).
