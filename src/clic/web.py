#!/usr/bin/env python3
import rpyc
from flask import Flask
app = Flask(__name__)

c = rpyc.connect('localhost', 18861)

def formatNode(node):
    if node.state != '':
        return 'Name: <b>{0}</b>, State: "{1}"<br>'.format(node.name, node.state)
    return ''

@app.route('/')
def main():
    return 'CLIC: CLuster In the Cloud<br>'.format(len(c.root.getNodes())) + ''.join([formatNode(node) for node in c.root.getNodes()])

def launch():
    if __name__ == '__main__':
        app.run(host='0.0.0.0')
