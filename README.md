# Network Device Automation Script

## Overview

This script automates interactions with network devices using SSH and SNMP protocols. It's designed to facilitate network administrators in managing and configuring multiple devices efficiently.

## Features

- **Device Type Autodetection**: Determines the type of network devices using SSH and SNMP.
- **Command Execution**: Executes a list of commands on specified devices.
- **Configuration Management**: Manages device configurations.
- **Logging**: Maintains logs for operations and errors.
- **User Interaction**: Prompts for user credentials and command inputs securely.
- **Ping Check**: Verifies network reachability of devices before processing.
- **Error Handling**: Implements robust error handling and retry mechanisms.

## Prerequisites

- Python 3.8+
- [Netmiko](https://github.com/ktbyers/netmiko) 4.x

## Installation

```
pip install -r requirements.txt
```

## Usage

Fully interactive (legacy behaviour):

```
python NetworkDeviceAutomation.py
```

Or with flags (any flag you omit is prompted for):

```
python NetworkDeviceAutomation.py \
    --user admin \
    --devices-file devices.txt \
    --commands-file commands.txt \
    --snmp-community public \
    --yes
```

By default only `show` / `display` / `get` style commands are accepted. To
push configuration changes, pass `--config` (commands are then run via
netmiko's `send_config_set`).

Use `--concurrency N` to process N devices in parallel (default `1`, which
preserves the original sequential behaviour). Results are still reported in
input order. SSH and SNMP are I/O-bound so a `ThreadPoolExecutor` works
well; 8–16 is a reasonable starting point for large inventories.

### File formats

- **devices file**: one host per line. `name ip` is allowed (the IP wins).
  Blank lines and `#`-comments are skipped.
- **commands file**: one command per line. Blank lines and `#`-comments
  are skipped.

## Logs

- Per-device logs: `<host>.log` in the working directory.
- Per-session JSON summary: `any_automate.log.<timestamp>` (override with
  `--session-log`).

## Exit codes

- `0` — all devices succeeded (or user cancelled at the prompt).
- `1` — bad input (no devices/commands or missing files).
- `2` — at least one device failed.

## Contributing

Contributions are welcome. Please add tests for non-trivial logic.

## License

MIT — see `LICENSE` if present.
