#!/usr/bin/env python3
import subprocess
import re
from clic import pssh

def responds(user, nameRegex = None):
    if nameRegex is None:
        nameRegex = re.compile('.*')
    return [node for node in all(True) if nameRegex.search(node) and pssh.canConnect(user, user, node)]

def all(running):
    gcloud = subprocess.Popen(['gcloud', 'compute', 'instances', 'list'], stdout=subprocess.PIPE)
    result = ''.join([byte.decode('utf-8') for byte in gcloud.stdout.readlines()]).strip()
    result = '\n'.join(result.split('\n')[1:]) # Chop off column headers
    if running:
        return re.findall('^\S*(?= .*RUNNING$)', result, re.MULTILINE)
    else:
        return re.findall('^\S*', result, re.MULTILINE)

def main():
    import argparse
    parser = argparse.ArgumentParser(description='Obtain a list of nodes that are running')
    from clic import version
    parser.add_argument('-v', '--version', action='version', version=version.__version__)
    parser.add_argument('-r', '--responds', metavar='USER', nargs=1, help='include only nodes that respond to ssh connections')
    args = parser.parse_args()

    if args.responds:
        print('\n'.join(responds(args.responds[0])))
    else:
        print('\n'.join(all(False)))
