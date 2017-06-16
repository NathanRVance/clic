#!/usr/bin/python3
import ipgetter
import os
from pathlib import Path
from pwd import getpwnam

def init(user, host):
    ip = ipgetter.myip()
    hostname = os.popen('hostname -s').read().strip()
    sshOpts = '-oStrictHostKeyChecking=no -oUserKnownHostsFile=/dev/null -oLogLevel=error'

    # Sync UIDs and GIDs
    for path in Path('/home').iterdir():
        if path.is_dir():
            localUser = path.parts[-1]
            uid = getpwnam(localUser).pw_uid
            gid = getpwnam(localUser)[2]
            os.system('sudo ssh -i /home/{0}/.ssh/id_rsa {2} {0}@{1} "nohup sudo su - -c \'usermod -o -u {4} {3} && groupmod -o -g {5} {3}\' &> /dev/null &"'.format(user, host, sshOpts, localUser, uid, gid))
    
    #os.system('sudo clic-copy-id --append --generate')
    os.system('sudo ssh -i /home/{0}/.ssh/id_rsa {2} {0}@{1} "sudo clic-sync-hosts {3} {4}"'.format(user, host, sshOpts, hostname, ip))
    
    # Remotely execute clic-mount
    os.system('sudo ssh -i /home/{0}/.ssh/id_rsa {2} {0}@{1} "sudo clic-mount {0}@{3} &"'.format(user, host, sshOpts, hostname))

if __name__ == "__main__":
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
