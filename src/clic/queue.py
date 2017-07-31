#!/usr/bin/env python3
from clic import nodes
import re
import os
import subprocess
import time

def getQueue(isHeadnode, partitions):
    return slurm(isHeadnode, partitions)

class abstract_queue:
    def __init__(self):
        pass
    def idle():
        # Return: {node, ...}
        pass
    def running():
        # Return: {node, ...}
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
        # Return: [[jobNum, partition], ...]
        pass
   
class slurm(abstract_queue):
    def __init__(self, isHeadnode, partitions):
        import configparser
        config = configparser.ConfigParser()
        config.read('/etc/clic/clic.conf')
        self.slurmDir = config['Queue']['slurmDir']
        self.namescheme = config['Daemon']['namescheme']
        self.user = config['Daemon']['user']
        self.isHeadnode = isHeadnode
        self.partitions = partitions
        if isHeadnode:
            # Initialize slurm.conf
            data = ''
            with open('{}/slurm.conf'.format(self.slurmDir)) as f:
                data = f.read()
            for partition in partitions:
                if not re.search('={0}-{1}-\[0-\d+\] '.format(self.namescheme, partition.name), data):
                    # RealMemory, TmpDisk in mb
                    data += 'NodeName={0}-{1}-[0-0] CPUs={2} TmpDisk={3} RealMemory={4} State=UNKNOWN\n'.format(self.namescheme, partition.name, partition.cpus, partition.disk * 1024, partition.realMem * 1024)
                    data += 'PartitionName={1} Nodes={0}-{1}-[0-0] MaxTime=UNLIMITED State=UP\n'.format(self.namescheme, partition.name)
            with open('{}/slurm.conf'.format(self.slurmDir), 'w') as f:
                f.write(data)
    
            # Initialize job_submit.lua
            data = []
            with open('{}/job_submit.lua'.format(self.slurmDir)) as f:
                data = f.readlines()
            start = 0
            for start in range(len(data)):
                if re.search('START CLIC STUFF', data[start]):
                    start += 1
                    while not re.search('END CLIC STUFF', data[start]):
                        del data[start]
                    break
            for partition in partitions:
                data.insert(start, '\tparts["{0}"] = {{ cpus = {1}, disk = {2}, mem = {3} }}\n'.format(partition.name, partition.cpus, partition.disk * 1024, partition.realMem * 1024))
            with open('{}/job_submit.lua'.format(self.slurmDir), 'w') as f:
                f.writelines(data)
            subprocess.Popen(['systemctl', 'restart', 'slurmctld.service']).wait()
        else:
            subprocess.Popen(['systemctl', 'restart', 'slurmd.service']).wait()

    def idle(self):
        return {nodes.getNode(nodeName) for nodeName in os.popen('sinfo -o "%t %n" | grep -E "idle|drain" | awk \'{print $2}\'').read().split()} - {None}

    def running(self):
        return {nodes.getNode(nodeName) for nodeName in os.popen('sinfo -h -N -r -o %N').read().split()} - {None}

    def configChanged(self):
        self.restart(True)

    def restart(self, restartSlurm, node=None):
        if restartSlurm and self.isHeadnode:
            subprocess.Popen(['systemctl', 'restart', 'slurmctld.service']).wait()
            time.sleep(5)
        if node:
            self.restartSlurmd(node)
            time.sleep(1)
            subprocess.Popen(['scontrol', 'update', 'nodename=' + node.name, 'state=resume'])
            time.sleep(1)
            subprocess.Popen(['scontrol', 'update', 'nodename=' + node.name, 'state=undrain'])

    def nodeChangedState(self, node):
        if node.state == 'C':
            subprocess.Popen(['scontrol', 'update', 'nodename=' + node.name, 'state=down', 'reason="Creating"']).wait()
        elif node.state == 'R':
            self.addToSlurmConf(node)
            subprocess.Popen(['scontrol', 'update', 'nodename=' + node.name, 'state=up', 'reason="Up"']).wait()
            time.sleep(1)
            subprocess.Popen(['scontrol', 'update', 'nodename=' + node.name, 'state=resume'])
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
            self.restart(True)
            self.restartSlurmd(node)
            time.sleep(5)

    def restartSlurmd(self, node):
        from clic import pssh
        pssh.run(self.user, self.user, node.name, 'sudo systemctl restart slurmd.service')

    def queuedJobs(self):
        qJobs = []
        for job in os.popen('squeue -h -t pd -o "%A %P"').read().strip().split('\n'):
            parts = job.split()
            if len(parts) == 2:
                parts[1] = nodes.getPartition(parts[1])
                if not parts[1] is None:
                    qJobs.append(parts)
        return qJobs
