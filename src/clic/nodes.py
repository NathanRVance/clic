#!/usr/bin/env python3
import time

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
