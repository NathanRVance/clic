#!/usr/bin/python3
import argparse
import subprocess
import os
import re
import time

parser = argparse.ArgumentParser(description='This is the CLIC daemon, which monitors the SLURM queue and creates and deletes compute nodes as necessary.')
parser.add_argument('-c', '--cloud', action='store_true', help='this is running on a cloud computer')
parser.add_argument('--logfile', nargs=1, default='/var/log/clic.log', help='file to output logs to (default: /var/log/clic.log)')
parser.add_argument('--max', nargs=1, type=int, default=100, help='maximum number of compute nodes in use (default: 100)')
parser.add_argument('user', metavar='USER', nargs=1, help='a user on compute nodes with passwordless sudo privilages')
parser.add_argument('namescheme', metavar='NAMESCHEME', nargs=1, help='the base name of the compute nodes')
args = parser.parse_args()

# Constants
waitTime = 15

user = args.user[0]
namescheme = args.namescheme[0]
logfile = args.logfile
maxNodeNum = args.max - 1
nodeNumPadding = len(str(maxNodeNum))
states = [''] * maxNodeNum
stateTimes = [time.time()] * maxNodeNum
queuedTimes = {}

def log(message):
    with open(logfile, 'a') as log:
        log.write(message)
    print(message)

def parseInt(value):
    try:
        return int(float(value))
    except:
        return 0

def setState(nodeName, state):
    nodeNum = parseInt(nodeName[-nodeNumPadding:])
    if not states[nodeNum] == state:
        states[nodeNum] = state
        stateTimes = time.time()

def getState(nodeName):
    return states[parseInt(nodeName[-nodeNumPadding:])]

def getNodesInState(state):
    return {namescheme + nodeNum.zfill(nodeNumPadding) for nodeNum in [0:maxNodeNum] if states[nodeNum] == state}

def timeInState(nodeName):
    return time.time() - stateTimes[parseInt(nodeName[-nodeNumPadding:])]

def create(numToCreate):
    existingDisks = set(os.popen('gcloud compute disks list | tail -n+2 | awk \'{print $1}\'').read().split())
    for node in (getNodesInState('') - existingDisks)[0:numToCreate]:
        setState(node, 'C')
        log('Creating {}\n'.format(node))
        subprocess.Popen('gcloud compute disks create {0} --size 10 --source-snapshot {1} &> /dev/null && gcloud compute instances create {0} --machine-type "n1-standard-1" --disk "name={0},device-name={0},mode=rw,boot=yes,auto-delete=yes" &> /dev/null || if [ $? -eq 1 ]; then echo "ERROR: Failed to create {0}" | tee -a {2}; fi'.format(node, namescheme, logfile), shell=True)

def delete(numToDelete):
    idleNodes = os.popen('sinfo -o "%t %n" | grep "idle" | awk \'{print $2}\'').read().split()
    for node in idleNodes[-numToDelete:]:
        setState(node, 'D')
        subprocess.Popen(['scontrol', 'update', 'nodename=' + node, 'state=drain', 'reason="Deleting"'])
        #TODO: finish me!


def mainLoop():
    while True:
        subprocess.Popen('clic-sync-hosts')
        # Start with some book keeping
        validName = re.compile(namescheme + '\d{' + nodNumPadding + '}')
        slurmRunning = {node for node in os.popen('sinfo -h -N -r -o %N').read().split() if validName.search(node)}
        cloudRunning = {node for node in os.popen('clic-nodesup -r').read().split() if validName.search(node)}
        cloudAll = {node for node in os.popen('clic-nodesup').read().split() if validName.search(node)}
        # Nodes that were creating and now are running:
        for node in cloudRunning if getState(node) == 'C':
            setState(node, 'R')
            subprocess.Popen(['scontrol', 'update', 'nodename=' + node, 'state=resume'])
            log('Node {} came up\n'.format(node))
        # Nodes that were deleting and now are gone:
        nodesWentDown = False
        for node in getNodesInState('D') - cloudAll:
            nodesWentDown = True
            setState(node, '')
            subprocess.Popen(['scontrol', 'update', 'nodename=' + node, 'state=down', 'reason="Deleted"'])
            log('Node {} went down\n'.format(node))
        if nodesWentDown:
            # There's a chance they'll come up later with different IPs. Restart slurmctld to avoid errors.
            subprocess.Popen(['systemctl', 'restart', 'slurmctld'])
            log('WARNING: Restarting slurmctld')
        
        # Error conditions:
        # We think they're running, but the cloud doesn't:
        for node in getNodesInState('R') - cloudRunning:
            setState(node, '')
            subprocess.Popen(['scontrol', 'update', 'nodename=' + node, 'state=down', 'reason="Error"'])
            log('ERROR: Node {} deleted outside of clic!'.format(node))
        # We think they're running, and so does the cloud, but slurm doesn't
        for node in getNodesInState('R') + cloudRunning - slurmRunning and timeInState(node) > waitTime:
            log('ERROR: Node {} is unresponsive!'.format(node))
        # Nodes are running but aren't registered:
        for node in getNodesInState('') & cloudRunning:
            log('ERROR: Encountered unregistered node {}!'.format(node))
        for node in getNodesInState('C') if timeInState(node) > 200:
            log('ERROR: Node {} hung on boot!'.format(node))

        
        # Add and delete nodes
        rJobs = os.popen('squeue -h -t r,cg,cf -o %A').read()
        qJobs = os.popen('squeue -h -t pd -o %A').read()
        
        jobsWaitingTooLong = 0
        for job in qJobs.split():
            if not job in queuedTimes:
                queuedTimes[job] = time.time()
            else:
                if time.time() - queuedTimes[job] > waitTime:
                    jobsWaitingTooLong += 1
        numIdle = parseInt(os.popen('sinfo -h -r -o %A | cut -d "/" -f 2').read())
        nodesToCreate = (jobsWaitingTooLong - numIdle - len(getNodesInState('C')) + 1) / 2
