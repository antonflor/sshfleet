#!/usr/bin/env python3

'''
Script for automated network device interactions
Version: 3.0
Created: 2019-10-24
Updated: 2020-07-14
'''

import os
import sys
import signal
import subprocess
import json
from datetime import datetime
from getpass import getpass
from netmiko import ConnectHandler, ssh_exception
from netmiko.ssh_autodetect import SSHDetect
from netmiko.snmp_autodetect import SNMPDetect

# Suppress warnings from paramiko
import warnings
warnings.filterwarnings(action='ignore', module='.*paramiko.*')

# Handle signals
signal.signal(signal.SIGPIPE, signal.SIG_DFL)  # IOError: Broken pipe
signal.signal(signal.SIGINT, signal.SIG_DFL)   # KeyboardInterrupt: Ctrl-C

# Global variables
CUR_DIR = os.getcwd()
LOGFILE = f'{CUR_DIR}/any_automate.log.{datetime.now().strftime("%Y%m%d_%H%M%S")}'

# Function definitions
def get_time():
    return datetime.now().strftime('%Y-%m-%d %H:%M:%S.%f')

def add_log(ip, log_type, message):
    with open(f'{ip}.log', 'a') as f:
        log = f'{get_time()} - {ip} {log_type} {message}\n'
        f.write(log)

# ... [Other function definitions remain the same, with minor adjustments for Python 3 compatibility]

# Main execution
if __name__ == '__main__':
    do_stuff()
