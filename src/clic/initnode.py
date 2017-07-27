#!/usr/bin/python3
import os
from pathlib import Path
from pwd import getpwnam
from clic import pssh

def init(user, host, skipsync, cpus, disk, mem):
    # Sync UIDs and GIDs
    for path in Path('/home').iterdir():
        if path.is_dir():
            localUser = path.parts[-1]
            try:
                uid = getpwnam(localUser).pw_uid
                gid = getpwnam(localUser).pw_gid
                pssh.run(user, user, host, 'nohup sudo su - -c \'usermod -o -u {1} {0}; groupmod -o -g {2} {0}\' &> /dev/null &'.format(localUser, uid, gid))
            except KeyError:
                continue
    
    hostname = os.popen('hostname -s').read().strip()
    if not skipsync:
        import ipgetter
        pssh.run(user, user, host, 'sudo clic-synchosts {0}:{1}'.format(hostname, ipgetter.myip()))
    pssh.run(user, user, host, 'clic-mount {0}@{1} &'.format(user, hostname))
    
    # Copy executables in /etc/clic/ to node and run in shell expansion order
    paths = [path for path in Path('/etc/clic').iterdir()]
    paths.sort()
    for path in paths:
        if path.is_file() and os.access(str(path), os.X_OK):
            dest = '/tmp/{0}'.format(path.parts[-1])
            pssh.copy(user, user, host, str(path), dest)
            pssh.run(user, user, host, 'sudo {0} {1} {2} {3}'.format(dest, cpus, disk, mem))


def main():
    import argparse
    import re
    parser = argparse.ArgumentParser(description='Intitialize a node for use with clic by configuring its /etc/hosts and nfs. This script is run from the head node.')
    from clic import version
    parser.add_argument('-v', '--version', action='version', version=version.__version__)
    parser.add_argument('userhost', metavar='USER@HOST', nargs=1, help='passwordless ssh exists both ways between USER@localhost and USER@HOST')
    args = parser.parse_args()
    [user, host] = args.userhost[0].split('@')
    init(user, host, False, 0, 0, 0)
