#!/usr/bin/env python3
from nodes import Node
from nodes import Partition

class abstract_queue:
    def __init__(self):
        pass
    def idle():
        # Return: [nodeName, ...]
        pass
    def running():
        # Return: [nodeName, ...]
        pass
    def configChanged():
        # Called whenever a node goes up or down
        pass
    def restart(isHeadnode):
        # Called to start the queue software, or when queue is misbehaving
        pass
    def nodeStateChanged(node):
        pass
    def queuedJobs():
        # Return: [[jobNum, partitionName], ...]
        pass
    
