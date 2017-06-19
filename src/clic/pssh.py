#!/usr/bin/env python3
import shlex, subprocess
import time
import os
import getpass

def canConnect(keyowner, user, host):
    from multiprocessing import Process
    import signal
    class timeout:
        def __init__(self, seconds=1, error_message='Timeout'):
            self.seconds = seconds
            self.error_message = error_message
        def handle_timeout(self, signum, frame):
            raise TimeoutError(self.error_message)
        def __enter__(self):
            signal.signal(signal.SIGALRM, self.handle_timeout)
            signal.alarm(self.seconds)
        def __exit__(self, type, value, traceback):
            signal.alarm(0)
    
    out = []
    try:
        with timeout(seconds=5):
            out = run(keyowner, user, host, 'exit')
    except TimeoutError:
        return False
    return out[1] == ''

def run(keyowner, user, host, command):
    sshOpts = '-o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null -o LogLevel=error'
    cmdarry = []
    if keyowner != getpass.getuser():
        cmdarry = ['sudo']
    ssh = subprocess.Popen(cmdarry + ['ssh', '-i', os.path.expanduser('~' + keyowner) + '/.ssh/id_rsa'] + shlex.split(sshOpts) + ['{0}@{1}'.format(user, host), command],
            shell=False, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    return [''.join([byte.decode('utf-8') for byte in ssh.stdout.readlines()]),
            ''.join([byte.decode('utf-8') for byte in ssh.stderr.readlines()])]

def main():
    import argparse
    import re
    parser = argparse.ArgumentParser(description='Remotely execute commands using ssh')
    parser.add_argument('--key', metavar='KEY_OWNER', nargs=1, help='use the key in KEY_OWNER\'s ~/.ssh directory when connecting to USER@HOST. Otherwise, pssh uses the key of the user that executes pssh.')
    parser.add_argument('--canconnect', action='store_true', help='tests if USER can passwordlessly ssh to HOST. Prints "True" on a successful connection, or "False" otherwise.')
    parser.add_argument('userhost', metavar='USER@HOST', nargs=1, help='connect to USER at HOST')
    parser.add_argument('command', metavar='CMD', nargs='?', help='execute commands as USER on HOST')
    args = parser.parse_args()
    # Error checking
    if (args.canconnect and args.command) or (not args.canconnect and not args.command):
        parser.error('must specify --canconnect xor COMMAND')
    
    [user, host] = args.userhost[0].split('@')

    if not args.key:
        args.key = [getpass.getuser()]

    if args.canconnect:
        print(canConnect(args.key[0], user, host))
    else:
        print(''.join(run(args.key[0], user, host, args.command)), end='')
