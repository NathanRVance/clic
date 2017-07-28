#!/usr/bin/env python3
import subprocess
import re
from clic import pssh

from clic import cloud as api
cloud = api.getCloud()

def responds(user=None, nameRegex=None):
    if user is None:
        import configparser
        config = configparser.ConfigParser()
        config.read('/etc/clic/clic.conf')
        user = config['Daemon']['user']
    if nameRegex is None:
        nameRegex = re.compile('.*')
    return [node for node in all(True) if nameRegex.search(node) and pssh.canConnect(user, user, node)]

def all(running):
    return [node['name'] for node in cloud.nodesUp(running)]

def main():
    import argparse
    parser = argparse.ArgumentParser(description='Obtain a list of nodes that are running')
    from clic import version
    parser.add_argument('-v', '--version', action='version', version=version.__version__)
    parser.add_argument('-r', '--responds', metavar='USER', nargs='?', help='include only nodes that respond to ssh connections')
    args = parser.parse_args()

    if args.responds:
        print('\n'.join(responds(args.responds[0])))
    else:
        print('\n'.join(all(False)))
