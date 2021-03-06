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
from clic import nodes

config = configparser.ConfigParser()
config.read('/etc/clic/clic.conf')

# Constants
settings = config['Daemon']
minRuntime = settings.getint('minRuntime')
namescheme = settings['namescheme']
import logging as loggingmod
loggingmod.basicConfig(filename=settings['logfile'], format='%(levelname)s: %(message)s', level=loggingmod.CRITICAL)
logging = loggingmod.getLogger('clic')
logging.setLevel(loggingmod.DEBUG)

isCloud = settings.getboolean('cloudHeadnode')

# Cloud settings
from clic import cloud as api
cloud = api.getCloud()

# Queue settings
isHeadnode = os.popen('hostname -s').read().strip() == namescheme or not isCloud
from clic import queue as q
queue = q.getQueue(isHeadnode, nodes.partitions)

class Job:
    def __init__(self, num):
        self.num = num
        self.time = time.time()
    def timeWaiting(self):
        return time.time() - self.time

jobs = {partition : [] for partition in nodes.partitions}

def getNodesInState(state):
    return {node for node in nodes.nodes if node.state == state}

def getDeletableNodes(partition):
    deletable = queue.idle()
    return [node for node in deletable if node.partition == partition and node.state == 'R' and node.timeInState() >= minRuntime]

def create(numToCreate, partition):
    existingDisks = cloud.getDisks()
    while numToCreate > 0:
        # Get a valid node
        while True:
            node = nodes.getFreeNode(partition)
            if node == None:
                return
            elif node.name in existingDisks:
                node.setState('D')
                logging.warning('Disk for {0} exists, but shouldn\'t! Deleting...'.format(node.name))
                cloud.deleteDisk(node.name)
            else:
                break
        node.setState('C')
        node.errors = 0
        queue.nodeChangedState(node)
        logging.info('Creating {}'.format(node.name))
        cloud.create(node)
        numToCreate -= 1

def deleteNode(node):
    node.setState('D')
    logging.info('Deleting {}'.format(node.name))
    queue.nodeChangedState(node)
    cloud.delete(node)
    #subprocess.Popen('while true; do if [ -n "`sinfo -h -N -o "%N %t" | grep "{0} " | awk \'{{print $2}}\' | grep drain`" ]; then echo Y | gcloud compute instances delete {0}; break; fi; sleep 10; done'.format(node.name), shell=True)

def mainLoop():
    while True:
        if not isCloud:
            synchosts.addAll()
        # Start with some book keeping
        queueRunning = queue.running()
        cloudRunning = nodesup.responds()
        cloudAll = nodesup.all(False)
        
        # Nodes that were creating and now are running:
        cameUp = []
        for node in cloudRunning:
            if node.state == 'C':
                node.setState('R')
                initnode.init(node.name, node.partition.cpus, node.partition.disk, node.partition.mem)
                cameUp.append(node)
                logging.info('Node {} came up'.format(node.name))
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
            logging.info('Node {} went down'.format(node.name))
        if nodesWentDown:
            # There's a chance they'll come up later with different IPs.
            queue.configChanged()
            continue
        
        # Error conditions:
        # We think they're up, but the cloud doesn't:
        for node in getNodesInState('R') - cloudAll:
            logging.warning('Node {} deleted outside of clic!'.format(node.name))
            deleteNode(node)
        
        # We think they're running, but slurm doesn't:
        for node in getNodesInState('R') - queueRunning:
            if node.timeInState() > 30:
                logging.error('Node {} is unresponsive!'.format(node.name))
                queue.restart(False, node=node)
                node.errors += 1
                if node.errors < 5:
                    # Spam a bunch of stuff to try to bring it back online
                    initnode.init(node.name, node.partition.cpus, node.partition.disk, node.partition.mem)
                    queue.restart(True, node=node)
                    time.sleep(5)
                    for node in getNodesInState('R'):
                        queue.restart(False, node=node)
                else:
                    # Something is very wrong. Kill it.
                    node.setState('D')
                    logging.error('Node {} is unresponsive. Deleting...'.format(node.name))
                    queue.nodeChangedState(node)
                    cloud.delete(node)

        # Nodes are running but aren't registered:
        for node in cloudRunning - getNodesInState('R') - getNodesInState('D'):
            logging.warning('Encountered unregistered node {}!'.format(node.name))
            node.setState('R')
            if not node in queueRunning:
                queue.nodeChangedState(node)

        # Nodes that are taking way too long to boot:
        for node in getNodesInState('C'):
            if node.timeInState() > 200:
                logging.error('Node {} hung on boot!'.format(node.name))

        # Book keeping for jobs. Modify existing structure rather than replacing because jobs keep track of wait time.
        # jobs = {partition : [job, ...], ...}
        # qJobs = [[jobNum, partition], ...]
        qJobs = queue.queuedJobs()
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
        return nodes.nodes

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
        logging.info('Starting clic as a head node')
        # Sort out ssh keys
        from clic import copyid
        copyid.refresh(True)
        copyid.copyAll(True)
        copyid.send()

        queue.restart(True)
        mainLoop()
    else:
        # This is a compute node
        logging.info('Starting clic as a compute node')
