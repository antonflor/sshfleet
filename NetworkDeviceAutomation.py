#!/usr/bin/env python3

'''
Script for automated network device interactions
Version: 3.0
Updated: 2020-07-14
'''

import os
import json
import subprocess
import base64
from datetime import datetime
from getpass import getpass
from netmiko import ConnectHandler, SSHDetect, SNMPDetect
import warnings
warnings.filterwarnings(action='ignore', module='.*paramiko.*')

# Handle signals
import signal
signal.signal(signal.SIGPIPE, signal.SIG_DFL)  # IOError: Broken pipe
signal.signal(signal.SIGINT, signal.SIG_DFL)   # KeyboardInterrupt: Ctrl-C

# Global variables
CUR_DIR = os.getcwd()
LOGFILE = os.path.join(CUR_DIR, f'any_automate.log.{datetime.now().strftime("%Y%m%d_%H%M%S")}')

# Function definitions
def get_time():
    return datetime.now().strftime('%Y-%m-%d %H:%M:%S.%f')

def add_log(ip, log_type, message):
    with open(f'{ip}.log', 'a') as f:
        log = f'{get_time()} - {ip} {log_type} {message}\n'
        f.write(log)

def ping_check(ip):
    response = subprocess.call(['ping', '-c', '3', str(ip)])
    return 'reachable' if response == 0 else 'unreachable'

def get_info(info):
    return base64.b64decode(info).decode('utf-8') if info else None

def return_type(ip, usr, pwd, commu=None):
    commu = commu or get_info('c25tcG0zIQ==\n')
    ssh_info = {'device_type': 'autodetect', 'host': ip, 'username': usr, 'password': pwd}
    snmp_info = {'hostname': ip, 'community': commu, 'snmp_version': 'v2c'}

    for _ in range(3):  # up to 3 attempts
        try:
            guesser_snmp = SNMPDetect(**snmp_info)
            guess = guesser_snmp.autodetect()
            return guess
        except Exception as e_snmp:
            pass

        try:
            guesser_ssh = SSHDetect(**ssh_info)
            guess = guesser_ssh.autodetect()
            return guess
        except Exception as e_ssh:
            if _ == 2:  # last attempt
                add_log(ip, 'ERROR', f'SNMP Error: {e_snmp}, SSH Error: {e_ssh}')
                return None

def gather_device_info():
    usr = input('User: ')
    pwd = getpass('Password: ')
    dev_file = input('Devices File: ')
    cmds_file = input('Commands File: ')

    with open(dev_file, 'r') as df, open(cmds_file, 'r') as cf:
        devices = df.readlines()
        commands = cf.readlines()

    ret = {'stuff': [], 'in': len(devices), 'cmds': [cmd.strip() for cmd in commands if cmd]}
    for line in devices:
        host = line.strip().split()
        hn = host[1] if len(host) > 1 else host[0]
        pingresult = ping_check(hn)
        type_ = return_type(hn, usr, pwd) if pingresult == 'reachable' else None
        err = 'Unable to determine device type' if not type_ else None
        ret['stuff'].append({'device': hn, 'cmds': ret['cmds'], 'usr': usr, 'pwd': pwd, 'ping': pingresult, 'type': type_, 'error': err})

    return ret

def check_go(go):
    return go.lower() in ['y', 'yes']

def get_clean_commands(commands, type_):
    return ['do ' + c if type_ and 'cisco_ios' in type_ and c.startswith('show') else c for c in commands]

def get_clean_output(output):
    return ' '.join('\n   {}'.format(out) for out in output.split('\n'))

def do_things(**kwargs):
    dev = kwargs.get('device')
    cmds = kwargs.get('cmds')
    usr = kwargs.get('usr')
    pwd = kwargs.get('pwd')
    err = kwargs.get('error', '')
    device_type = kwargs.get('type')

    new_cmds = get_clean_commands(cmds, device_type)
    cmd_print = ' '.join('\n - {}'.format(command) for command in new_cmds)
    sep_one = '=' * 50
    sep_two = '=' * 5

    print(f'{get_time()} - {dev} - Processing..')
    add_session_log(dev, f'{get_time()} - Processing Device: {dev}')

    try:
        if err:
            raise RuntimeError(err)
        connecthandler = get_connecthandler(dev, usr, pwd, device_type)
        run_cmds = connecthandler.send_config_set(new_cmds)
        clean_out = get_clean_output(run_cmds)

        print(sep_two)
        print_stuff = f'Device:\n - {dev}\n{sep_two}\nCommands: {cmd_print}\n{sep_two}\nOutput: {clean_out}'
        print(print_stuff)
        add_session_log(dev, f'\n{sep_one}\n{get_time()} - Device Results:\n{sep_two}\n{print_stuff}')
        print(f'{sep_two}\n{dev} - Done\n{sep_one}')

        return {'complete': True, 'device': dev, 'error': ''}
    except Exception as e:
        error_message = f'\n{dev} - Broke..ERROR: {e}\n{sep_one}'
        print(error_message)
        add_session_log(dev, error_message)
        return {'complete': False, 'device': dev, 'error': str(e)}

def do_stuff():
    start_time = datetime.now()
    stuffs = gather_device_info()
    total_devices = stuffs.get('in', 0)
    cmds = stuffs.get('cmds', [])
    cmd_list = ' '.join('\n        - {}'.format(c) for c in cmds)
    sep = '=' * 50

    print(f'\n{sep}\nTotal devices: {total_devices}\nCommand(s): {cmd_list}\n{sep}\n')
    proceed = check_go(input('Proceed? [y/n]: '))
    if not proceed:
        print('Exiting.. ')
        sys.exit()

    print('=' * 75)
    results = [do_things(**device_info) for device_info in stuffs.get('stuff', [])]

    good = [g for g in results if g.get('complete')]
    bad = [b for b in results if not b.get('complete')]
    end_time = datetime.now()

    print(f'Start Time: {start_time}\nEnd Time: {end_time}\nTotal Time: {end_time - start_time}')
    print('=' * 25)
    print(f'Total in: {total_devices}\nTotal Processed: {len(results)}\nTotal Completed: {len(good)}\nTotal Failed: {len(bad)}\nErrors: {json.dumps(bad, indent=4)}')

    with open(LOGFILE, 'w') as lf:
        lf.write(json.dumps(results))

if __name__ == '__main__':
    do_stuff()
