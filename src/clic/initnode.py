#!/usr/bin/python3
import os
from pathlib import Path
from pwd import getpwnam
from clic import pssh

def init(user, host, skipsync):
    # Sync UIDs and GIDs
    for path in Path('/home').iterdir():
        if path.is_dir():
            localUser = path.parts[-1]
            uid = getpwnam(localUser).pw_uid
            gid = getpwnam(localUser)[2]
            pssh.run(user, user, host, 'nohup sudo su - -c \'usermod -o -u {1} {0}; groupmod -o -g {2} {0}\' &> /dev/null &'.format(localUser, uid, gid))
    
    hostname = os.popen('hostname -s').read().strip()
    if not skipsync:
        import ipgetter
        pssh.run(user, user, host, 'sudo clic-synchosts {0}:{1}'.format(hostname, ipgetter.myip()))
    pssh.run(user, user, host, 'sudo clic-mount {0}@{1} &'.format(user, hostname))

def main():
    import argparse
    import re
    parser = argparse.ArgumentParser(description='Intitialize a node for use with clic by configuring its /etc/hosts and nfs. This script is run from the head node.')
    parser.add_argument('userhost', metavar='USER@HOST', nargs=1, help='passwordless ssh exists both ways between USER@localhost and USER@HOST')
    args = parser.parse_args()
    # Error checking
    if not re.search('^\w+@\w+$', args.userhost[0]):
        parser.error('incorrect formatting: ' + args.userhost[0])
    [user, host] = args.userhost[0].split('@')
    init(user, host)
