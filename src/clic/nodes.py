#!/usr/bin/env python3
import time
import re
import configparser
config = configparser.ConfigParser()
config.read('/etc/clic/clic.conf')
settings = config['Nodes']
cpuValues = settings['cpus'].replace(' ', '').split(',')
diskValues = settings['disksize'].replace(' ', '').split(',')
memValues = settings['memory'].replace(' ', '').split(',')
namescheme = config['Daemon']['namescheme']

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
    def __init__(self, namescheme, partition, num):
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
    if partition == None:
        return None
    num = int(re.search('(?<=-)\d+$', nodeName).group(0))
    node = Node(namescheme, partition, num)
    nodes.append(node)
    return node

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
