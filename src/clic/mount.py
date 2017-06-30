#!/usr/bin/env python3
import os
import time

def mount(user, host):
    sshOpts = '-oStrictHostKeyChecking=no -oUserKnownHostsFile=/dev/null -oLogLevel=error'
    # Set up ssh tunnel
    os.popen('sudo ssh -i /home/{0}/.ssh/id_rsa {2} -fN -L 3049:localhost:2049 {0}@{1}'.format(user, host, sshOpts))
    time.sleep(2)
    # Set up nfs
    os.system('sudo mount -t nfs4 -o port=3049,rw localhost:/home /home')
    # Fix /home/*/.ssh
    # Create a directory to bind / to
    os.system('if [ ! -d "/bind-root" ]; then sudo mkdir /bind-root; fi')
    os.system('sudo mount --bind / /bind-root')
    os.system('for user in `ls /home`; do sudo mount --bind /bind-root/home/$user/.ssh /home/$user/.ssh; done')
    # Mount /etc/slurm
    os.system('sudo mount -t nfs4 -o port=3049,ro localhost:/etc/slurm /etc/slurm')
    # (re)start slurmd
    os.system('sudo systemctl restart slurmd.service')

def main():
    import argparse
    import re
    parser = argparse.ArgumentParser(description='Mount remote home directory (NOTE: preserves /home/*/.ssh)')
    parser.add_argument('userhost', metavar='USER@HOST', nargs=1, help='passwordless ssh exists from USER@localhost to USER@HOST')
    args = parser.parse_args()
    # Error checking
    if not re.search('^[\w-]+@[\w-]+$', args.userhost[0]):
        parser.error('incorrect formatting: ' + args.userhost[0])
    
    [user, host] = args.userhost[0].split('@')
    mount(user, host)
