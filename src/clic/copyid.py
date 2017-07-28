#!/usr/bin/env python3
from pathlib import Path
import os
import re
import pwd

# keys = [[keyUser, keyValue], ...]
keys = []

from clic import cloud as api
cloud = api.getCloud()

def refresh(append):
    global keys
    keys = []
    if append:
        keys = cloud.getSshKeys()

def copy(generate, localuser, remoteuser):
    global keys
    key = Path('/home/' + localuser + '/.ssh/id_rsa.pub')
    if not key.is_file() and generate:
        # Generate a key
        print('generating for ' + localuser)
        os.system('su - ' + localuser + ' -c "ssh-keygen -t rsa -N \'\' -f ~/.ssh/id_rsa"')
    if key.is_file():
        with open(str(key), 'r') as keyFile:
            newkey = [remoteuser, keyFile.read().strip()]
            if not newkey in keys:
                keys.append(newkey)

def copyAll(generate):
    users = []
    for user in Path('/home').iterdir():
        try:
            pwd.getpwnam(user.parts[-1])
        except KeyError:
            continue
        if user.is_dir():
            copy(generate, user.parts[-1], user.parts[-1])

def send():
    global keys
    cloud.setSshKeys(keys)

def main():
    import argparse
    parser = argparse.ArgumentParser(description='Copy public keys to cloud computers')
    from clic import version
    parser.add_argument('-v', '--version', action='version', version=version.__version__)
    parser.add_argument('-g', '--generate', action='store_true', help='generate public keys for users without one')
    parser.add_argument('-a', '--append', action='store_true', help='append keys to existing keys (default: replace)')
    parser.add_argument('-u', metavar=('LOCAL_USER', 'REMOTE_USER'), nargs=2, help='allow ssh from LOCAL_USER to REMOTE_USER')
    parser.add_argument('users', metavar='USER', nargs='*', help='allow ssh from USER on localhost to USER on remotehost (default: if called with no -u, allows all users with home directories in /home)')
    args = parser.parse_args()
    
    refresh(args.append)
    if args.u:
        copy(args.generate, args.u[0], args.u[1])
    elif len(args.users) == 0:
        copyAll(args.generate)
    for user in args.users:
        copy(args.generate, user, user)
    send()
