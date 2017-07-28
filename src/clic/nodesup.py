#!/usr/bin/env python3
import subprocess
import re
from clic import pssh

from clic import cloud as api
cloud = api.getCloud()

import configparser
config = configparser.ConfigParser()
config.read('/etc/clic/clic.conf')
user = config['Daemon']['user']

def responds(user=user):
    return {node for node in all(True) if pssh.canConnect(user, user, node.name)}

def all(running):
    return {node['node'] for node in cloud.nodesUp(running)}

def main():
    import argparse
    parser = argparse.ArgumentParser(description='Obtain a list of nodes that are running')
    from clic import version
    parser.add_argument('-v', '--version', action='version', version=version.__version__)
    parser.add_argument('-r', '--responds', metavar='USER', nargs='?', help='include only nodes that respond to ssh connections')
    args = parser.parse_args()

    if args.responds:
        print('\n'.join([node.name for node in responds(args.responds)]))
    else:
        print('\n'.join([node.name for node in all(False)]))
