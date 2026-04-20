# Network Device Automation

Bulk-execute commands across a list of network devices over SSH, with optional
SNMP-based device-type autodetection. Thin wrapper over
[Netmiko](https://github.com/ktbyers/netmiko) with sensible defaults, per-device
logs, a JSON session summary, and opt-in parallelism.

## Quick start

```bash
git clone https://github.com/antonflor/NetworkDeviceAutomation.git
cd NetworkDeviceAutomation
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
```

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

Run it:

```bash
python NetworkDeviceAutomation.py \
    --user admin \
    --devices-file devices.txt \
    --commands-file commands.txt \
    --concurrency 8 \
    --yes
```

## Requirements

- Python 3.9+
- [Netmiko](https://github.com/ktbyers/netmiko) 4.x (installed by `requirements.txt`)
- `ping` on `PATH` (optional — reachability checks are skipped if it's missing)

## Usage

### Fully interactive (legacy behaviour)

```bash
python NetworkDeviceAutomation.py
```

Prompts for user, password, devices file, and commands file. Any flag you
pass on the command line replaces the corresponding prompt.

### Read-only commands (default)

Only `show` / `display` / `get` style commands are accepted. Anything else
is rejected up front — you can't change config by accident.

```bash
python NetworkDeviceAutomation.py \
    --user admin \
    --devices-file devices.txt \
    --commands-file commands.txt \
    --yes
```

### Pushing configuration changes

Pass `--config` to run the command list via netmiko's `send_config_set`:

```bash
python NetworkDeviceAutomation.py \
    --user admin \
    --devices-file devices.txt \
    --commands-file changes.txt \
    --config
```

### Parallel execution

`--concurrency N` runs N devices in parallel via a `ThreadPoolExecutor`.
Default is `1` (sequential). SSH/SNMP are I/O-bound, so 8–16 is a sensible
starting point for large inventories. Results stay in input order in the
session summary.

```bash
python NetworkDeviceAutomation.py --concurrency 16 ...
```

### SNMP-based device-type autodetect

If you supply an SNMP community, detection tries SNMP first (faster than
SSH autodetect) before falling back to SSH. Never hardcode the community
in source — pass it explicitly:

```bash
python NetworkDeviceAutomation.py --snmp-community public ...
# or
SNMP_COMMUNITY=public python NetworkDeviceAutomation.py ...
```

### All flags

```
--user USER              SSH username (prompted if omitted)
--devices-file PATH      Inventory file (prompted if omitted)
--commands-file PATH     Command list (prompted if omitted)
--snmp-community STR     Enables SNMP detection (or set SNMP_COMMUNITY env var)
--config                 Run commands in config mode via send_config_set
--concurrency N          Parallel devices (default 1)
--yes                    Skip the "Proceed? [y/n]" confirmation prompt
--session-log PATH       Override the JSON summary location
--verbose, -v            Debug logging
```

## File formats

- **devices file** — one host per line. `name ip` is allowed (the IP wins).
  Blank lines and `#`-comments are skipped.
- **commands file** — one command per line. Blank lines and `#`-comments
  are skipped.

## Output

Written to the current working directory:

- `<host>.log` — per-device log: connection events, commands run, raw output.
- `any_automate.log.<timestamp>` — JSON array summarising every device's
  result (`device`, `complete`, `error`). Override the path with
  `--session-log`.

## Exit codes

| Code | Meaning |
|---|---|
| `0` | All devices succeeded (or the user cancelled at the prompt). |
| `1` | Bad input: missing files, empty devices/commands list. |
| `2` | At least one device failed. |

These slot cleanly into cron or CI.

## Development

```bash
pip install -r requirements-dev.txt
pytest -q           # unit tests (netmiko is stubbed — no real deps needed)
ruff check .        # lint
python -m py_compile NetworkDeviceAutomation.py
```

CI runs the same three checks across Python 3.9–3.12 on every push and PR
(see `.github/workflows/ci.yml`).

## Contributing

PRs welcome. Please keep changes small, add tests for non-trivial logic,
and make sure `pytest -q` and `ruff check .` are green locally before
opening a PR.

## License

[MIT](LICENSE).
