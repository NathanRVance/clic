#!/usr/bin/env python3
from setuptools import setup

setup(
        name='clic',
        version='0.0.5',
        description='CLuster In the Cloud',
        long_description='Dynamically resizing high throughput cloud computing',
        url='https://github.com/nathanrvance/clic',
        author='Nathan Vance',
        author_email='natervance@gmail.com',
        license='MIT',
        classifiers=['Development Status :: 2 - Pre-Alpha', 'Intended Audience :: Science/Research', 'Topic :: System :: Clustering', 'License :: OSI Approved :: MIT License', 'Programming Language :: Python :: 3 :: Only'],
        keywords='dynamic high-performance cloud computing',
        packages=['clic'],
        install_requires=['rpyc', 'Flask', 'ipgetter'],
        entry_points={
            'console_scripts': [
                'clic = clic.clic:main',
                'clic-copyid = clic.copyid:main',
                'clic-initnode = clic.initnode:main',
                'clic-mount = clic.mount:main',
                'clic-nodesup = clic.nodesup:main',
                'clic-ssh = clic.pssh:main',
                'clic-synchosts = clic.synchosts:main',
                'clic-web = clic.web:launch',
                ]
            }
        )
