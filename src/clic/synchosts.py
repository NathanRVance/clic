#!/usr/bin/env python3
import re
import subprocess

def read():
    hosts = open('/etc/hosts', 'r')
    contents = hosts.readlines()
    hosts.close()
    return contents

def add(host, ip):
    contents = read()
    delete = re.compile('(^{0} )|( {1}$)'.format(re.escape(ip), re.escape(host)))
    with open('/etc/hosts', 'w') as hosts:
        for line in contents:
            if not delete.search(line):
                hosts.write(line)
        hosts.write('{0} {1}\n'.format(ip, host))

def addAll():
    from clic import cloud as api
    cloud = api.getCloud()
    for node in cloud.nodesUp(True):
        add(node['node'].name, node['ip'])

def main():
    import argparse
    parser = argparse.ArgumentParser(description='Modify /etc/hosts. Default action is add ip addresses for compute nodes')
    from clic import version
    parser.add_argument('-v', '--version', action='version', version=version.__version__)
    parser.add_argument('hostip', metavar='HOST:IP', nargs='?', help='add HOST:ID mapping to /etc/hosts')
    args = parser.parse_args()
    
    if args.hostip:
        [host, ip] = args.hostip.split(':')
        add(host, ip)
    else:
        addAll()
