# NetworkDeviceAutomation.py

## Overview

NetworkDeviceAutomation.py is a Python 3 script designed for automating network device management tasks. It utilizes SSH and SNMP protocols to interact with a variety of network devices, enabling efficient execution of commands and configuration management. This script is particularly useful for network administrators and IT professionals looking to streamline their network operations.

## Features

- **Device Type Autodetection**: Automatically identifies the type of network device using SSH and SNMP.
- **Command Execution**: Executes a predefined list of commands on multiple devices.
- **Configuration Management**: Facilitates efficient management of device configurations.
- **Logging and Error Handling**: Maintains logs for operations and errors for better insight and troubleshooting.
- **User Interaction**: Securely prompts for user credentials and command inputs.
- **Ping Check**: Verifies network reachability of devices before processing.
- **Robust Error Handling**: Includes retry mechanisms for enhanced reliability.

## Prerequisites

- Python 3.x
- `netmiko` library
- Access to network devices compatible with SSH and SNMP protocols.

## Installation

1. Clone the repository:

   ```
   git clone https://github.com/antonflor/NetworkDeviceAutomation.git
   ```

2. Navigate to the script directory:

   ```
   cd NetworkDeviceAutomation
   ```

3. Install required Python libraries:

   ```
   pip install -r requirements.txt
   ```

## Usage

1. Prepare a list of devices and commands in separate text files.

2. Run the script:

   ```
   python3 NetworkDeviceAutomation.py
   ```

3. Follow the on-screen prompts to enter user credentials and file names for devices and commands.

## Configuration

- Modify the script as needed to accommodate specific network environments or device types.
- Update the command list file to include the commands you wish to execute on the network devices.

## Contributing

Contributions to this project are welcome. Please fork the repository and submit a pull request with your changes.

## License

This project is licensed under the MIT License.

## Support

For support or queries, please open an issue in the GitHub repository issue tracker.

------

*Note: This script is intended for professional use. Please ensure you have proper authorization to access and manage the network devices targeted by this script.*
