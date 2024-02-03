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

- Python 3.x
- Netmiko library

## Installation

1. Ensure Python 3.x is installed on your system.

2. Install Netmiko using pip:

   ```
   pip install netmiko
   ```

## Usage

1. Modify the script to include the necessary device IPs, commands, and credentials.

2. Run the script:

   ```
   python NetworkDeviceAutomation.py
   ```

3. Follow the on-screen prompts for user credentials and other inputs.

## Logs

Logs are generated in the current working directory, named `any_automate.log`, followed by a timestamp.

## Contributing

Contributions to this project are welcome. Please ensure to update tests as appropriate.

## License

This project is licensed under the MIT License - see the [LICENSE.md](https://chat.openai.com/c/LICENSE.md) file for details.
