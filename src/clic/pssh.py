#!/usr/bin/env python3
import shlex, subprocess
import time
import os
import getpass

sshOpts = shlex.split('-o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null -o LogLevel=error')

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
    cmdarry = []
    if keyowner != getpass.getuser():
        cmdarry = ['sudo']
    ssh = subprocess.Popen(cmdarry + ['ssh', '-i', os.path.expanduser('~' + keyowner) + '/.ssh/id_rsa'] + sshOpts + ['{0}@{1}'.format(user, host), command],
            shell=False, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    return [''.join([byte.decode('utf-8') for byte in ssh.stdout.readlines()]),
            ''.join([byte.decode('utf-8') for byte in ssh.stderr.readlines()])]

def copy(keyowner, user, host, pathOrig, pathDest):
    cmdarry = []
    if keyowner != getpass.getuser():
        cmdarry = ['sudo']
    scp = subprocess.Popen(cmdarry + ['scp', '-i', os.path.expanduser('~' + keyowner) + '/.ssh/id_rsa'] + sshOpts + [pathOrig, '{0}@{1}:{2}'.format(user, host, pathDest)],
            shell=False, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    return [''.join([byte.decode('utf-8') for byte in scp.stdout.readlines()]),
            ''.join([byte.decode('utf-8') for byte in scp.stderr.readlines()])]

def main():
    import argparse
    import re
    parser = argparse.ArgumentParser(description='Remotely execute commands using ssh')
    from clic import version
    parser.add_argument('-v', '--version', action='version', version=version.__version__)
    parser.add_argument('--key', metavar='KEY_OWNER', nargs=1, help='use the key in KEY_OWNER\'s ~/.ssh directory when connecting to USER@HOST. Otherwise, pssh uses the key of the user that executes pssh.')
    parser.add_argument('userhost', metavar='USER@HOST', nargs=1, help='connect to USER at HOST')
    group = parser.add_mutually_exclusive_group()
    group.add_argument('--canconnect', action='store_true', help='tests if USER can passwordlessly ssh to HOST. Prints "True" on a successful connection, or "False" otherwise.')
    group.add_argument('--command', metavar='CMD', nargs=1, help='execute CMD as USER on HOST')
    group.add_argument('--copy', metavar=('ORIG', 'DEST'), nargs=2, help='copy ORIG on localhost to DEST on HOST')
    args = parser.parse_args()
    
    [user, host] = args.userhost[0].split('@')

    if not args.key:
        args.key = [getpass.getuser()]

    if args.canconnect:
        print(canConnect(args.key[0], user, host))
    elif args.command:
        print(''.join(run(args.key[0], user, host, args.command[0])), end='')
    else:
        print(''.join(copy(args.key[0], user, host, args.copy[0], args.copy[1])), end='')
