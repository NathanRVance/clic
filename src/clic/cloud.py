#!/usr/bin/env python3
from clic import nodes
import time
import logging as loggingmod
logging = loggingmod.getLogger('cloud')
logging.setLevel(loggingmod.WARNING)

def getCloud():
    return gcloud()

class abstract_cloud:
    def __init__(self):
        pass
    def makeImage(self, instanceName, recreateInstance):
        pass
    def create(self, node):
        pass
    def delete(node):
        pass
    def deleteDisk(diskName):
        pass
    def getDisks():
        # Return: [diskName, ...]
        pass
    def getSshKeys():
        # Return: [[keyUser, keyValue], ...]
        pass
    def setSshKeys(keys):
        # keys: [[keyUser, keyValue], ...]
        pass
    def nodesUp(self, running):
        # Return: [{'node' : node, 'name': name, 'running' : True|False, 'ip' : IP} ...]
        pass


class gcloud(abstract_cloud):
    # Docs: https://developers.google.com/resources/api-libraries/documentation/compute/v1/python/latest/
    def __init__(self):
        import configparser
        config = configparser.ConfigParser()
        config.read('/etc/clic/clic.conf')
        settings = config['Cloud']
        self.project = settings['project']
        self.zone = settings['zone']
        self.image = settings['image']
        import googleapiclient.discovery
        # Must first do sudo gcloud auth application-default login
        self.api = googleapiclient.discovery.build('compute', 'v1')

    def isDone(self, operation):
        from googleapiclient.errors import HttpError
        # There's probably some elegant way to do this. I don't know that way.
        try:
            return self.api.zoneOperations().get(project=self.project, zone=self.zone, operation=operation['name']).execute()['status'] == 'DONE'
        except HttpError:
            return self.api.globalOperations().get(project=self.project, operation=operation['name']).execute()['status'] == 'DONE'

    def wait(self, operation):
        while True:
            if self.isDone(operation):
               break
            time.sleep(1)

    def makeImage(self, instanceName, recreateInstance=False):
        diskName = [disk for disk in self.api.instances().get(project=self.project, zone=self.zone, instance=instanceName).execute()['disks'] if disk['boot']][0]['deviceName']
        print("Setting disk autodelete to False")
        self.wait(self.api.instances().setDiskAutoDelete(project=self.project, zone=self.zone, instance=instanceName, autoDelete=False, deviceName=diskName).execute())
        
        # Grab instance data to recreate it later
        machineType = self.api.instances().get(project=self.project, zone=self.zone, instance=instanceName).execute()['machineType']

        print("Deleting instance")
        self.wait(self.deleteName(instanceName))
        # Create the image
        self.diskToImage(diskName)

        if recreateInstance:
            print("Recreating instance")
            config = {'name': instanceName, 'machineType': machineType,
                'disks': [
                    {
                        'boot': True,
                        'autoDelete': True,
                        'deviceName': diskName,
                        'source': 'projects/{0}/zones/{1}/disks/{2}'.format(self.project, self.zone, diskName)
                    }
                ],
                "serviceAccounts": [ { "scopes": [ "https://www.googleapis.com/auth/cloud-platform" ] } ],
                # Specify a network interface with NAT to access the public
                # internet.
                'networkInterfaces': [{
                    'network': 'global/networks/default',
                    'accessConfigs': [
                        {'type': 'ONE_TO_ONE_NAT', 'name': 'External NAT'}
                    ]
                }]
            }
            self.wait(self.api.instances().insert(project=self.project, zone=self.zone, body=config).execute())

    def diskToImage(self, diskName):
        print("Creating image")
        self.wait(self.api.images().insert(project=self.project, body={
                'sourceDisk' : 'zones/{0}/disks/{1}'.format(self.zone, diskName),
                'name' : self.image,
                'family' : self.image
            }).execute())

    def create(self, node):
        try:
            # Get the latest image
            image_response = self.api.images().getFromFamily(project=self.project, family=self.image).execute()
            source_disk_image = image_response['selfLink']
            machine_type = 'zones/{0}/machineTypes/n1-{1}-{2}'.format(self.zone, node.partition.mem, node.partition.cpus)
            from pathlib import Path
            from pwd import getpwnam
            cmds = ['index=2000; for user in `ls /home`; do usermod -o -u $index $user; groupmod -o -g $index $user; let "index += 1"; done']
            for path in Path('/home').iterdir():
                if path.is_dir():
                    localUser = path.parts[-1]
                    try:
                        uid = getpwnam(localUser).pw_uid
                        cmds.append('sudo usermod -o -u {0} {1}'.format(uid, localUser))
                        gid = getpwnam(localUser).pw_gid
                        cmds.append('sudo groupmod -o -g {0} {1}'.format(gid, localUser))
                    except KeyError:
                        continue
            config = {'name': node.name, 'machineType': machine_type,
                'disks': [
                    {
                        'boot': True,
                        'autoDelete': True,
                        'initializeParams': {
                            'diskSizeGb': int(node.partition.disk * 1.1),
                            'sourceImage': source_disk_image,
                        }
                    }
                ],
                'metadata': {
                    'items': [
                        {
                            'key': 'startup-script',
                            'value': '#! /bin/bash\n{}'.format('\n'.join(cmds))
                        }
                    ]
                },
                # Specify a network interface with NAT to access the public
            # internet.
                'networkInterfaces': [{
                    'network': 'global/networks/default',
                    'accessConfigs': [
                        {'type': 'ONE_TO_ONE_NAT', 'name': 'External NAT'}
                    ]
                }]
            }
            return self.api.instances().insert(project=self.project, zone=self.zone, body=config).execute()
        except Exception as e:
            logging.error(traceback.format_exc())

    def delete(self, node):
        return self.deleteName(node.name)

    def deleteName(self, name):
        try:
            return self.api.instances().delete(project=self.project, zone=self.zone, instance=name).execute()
        except Exception as e:
            logging.error(traceback.format_exc())

    def deleteDisk(self, diskName):
        from googleapiclient.errors import HttpError
        try:
            return self.api.disks().delete(project=self.project, zone=self.zone, disk=diskName).execute()
        except Exception as e:
            logging.error(traceback.format_exc())
    
    def getDisks(self):
        try:
            return [disk['name'] for disk in self.api.disks().list(project=self.project, zone=self.zone).execute().get('items', [])]
        except Exception as e:
            logging.error(traceback.format_exc())
            return []
    
    def getSshKeys(self):
        keys = []
        try:
            for key in next(value['value'] for value in self.api.projects().get(project=self.project).execute()['commonInstanceMetadata']['items'] if value['key'] == 'sshKeys').split('\n'):
                keys.append(key.split(':', 1))
        except Exception as e:
            logging.error(traceback.format_exc())
        return keys

    def setSshKeys(self, keys):
        try:
            current = self.api.projects().get(project=self.project).execute()['commonInstanceMetadata']
            formatKeys = [':'.join(key) for key in keys]
            next(value for value in current['items'] if value['key'] == 'sshKeys')['value'] = '\n'.join(formatKeys)
            self.wait(self.api.projects().setCommonInstanceMetadata(project=self.project, body=current).execute())
        except Exception as e:
            logging.error(traceback.format_exc())

    def nodesUp(self, running):
        try:
            allNodes = []
            for item in self.api.instances().list(project=self.project, zone=self.zone).execute().get('items', []):
                node = {'node' : nodes.getNode(item['name']), 'name' : item['name'], 'running' : item['status'] == 'RUNNING'}
                if node['running']:
                    node['ip'] = item['networkInterfaces'][0]['accessConfigs'][0]['natIP']
                else:
                    node['ip'] = ''
                allNodes.append(node)
            if not running:
                return allNodes
            else:
                return [node for node in allNodes if node['running']]
        except Exception as e:
            logging.error(traceback.format_exc())

def main():
    import argparse
    parser = argparse.ArgumentParser(description='Execute cloud API commands')
    from clic import version
    parser.add_argument('-v', '--version', action='version', version=version.__version__)
    image = parser.add_argument_group()
    image.add_argument('--image', metavar='NAME', nargs=1, help='Create an image from NAME')
    image.add_argument('--recreate', action='store_true', help='Recreate NAME after creating an image')
    args = parser.parse_args()

    if args.image:
        getCloud().makeImage(args.image[0], args.recreate)
