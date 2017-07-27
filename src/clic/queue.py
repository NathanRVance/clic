#!/usr/bin/env python3
from nodes import Node
from nodes import Partition
import re
import os
import subprocess

def getQueue(isHeadnode):
    return slurm(isHeadnode)

class abstract_queue:
    def __init__(self):
        pass
    def idle():
        # Return: {nodeName, ...}
        pass
    def running():
        # Return: {nodeName, ...}
        pass
    def configChanged():
        # Called whenever a node goes up or down
        pass
    def restart(restartQueue, node=None):
        # Called when queue is misbehaving
        pass
    def nodeChangedState(node):
        pass
    def queuedJobs():
        # Return: [[jobNum, partitionName], ...]
        pass
   
class slurm(abstract_queue):
    def __init__(self, isHeadnode):
        import configparser
        config = configparser.ConfigParser()
        self.slurmDir = config['Queue']['slurmDir']
        self.namescheme = config['Daemon']['namescheme']
        self.isHeadnode = isHeadnode
        if isHeadnode:
            subprocess.Popen(['systemctl', 'restart', 'slurmctld.service']).wait()
        else:
            subprocess.Popen(['systemctl', 'restart', 'slurmd.service']).wait()

    def idle(self):
        return {nodeName for nodeName in os.popen('sinfo -o "%t %n" | grep -E "idle|drain" | awk \'{print $2}\'').read().split()}

    def running(self):
        return {nodeName for nodeName in os.popen('sinfo -h -N -r -o %N').read().split()}

    def configChanged(self):
        self.restart(True)

    def restart(self, restartSlurm, node=None):
        if restartSlurm and self.isHeadnode:
            subprocess.Popen(['systemctl', 'restart', 'slurmctld.service']).wait()
        if node:
            self.restartSlurmd(node)
            subprocess.Popen(['scontrol', 'update', 'nodename=' + node.name, 'state=resume'])
            subprocess.Popen(['scontrol', 'update', 'nodename=' + node.name, 'state=undrain'])

    def nodeChangedState(self, node):
        if node.state == 'C':
            subprocess.Popen(['scontrol', 'update', 'nodename=' + node.name, 'state=down', 'reason="Creating"']).wait()
        elif node.state == 'R':
            subprocess.Popen(['scontrol', 'update', 'nodename=' + node.name, 'state=up', 'reason="Up"']).wait()
            self.addToSlurmConf(node)
        elif node.state == 'D':
            subprocess.Popen(['scontrol', 'update', 'nodename=' + node.name, 'state=drain', 'reason="Deleting"']).wait()
        elif node.state == '':
            subprocess.Popen(['scontrol', 'update', 'nodename=' + node.name, 'state=down', 'reason="Deleted"']).wait()

    def addToSlurmConf(self, node):
        data = ''
        pattern = re.compile('(?<=={0}-{1}-\[0-)\d+(?=\])'.format(self.namescheme, node.partition.name))
        with open('{}/slurm.conf'.format(self.slurmDir)) as f:
            data = f.read()
        if int(pattern.search(data).group(0)) < node.num:
            data = pattern.sub(str(node.num), data)
            with open('{}/slurm.conf'.format(self.slurmDir), 'w') as f:
                f.write(data)
            self.restartSlurmd(node)

    def restartSlurmd(self, node):
        from clic import pssh
        pssh.run(user, user, node.name, 'sudo systemctl restart slurmd.service')

    def queuedJobs(self):
        return [job.split() for job in os.popen('squeue -h -t pd -o "%A %P"').read().strip().split('\n') if len(job.split()) == 2]
