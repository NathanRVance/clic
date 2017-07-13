#!/usr/bin/env python3
import subprocess
import os
import re
import time
import rpyc
from threading import Thread
from clic import initnode
from clic import nodesup
from clic import synchosts
from clic import pssh
import configparser
import fileinput

config = configparser.ConfigParser()
config.read('/etc/clic/clic.conf')
settings = config['Daemon']

# Constants
minRuntime = settings.getint('minRuntime')
slurmDir = settings['slurmDir']
user = settings['user']
namescheme = settings['namescheme']
snapshot = settings['snapshot']
logfile = settings['logfile']
isCloud = settings.getboolean('cloudHeadnode')
validName = re.compile('^' + namescheme + '-\w+-\d+$')

# Node settings
settings = config['Nodes']
cpuValues = settings['cpus'].replace(' ', '').split(',')
diskValues = settings['disksize'].replace(' ', '').split(',')
memValues = settings['memory'].replace(' ', '').split(',')

def parseInt(value):
    try:
        return int(float(value))
    except:
        return 0

class Partition:
    def __init__(self, cpus, disk, mem):
        self.cpus = int(cpus)
        self.disk = int(disk)
        self.mem = mem
        if mem == 'standard':
            self.realMem = int(float(self.cpus) * 3.75)
        elif mem == 'highmem':
            self.realMem = int(float(self.cpus) * 6.5)
        elif mem == 'highcpu':
            self.realMem = int(float(self.cpus) * .9)
        self.name = '{0}cpu{1}disk{2}'.format(cpus, disk, mem)

partitions = [Partition(cpus, disk, mem) for cpus in cpuValues for disk in diskValues for mem in memValues if not (cpus == '1' and mem == 'highmem') and not (cpus == '1' and mem == 'highcpu')]

def getPartition(name):
    return next((partition for partition in partitions if partition.name == name), None)

class Node:
    def __init__(self, partition, num):
        self.partition = partition
        self.num = num
        self.name = '{0}-{1}-{2}'.format(namescheme, partition.name, num)
        self.state = ''
        self.timeEntered = time.time()
        self.errors = 0
    def __str__(self):
        return self.name
    def setState(self, state):
        if self.state != state:
            self.timeEntered = time.time()
            self.state = state
    def timeInState(self):
        return time.time() - self.timeEntered

nodes = []

def getNode(nodeName):
    node = next((node for node in nodes if node.name == nodeName), None)
    if not node == None:
        return node
    partition = getPartition(re.search('(?<=-)[^-]+(?=-\d+$)', nodeName).group(0))
    num = int(re.search('(?<=-)\d+$', nodeName).group(0))
    node = Node(partition, num)
    nodes.append(node)
    return node

class Job:
    def __init__(self, num):
        self.num = num
        self.time = time.time()
    def timeWaiting(self):
        return time.time() - self.time

jobs = {partition : [] for partition in partitions}

def log(message):
    message = message.strip() + '\n'
    with open(logfile, 'a') as log:
        log.write(message)
    print(message)

def getNodesInState(state):
    return {node for node in nodes if node.state == state}

def getFreeNode(partition):
    freeNum = 0
    for node in nodes:
        if node.partition == partition:
            if node.num >= freeNum:
                freeNum = node.num + 1
            if node.state == '':
                return node
    # Time to make it
    node = Node(partition, freeNum)
    nodes.append(node)
    return node

def getDeletableNodes(partition):
    deletable = [getNode(nodeName) for nodeName in os.popen('sinfo -o "%t %n" | grep -E "idle|drain" | awk \'{print $2}\'').read().split() if validName.search(nodeName)]
    return [node for node in deletable if node.partition == partition and node.state == 'R' and node.timeInState() >= minRuntime]

def addToSlurmConf(node):
    data = ''
    pattern = re.compile('(?<=={0}-{1}-\[0-)\d+(?=\])'.format(namescheme, node.partition.name))
    with open('{}/slurm.conf'.format(slurmDir)) as f:
        data = f.read()
    if int(pattern.search(data).group(0)) < node.num:
        data = pattern.sub(str(node.num), data)
        with open('{}/slurm.conf'.format(slurmDir), 'w') as f:
            f.write(data)
        restartSlurmd(node)

def restartSlurmctld():
    log('WARNING: Restarting slurmctld')
    subprocess.Popen(['systemctl', 'restart', 'slurmctld']).wait()
    time.sleep(5)
    for node in getNodesInState('R'):
        subprocess.Popen(['scontrol', 'update', 'nodename=' + node.name, 'state=resume'])
        subprocess.Popen(['scontrol', 'update', 'nodename=' + node.name, 'state=undrain'])

def restartSlurmd(node):
    pssh.run(user, user, node.name, 'sudo systemctl restart slurmd.service')

def create(numToCreate, partition):
    existingDisks = {nodeName for nodeName in os.popen('gcloud compute disks list | tail -n+2 | awk \'{print $1}\'').read().split() if validName.search(nodeName)}
    while numToCreate > 0:
        # Get a valid node
        while True:
            node = getFreeNode(partition)
            if node == None:
                return
            elif node.name in existingDisks:
                node.setState('D')
                log('ERROR: Disk for {0} exists, but shouldn\'t! Deleting...'.format(node.name))
                subprocess.Popen('echo Y | gcloud compute disks delete {0}'.format(node.name), shell=True)
            else:
                break
        node.setState('C')
        node.errors = 0
        subprocess.Popen(['scontrol', 'update', 'nodename=' + node.name, 'state=down', 'reason="Creating"'])
        log('Creating {}'.format(node.name))
        subprocess.Popen('gcloud compute disks create {0} --size {3} --source-snapshot {1} && gcloud compute instances create {0} --machine-type "n1-{4}-{2}" --disk "name={0},device-name={0},mode=rw,boot=yes,auto-delete=yes" || echo "ERROR: Failed to create {0}" | tee -a {5}'.format(node.name, snapshot, partition.cpus, partition.disk, partition.mem, logfile), shell=True)
        numToCreate -= 1

def deleteNode(node):
        node.setState('D')
        log('Deleting {}'.format(node.name))
        subprocess.Popen(['scontrol', 'update', 'nodename=' + node.name, 'state=drain', 'reason="Deleting"'])
        subprocess.Popen('while true; do if [ -n "`sinfo -h -N -o "%N %t" | grep "{0} " | awk \'{{print $2}}\' | grep drain`" ]; then echo Y | gcloud compute instances delete {0}; break; fi; sleep 10; done'.format(node.name), shell=True)

def mainLoop():
    while True:
        if not isCloud:
            synchosts.addAll()
        # Start with some book keeping
        slurmRunning = {getNode(nodeName) for nodeName in os.popen('sinfo -h -N -r -o %N').read().split() if validName.search(nodeName)} - {None}
        cloudRunning = {getNode(nodeName) for nodeName in nodesup.responds(user, validName) if validName.search(nodeName)} - {None}
        cloudAll = {getNode(nodeName) for nodeName in nodesup.all(False) if validName.search(nodeName)} - {None}
        
        # Nodes that were creating and now are running:
        cameUp = []
        for node in cloudRunning:
            if node.state == 'C':
                node.setState('R')
                initnode.init(user, node.name, isCloud, node.partition.cpus, node.partition.disk, node.partition.mem)
                cameUp.append(node)
                log('Node {} came up'.format(node.name))
        if len(cameUp) > 0:
            for node in cameUp:
                addToSlurmConf(node)
            restartSlurmctld()
            continue
        
        # Nodes that were deleting and now are gone:
        nodesWentDown = False
        for node in getNodesInState('D') - cloudAll:
            nodesWentDown = True
            node.setState('')
            subprocess.Popen(['scontrol', 'update', 'nodename=' + node.name, 'state=down', 'reason="Deleted"'])
            log('Node {} went down'.format(node.name))
        if nodesWentDown:
            # There's a chance they'll come up later with different IPs. Restart slurmctld to avoid errors.
            restartSlurmctld()
            continue
        
        # Error conditions:
        # We think they're up, but the cloud doesn't:
        for node in getNodesInState('R') - cloudAll:
            log('ERROR: Node {} deleted outside of clic!'.format(node.name))
            deleteNode(node)
        
        # We think they're running, but slurm doesn't:
        for node in getNodesInState('R') - slurmRunning:
            if node.timeInState() > 30:
                log('ERROR: Node {} is unresponsive!'.format(node.name))
                node.errors += 1
                if node.errors < 5:
                    # Spam a bunch of stuff to try to bring it back online
                    addToSlurmConf(node)
                    initnode.init(user, node.name, isCloud, node.partition.cpus, node.partition.disk, node.partition.mem)
                    restartSlurmd(node)
                    restartSlurmctld()
                else:
                    # Something is very wrong. Kill it.
                    node.setState('D')
                    log('Deleting {}'.format(node.name))
                    subprocess.Popen(['scontrol', 'update', 'nodename=' + node.name, 'state=down', 'reason="error"'])
                    subprocess.Popen('echo Y | gcloud compute instances delete {0}'.format(node.name), shell=True)

        # Nodes are running but aren't registered:
        for node in cloudRunning - getNodesInState('R') - getNodesInState('D'):
            log('ERROR: Encountered unregistered node {}!'.format(node.name))
            node.setState('R')
            if not node in slurmRunning:
                subprocess.Popen(['scontrol', 'update', 'nodename=' + node.name, 'state=resume'])

        # Nodes that are taking way too long to boot:
        for node in getNodesInState('C'):
            if node.timeInState() > 200:
                log('ERROR: Node {} hung on boot!'.format(node.name))

        # Book keeping for jobs. Modify existing structure rather than replacing because jobs keep track of wait time.
        # jobs = {partition : [job, ...], ...}
        # qJobs = [[jobNum, partition], ...]
        qJobs = [[job.split()[0], getPartition(job.split()[1])] for job in os.popen('squeue -h -t pd -o "%A %P"').read().strip().split('\n') if len(job.split()) == 2]
        # Delete dequeued jobs
        for partition in jobs:
            for job in jobs[partition]:
                if job.num not in [qJob[0] for qJob in qJobs if qJob[1] == partition]:
                    jobs[partition].remove(job)
        # Add new jobs
        # Sometimes, immediately after slurmctld restarts, running jobs are listed as queued. Only queue jobs with a number greater than any other job.
        sampleNum = 0
        for partition in jobs:
            for job in jobs[partition]:
                if int(job.num) > sampleNum:
                    sampleNum = int(job.num)
        for qJob in qJobs:
            if qJob[1] in jobs and qJob[0] not in [job.num for job in jobs[qJob[1]]] and int(qJob[0]) > sampleNum:
                jobs[qJob[1]].append(Job(qJob[0]))

        # Create and delete nodes
        for partition in jobs:
            deletable = getDeletableNodes(partition)
            creating = {node for node in getNodesInState('C') if node.partition == partition}
            running = {node for node in getNodesInState('R') if node.partition == partition}
            if len(creating) + len(running) == 0 and len(jobs[partition]) > 0:
                create(int((len(jobs[partition]) + 1) / 2), partition)
            else:
                # SLURM may not have had the chance to utilize some "running" nodes
                unutilized = 0
                for node in running:
                    if node.timeInState() < 60:
                        unutilized += 1
                jobsWaitingTooLong = [job for job in jobs[partition] if job.timeWaiting() > 30]
                create(int((len(jobsWaitingTooLong) + 1) / 2 - len(creating) - len(deletable) - unutilized), partition)
            # Delete nodes
            if len(deletable) > 0 and len(jobs[partition]) == 0:
                for node in deletable[0:int((len(deletable) + 1) / 2)]:
                    deleteNode(node)

class exportNodes(rpyc.Service):
    def on_connect(self):
        pass
    def on_disconnect(self):
        pass
    def exposed_getNodes(self):
        return nodes

def startServer():
    if __name__ == "__main__":
        from rpyc.utils.server import ThreadedServer
        t = ThreadedServer(exportNodes, hostname='localhost', port=18861, protocol_config={'allow_public_attrs':True})
        t.start()

def main():
    Thread(target = startServer).start()

    if os.popen('hostname -s').read().strip() == namescheme or not isCloud:
        # This is the head node
        log('Starting clic as a head node')
        # Initialize slurm.conf
        data = ''
        with open('{}/slurm.conf'.format(slurmDir)) as f:
            data = f.read()
        for partition in partitions:
            if not re.search('={0}-{1}-\[0-\d+\] '.format(namescheme, partition.name), data):
                # RealMemory, TmpDisk in mb
                data += 'NodeName={0}-{1}-[0-0] CPUs={2} TmpDisk={3} RealMemory={4} State=UNKNOWN\n'.format(namescheme, partition.name, partition.cpus, partition.disk * 1024, partition.realMem * 1024)
                data += 'PartitionName={1} Nodes={0}-{1}-[0-0] MaxTime=UNLIMITED State=UP\n'.format(namescheme, partition.name)
        with open('{}/slurm.conf'.format(slurmDir), 'w') as f:
            f.write(data)

        # Initialize job_submit.lua
        data = []
        with open('{}/job_submit.lua'.format(slurmDir)) as f:
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
        with open('{}/job_submit.lua'.format(slurmDir), 'w') as f:
            f.writelines(data)

        log('Starting slurmctld.service')
        subprocess.Popen(['systemctl', 'restart', 'slurmctld.service']).wait()
        if isCloud:
            zone = os.popen('gcloud compute instances list | grep "$(hostname) " | awk \'{print $2}\'').read()
            log('Configuring gcloud for zone {}'.format(zone))
            subprocess.Popen(['gcloud', 'config', 'set', 'compute/zone', zone])
        mainLoop()
    else:
        # This is a compute node
        log('Starting clic as a compute node')
        log('Starting slurmd.service')
        subprocess.Popen(['systemctl', 'restart', 'slurmd.service']).wait()
