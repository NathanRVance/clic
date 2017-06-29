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
import configparser

config = configparser.ConfigParser()
config.read('/etc/clic/clic.conf')
settings = config['Daemon']

# Constants
waitTime = settings.getint(['waitTime'])
maxNodes = settings.getint(['maxNodes'])
minRuntime = settings.getInt(['minRuntime'])

user = settings['user']
namescheme = settings['namescheme']
logfile = settings['logfile']
isCloud = settings.getboolean('cloudHeadnode')
validName = re.compile('^' + namescheme + '-\d+cpu-\d+$')

def parseInt(value):
    try:
        return int(float(value))
    except:
        return 0

class Node:
    def __init__(self, cpus, num):
        self.cpus = cpus
        self.partition = '{0}cpu'.format(cpus)
        self.num = num
        self.name = '{0}-{1}-{2}'.format(namescheme, self.partition, num)
        self.state = ''
        self.timeEntered = time.time()
    def __str__(self):
        return self.name
    def setState(self, state):
        if self.state != state:
            self.timeEntered = time.time()
            self.state = state
    def timeInState(self):
        return time.time() - self.timeEntered

nodes = [Node(cpus, num) for num in range(maxNodes) for cpus in [1, 2, 4, 8, 16, 32]]

class Job:
    def __init__(self, num):
        self.num = num
        self.time = time.time()
    def timeWaiting(self):
        return time.time() - self.time

jobs = {'{0}cpu'.format(cpus) : [] for cpus in [1, 2, 4, 8, 16, 32]}

def getNode(nodeName):
    return next(node for node in nodes if node.name == nodeName)

def log(message):
    message = message.strip() + '\n'
    with open(logfile, 'a') as log:
        log.write(message)
    print(message)

def getNodesInState(state):
    return {node for node in nodes if node.state == state}

def create(numToCreate, partition):
    if numToCreate < 0:
        return
    existingDisks = {getNode(nodeName) for nodeName in os.popen('gcloud compute disks list | tail -n+2 | awk \'{print $1}\'').read().split() if validName.search(nodeName)}
    freeNodes = [node for node in getNodesInState('') - existingDisks if node.partition == partition]
    for node in sorted(freeNodes, key=lambda node: node.num)[0:int(numToCreate)]:
        node.setState('C')
        subprocess.Popen(['scontrol', 'update', 'nodename=' + node.name, 'state=down', 'reason="Creating"'])
        log('Creating {}'.format(node.name))
        subprocess.Popen('gcloud compute disks create {0} --size 10 --source-snapshot {1} && gcloud compute instances create {0} --machine-type "n1-standard-{2}" --disk "name={0},device-name={0},mode=rw,boot=yes,auto-delete=yes" || echo "ERROR: Failed to create {0}" | tee -a {3}'.format(node.name, namescheme, node.cpus, logfile), shell=True)

def delete(numToDelete, partition):
    idleNodes = [getNode(nodeName) for nodeName in os.popen('sinfo -o "%t %n" | grep "idle" | awk \'{print $2}\'').read().split() if validName.search(nodeName)]
    #Narrow by partition
    idleNodes = [node for node in idleNodes if node.partition == partition]
    for node in idleNodes:
        if numToDelete <= 0:
            return
        if node.state == 'R' and node.timeInState() >= minRuntime:
            node.setState('D')
            log('Deleting {}'.format(node.name))
            subprocess.Popen(['scontrol', 'update', 'nodename=' + node.name, 'state=drain', 'reason="Deleting"'])
            subprocess.Popen('while true; do if [ -n "`sinfo -h -N -o "%N %t" | grep "{0} " | awk \'{{print $2}}\' | grep drain`" ]; then echo Y | gcloud compute instances delete {0}; break; fi; sleep 10; done'.format(node.name), shell=True)
            numToDelete -= 1

def mainLoop():
    while True:
        if not isCloud:
            synchosts.addAll()
        # Start with some book keeping
        slurmRunning = {getNode(nodeName) for nodeName in os.popen('sinfo -h -N -r -o %N').read().split() if validName.search(nodeName)}
        cloudRunning = {getNode(nodeName) for nodeName in nodesup.responds(user, validName) if validName.search(nodeName)}
        cloudAll = {getNode(nodeName) for nodeName in nodesup.all(False) if validName.search(nodeName)}
        
        # Nodes that were creating and now are running:
        names = []
        for node in cloudRunning:
            if node.state == 'C':
                node.setState('R')
                initnode.init(user, node.name, isCloud)
                names.append(node.name)
                log('Node {} came up'.format(node.name))
        if len(names) > 0:
            time.sleep(5)
            for name in names:
                subprocess.Popen(['scontrol', 'update', 'nodename=' + name, 'state=resume'])
            # There's a chance they came up with different IPs. Restart slurmctld to avoid errors.
            log('WARNING: Restarting slurmctld')
            subprocess.Popen(['systemctl', 'restart', 'slurmctld']).wait()
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
            log('WARNING: Restarting slurmctld')
            subprocess.Popen(['systemctl', 'restart', 'slurmctld']).wait()
            continue
        
        # Error conditions (log but don't do anything about it):
        # We think they're up, but the cloud doesn't:
        for node in getNodesInState('R') - cloudAll:
            #node.setState('')
            #subprocess.Popen(['scontrol', 'update', 'nodename=' + node.name, 'state=down', 'reason="Error"'])
            log('ERROR: Node {} deleted outside of clic!'.format(node.name))
        
        # We think they're running, but slurm doesn't:
        for node in getNodesInState('R') - slurmRunning:
            if node.timeInState() > 30:
                log('ERROR: Node {} is unresponsive!'.format(node.name))

        # Nodes are running but aren't registered:
        for node in getNodesInState('') & cloudRunning:
            log('ERROR: Encountered unregistered node {}!'.format(node.name))

        # Nodes that are taking way too long to boot:
        for node in getNodesInState('C'):
            if node.timeInState() > 200:
                log('ERROR: Node {} hung on boot!'.format(node.name))

        # Book keeping for jobs. Modify existing structure rather than replacing because jobs keep track of wait time.
        # jobs = {partition : [job, ...], ...}
        # qJobs = [[jobNum, partition], ...]
        qJobs = [job.split() for job in os.popen('squeue -h -t pd -o "%A %P"').read().strip().split('\n') if len(job.split()) == 2]
        # Delete dequeued jobs
        for partition in jobs:
            for job in jobs[partition]:
                if job.num not in [qJob[0] for qJob in qJobs if qJob[1] == partition]:
                    jobs[partition].remove(job)
        # Add new jobs
        # Sometimes, immediately after slurmctld restarts, running jobs are listed as queued. Only queue jobs with a number greater than any other job.
        sampleNum = 0
        for partition in jobs:
            if len(jobs[partition]) > 0:
                sampleNum = int(jobs[partition][0].num)
                break
        for qJob in qJobs:
            if qJob[1] in jobs and qJob[0] not in [job.num for job in jobs[qJob[1]]] and int(qJob[0]) > sampleNum:
                jobs[qJob[1]].append(Job(qJob[0]))

        # idle = {partition : numIdle, ...}
        sinfo = ['']
        while sinfo == ['']:
            sinfo = os.popen('sinfo -h -r -o "%A %P"').read().strip().split('\n')
        idle = {partInfo.split()[1].strip('*') : parseInt(partInfo.split()[0].split('/')[1]) for partInfo in sinfo}
        for partition in jobs:
            # Add nodes
            creating = {node for node in getNodesInState('C') if node.partition == partition}
            running = {node for node in getNodesInState('R') if node.partition == partition}
            if len(creating) + len(running) == 0 and len(jobs[partition]) > 0:
                create(int((len(jobs[partition]) + 1) / 2), partition)
            else:
                # SLURM may not have had the chance to utilize some "running" nodes
                unutilized = 0
                for node in running:
                    if node.timeInState() < 15:
                        unutilized += 1
                jobsWaitingTooLong = [job for job in jobs[partition] if job.timeWaiting() > waitTime]
                create(int((len(jobsWaitingTooLong) + 1) / 2 - len(creating) - idle[partition] - unutilized), partition)
            # Delete nodes
            if idle[partition] > 0 and len(jobs[partition]) == 0:
                delete(int((idle[partition] + 1) / 2), partition)

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
