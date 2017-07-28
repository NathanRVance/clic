#!/usr/bin/env python3
import subprocess
import os
import re
import time
import rpyc
import configparser
import fileinput
from threading import Thread
from clic import initnode
from clic import nodesup
from clic import synchosts
from clic import pssh
from clic.nodes import Partition
from clic.nodes import Node

config = configparser.ConfigParser()
config.read('/etc/clic/clic.conf')

# Constants
settings = config['Daemon']
minRuntime = settings.getint('minRuntime')
slurmDir = config['Queue']['slurmDir'] #TODO: Eliminate
user = settings['user']
namescheme = settings['namescheme']
logfile = settings['logfile']
isCloud = settings.getboolean('cloudHeadnode')
validName = re.compile('^' + namescheme + '-\w+-\d+$')

# Cloud settings
from clic import cloud as api
cloud = api.getCloud()

# Queue settings
isHeadnode = os.popen('hostname -s').read().strip() == namescheme or not isCloud
from clic import queue as q
queue = q.getQueue(isHeadnode)

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

partitions = [Partition(cpus, disk, mem) for cpus in cpuValues for disk in diskValues for mem in memValues if not (cpus == '1' and mem == 'highmem') and not (cpus == '1' and mem == 'highcpu')]

nodes = []

def getPartition(name):
    return next((partition for partition in partitions if partition.name == name), None)

def getNode(nodeName):
    node = next((node for node in nodes if node.name == nodeName), None)
    if not node == None:
        return node
    partition = getPartition(re.search('(?<=-)[^-]+(?=-\d+$)', nodeName).group(0))
    num = int(re.search('(?<=-)\d+$', nodeName).group(0))
    node = Node(namescheme, partition, num)
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
    node = Node(namescheme, partition, freeNum)
    nodes.append(node)
    return node

def getDeletableNodes(partition):
    deletable = [getNode(node) for node in queue.idle() if validName.search(node)]
    return [node for node in deletable if node.partition == partition and node.state == 'R' and node.timeInState() >= minRuntime]

def create(numToCreate, partition):
    existingDisks = {nodeName for nodeName in cloud.getDisks() if validName.search(nodeName)}
    while numToCreate > 0:
        # Get a valid node
        while True:
            node = getFreeNode(partition)
            if node == None:
                return
            elif node.name in existingDisks:
                node.setState('D')
                log('ERROR: Disk for {0} exists, but shouldn\'t! Deleting...'.format(node.name))
                cloud.deleteDisk(node.name)
            else:
                break
        node.setState('C')
        node.errors = 0
        queue.nodeChangedState(node)
        log('Creating {}'.format(node.name))
        cloud.create(node)
        numToCreate -= 1

def deleteNode(node):
    node.setState('D')
    log('Deleting {}'.format(node.name))
    queue.nodeChangedState(node)
    cloud.delete(node)
    #subprocess.Popen('while true; do if [ -n "`sinfo -h -N -o "%N %t" | grep "{0} " | awk \'{{print $2}}\' | grep drain`" ]; then echo Y | gcloud compute instances delete {0}; break; fi; sleep 10; done'.format(node.name), shell=True)

def mainLoop():
    while True:
        if not isCloud:
            synchosts.addAll()
        # Start with some book keeping
        queueRunning = {getNode(nodeName) for nodeName in queue.running() if validName.search(nodeName)} - {None}
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
            queue.configChanged()
            for node in cameUp:
                queue.nodeChangedState(node)
            continue
        
        # Nodes that were deleting and now are gone:
        nodesWentDown = False
        for node in getNodesInState('D') - cloudAll:
            nodesWentDown = True
            node.setState('')
            queue.nodeChangedState(node)
            log('Node {} went down'.format(node.name))
        if nodesWentDown:
            # There's a chance they'll come up later with different IPs.
            queue.configChanged()
            continue
        
        # Error conditions:
        # We think they're up, but the cloud doesn't:
        for node in getNodesInState('R') - cloudAll:
            log('ERROR: Node {} deleted outside of clic!'.format(node.name))
            deleteNode(node)
        
        # We think they're running, but slurm doesn't:
        for node in getNodesInState('R') - queueRunning:
            if node.timeInState() > 30:
                log('ERROR: Node {} is unresponsive!'.format(node.name))
                node.errors += 1
                if node.errors < 5:
                    # Spam a bunch of stuff to try to bring it back online
                    initnode.init(user, node.name, isCloud, node.partition.cpus, node.partition.disk, node.partition.mem)
                    queue.restart(True, node=node)
                    time.sleep(5)
                    for node in getNodesInState('R'):
                        queue.restart(False, node=node)
                else:
                    # Something is very wrong. Kill it.
                    node.setState('D')
                    log('Deleting {}'.format(node.name))
                    queue.nodeChangedState(node)
                    cloud.delete(node)

        # Nodes are running but aren't registered:
        for node in cloudRunning - getNodesInState('R') - getNodesInState('D'):
            log('ERROR: Encountered unregistered node {}!'.format(node.name))
            node.setState('R')
            if not node in queueRunning:
                queue.nodeChangedState(node)

        # Nodes that are taking way too long to boot:
        for node in getNodesInState('C'):
            if node.timeInState() > 200:
                log('ERROR: Node {} hung on boot!'.format(node.name))

        # Book keeping for jobs. Modify existing structure rather than replacing because jobs keep track of wait time.
        # jobs = {partition : [job, ...], ...}
        # qJobs = [[jobNum, partition], ...]
        qJobs = [[job[0], getPartition(job[1])] for job in queue.queuedJobs()]
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
    import argparse
    parser = argparse.ArgumentParser(description='Start the clic daemon')
    from clic import version
    parser.add_argument('-v', '--version', action='version', version=version.__version__)
    parser.parse_args()

    Thread(target = startServer).start()

    if isHeadnode:
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

        # Sort out ssh keys
        from clic import copyid
        copyid.refresh(True)
        copyid.copy(True, user, user)
        copyid.send()

        queue.restart(True)
        mainLoop()
    else:
        # This is a compute node
        log('Starting clic as a compute node')
