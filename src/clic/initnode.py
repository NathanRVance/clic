#!/usr/bin/python3
import os
from pathlib import Path
from pwd import getpwnam
from clic import pssh

import configparser
config = configparser.ConfigParser()
config.read('/etc/clic/clic.conf')
user = config['Daemon']['user']

def init(host, cpus, disk, mem, user=user):
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
    init(host, 0, 0, 0, user=user)
