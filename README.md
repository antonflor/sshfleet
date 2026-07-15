# sshfleet

Bulk-execute commands across a fleet of network devices over SSH, with
optional SNMP-based device-type autodetection. Thin wrapper over
[Netmiko](https://github.com/ktbyers/netmiko) with sensible defaults,
per-device logs, a JSON session summary, and opt-in parallelism.

## Install

The cleanest way is [pipx](https://pipx.pypa.io/), which gives you an isolated
`sshfleet` command:

```bash
pipx install git+https://github.com/antonflor/sshfleet.git
sshfleet --version
```

Or plain pip into a venv:

```bash
git clone https://github.com/antonflor/sshfleet.git
cd sshfleet
python3 -m venv .venv && source .venv/bin/activate
pip install .
```

Either way you get the `sshfleet` command. Running the script directly
(`python sshfleet.py`) still works too.

## Quick start

Create an inventory file and a command file:

```text
# devices.txt — one host per line; "name ip" also OK (IP wins); # for comments
core-sw1 10.0.0.1
10.0.0.2
```

```text
# commands.txt — one command per line
show version
show ip interface brief
```

Preview what would run, then run it:

```bash
sshfleet --devices-file devices.txt --commands-file commands.txt --dry-run
sshfleet --user admin --devices-file devices.txt --commands-file commands.txt \
    --concurrency 8 --yes
```

## Requirements

- Python 3.9+
- [Netmiko](https://github.com/ktbyers/netmiko) 4.x (installed automatically)
- `ping` on `PATH` (optional — reachability checks are skipped if it's
  missing, or pass `--no-ping`)

## Usage

### Fully interactive (legacy behaviour)

```bash
sshfleet
```

Prompts for devices file, commands file, user, and password. Any flag you
pass on the command line replaces the corresponding prompt.

### Read-only commands (default)

Only `show` / `display` / `get` style commands are accepted. Anything else is
rejected up front — before you're even asked for a password — so you can't
change config by accident.

### Pushing configuration changes

Pass `--config` to run the command list via netmiko's `send_config_set`:

```bash
sshfleet --user admin --devices-file devices.txt --commands-file changes.txt --config
```

### Skipping autodetection

Device-type detection (SNMP and/or SSH) is the slowest part of a run. If your
inventory is homogeneous, name the
[netmiko device type](https://github.com/ktbyers/netmiko/blob/develop/PLATFORMS.md)
directly:

```bash
sshfleet --device-type cisco_ios ...
```

### Parallel execution

`--concurrency N` runs N devices in parallel via a thread pool. Default is `1`
(sequential). SSH/SNMP are I/O-bound, so 8–16 is a sensible starting point for
large inventories. Results stay in input order in the session summary.

### Non-interactive / scripted runs

For cron or CI, combine `--yes` (skip confirmation) with the
`SSHFLEET_PASSWORD` environment variable (skip the password prompt). Prefer
injecting it from a secret store; avoid writing it into shell history or
scripts.

```bash
SSHFLEET_PASSWORD="$(vault kv get -field=pw net/creds)" \
    sshfleet --user admin --devices-file devices.txt --commands-file commands.txt \
        --device-type cisco_ios --yes --output-dir /var/log/sshfleet
```

### SNMP-based device-type autodetect

If you supply an SNMP community, detection tries SNMP first (faster than SSH
autodetect) before falling back to SSH. SNMP support needs the optional
`pysnmp` dependency — install with `pip install sshfleet[snmp]` (or
`pipx install "sshfleet[snmp] @ git+https://github.com/antonflor/sshfleet.git"`).
Never hardcode the community in source — pass it explicitly:

```bash
sshfleet --snmp-community public ...
# or
SNMP_COMMUNITY=public sshfleet ...
```

### All flags

```
--user USER              SSH username (prompted if omitted)
--devices-file PATH      Inventory file (prompted if omitted)
--commands-file PATH     Command list (prompted if omitted)
--device-type TYPE       Netmiko device type for all hosts; skips autodetection
--snmp-community STR     Enables SNMP detection (or set SNMP_COMMUNITY env var)
--config                 Run commands in config mode via send_config_set
--concurrency N          Parallel devices (default 1)
--no-ping                Skip the ICMP reachability check
--dry-run                Print the plan and exit; no credentials needed
--yes                    Skip the "Proceed? [y/n]" confirmation prompt
--output-dir PATH        Directory for logs + session summary (default: cwd)
--session-log PATH       Override the JSON summary location
--version                Print version and exit
--verbose, -v            Debug logging
```

Environment variables: `SSHFLEET_PASSWORD` (SSH password), `SNMP_COMMUNITY`.

## File formats

- **devices file** — one host per line. `name ip` is allowed (the IP wins).
  Blank lines and `#`-comments are skipped.
- **commands file** — one command per line. Blank lines and `#`-comments are
  skipped.

## Output

Written to `--output-dir` (default: current working directory):

- `<host>.log` — per-device log: connection events, commands run, raw output.
- `session_<timestamp>.json` — JSON array summarising every device's result
  (`device`, `complete`, `error`). Override the path with `--session-log`.

## Exit codes

| Code | Meaning |
|---|---|
| `0` | All devices succeeded (or dry run, or the user cancelled at the prompt). |
| `1` | Bad input: missing files, empty or disallowed devices/commands list. |
| `2` | At least one device failed. |

These slot cleanly into cron or CI.

## Scope

sshfleet is deliberately small: run a list of commands across an inventory of
*network devices* (switches, routers, firewalls — anything netmiko speaks).
It is not a general server-configuration tool; for Linux fleet management,
key distribution, and orchestration, reach for Ansible/Fabric/pssh.

## Development

```bash
pip install -e .[dev]
pytest -q           # unit tests (netmiko is stubbed — no real devices needed)
ruff check .        # lint
```

CI runs lint, tests, and a package-install smoke test across Python 3.9–3.13
on every push and PR (see `.github/workflows/ci.yml`).

## Contributing

PRs welcome. Please keep changes small, add tests for non-trivial logic, and
make sure `pytest -q` and `ruff check .` are green locally before opening a PR.

## License

[MIT](LICENSE).
