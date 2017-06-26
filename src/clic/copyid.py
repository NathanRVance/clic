#!/usr/bin/env python3
from pathlib import Path
import os
import re

keys = ''

def refresh(append):
    global keys
    keys = ''
    if append:
        current = os.popen('gcloud compute project-info describe').read()
        match = re.search('key: sshKeys.*?kind:', current, re.DOTALL)
        if match:
            current = match.group(0)
            current = '\n'.join(current.split('\n')[1:-1])
            current = re.sub('\|-?\s*', '', current)
            current = re.sub('\s*value:\s*', '', current)
            current = re.sub('\n\s*', '\n', current)
            current = re.sub('\n(?=\S*@\S*)', ' ', current)
            current = re.sub('\^DELIM\^', '', current)
            current = re.sub(',', 'DELIM', current)
            keys = current + '\n'

def copy(generate, localuser, remoteuser):
    global keys
    key = Path('/home/' + localuser + '/.ssh/id_rsa.pub')
    if not key.is_file() and generate:
        # Generate a key
        print('generating for ' + localuser)
        os.system('su - ' + localuser + ' -c "ssh-keygen -t rsa -N \'\' -f ~/.ssh/id_rsa"')
    if key.is_file():
        with open(str(key), 'r') as keyFile:
            newkey = remoteuser + ":" + keyFile.read()
            if not re.search(re.escape(newkey.rstrip()), keys):
                keys += newkey
    

def copyAll(generate):
    users = []
    for user in Path('/home').iterdir():
        if user.is_dir():
            copy(generate, user.parts[-1], user.parts[-1])

def send():
    global keys
    keys = keys.rstrip() # Trim trailing newline
    os.system('gcloud compute project-info add-metadata --metadata=^DELIM^sshKeys=\'{0}\''.format(keys))
    print('gcloud compute project-info add-metadata --metadata=^DELIM^sshKeys=\'{0}\''.format(keys))

def main():
    import argparse
    parser = argparse.ArgumentParser(description='Copy public keys to cloud computers')
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
