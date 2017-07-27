# CLIC
## CLuster In the Cloud

__NOTE:__ This software is under heavy development and should only be used for testing purposes!

CLIC creates a virtual, automatically resizing cluster in a cloud environment. The technologies that CLIC uses are:
  * Supported OS's: Ubuntu, Debian, CentOS
  * Queueing system: SLURM
  * File sharing: NFS through a SSH tunnel
  * Implementation languages: bash scripts for installation and python3 for execution
  * Cloud environment: Google Compute Engine (GCE)

The CLIC daemon monitors the SLURM queue. If CLIC detects that the cluster is overwhelmed by jobs, it creates new instances to handle these jobs. When the new instances come online, CLIC notifies SLURM that they are able to recieve jobs, and SLURM incorporates them into the cluster. If CLIC detects that the cluster is underutilized, it notifies SLURM that it is removing some of the idle instances, then deletes those intances from the cloud.

## Pure Cloud vs Hybrid Clusters

There are two ways of installing CLIC. One is to have both the head node and the compute nodes housed in the same cloud. Alternatively, CLIC supports a hybrid approach in which the headnode is physical (outside of the cloud) and only the compute nodes are within the cloud. This can save on costs when compared to a pure cloud cluster, but security, convenience, and reliability may suffer.

## Quickstart

1. Create a GCE instance. The name given this instance will become the base name of the cluster. For example, if you name it NAME, then instances created by CLIC will follow the pattern NAME-PARTITION-ID, where PARTITION is the SLURM partition to which the node belongs, and ID differentiates among nodes in a partition. If you are creating a cloud head node, set the API access scope to "Allow full access to all Cloud APIs"

2. Install CLIC
    * Pure Cloud: execute the `install` script on some machine other than NAME. The Google Cloud Shell works well for this purpose:  
      `./install --head NAME`  

    * Hybrid: execute the `install` script on the physical headnode:  
      `./install --head HOSTNAME --comptue NAME`  
      where HOSTNAME is the name of the headnode, and NAME is the name of the GCE instance.

3. Use sbatch to submit jobs. It takes about 2 minutes for CLIC to create cloud instances to handle jobs.

## Configuration
### clic.conf

The main configuration file is /etc/clic/clic.conf. Normally, the only part of this file that must be edited is the [Nodes] section, which describes the charictaristics of cloud nodes created by CLIC. There are three points of configuration for cloud nodes:
  * cpus
  * disksize (GB)
  * memory (standard, highmem, highcpu)

Each of these fields allows for comma separated values, and SLURM partitions will be created by CLIC for every valid combination of values. Things are done this way so that SLURM doesn't run jobs on overprovisioned nodes, which would make CLIC unable to delete them when scaling the cluster.

### Initialization scripts

When cloud nodes are created, all executable files in /etc/clic/ are copied to the node. These scripts are then run with command line arguments cpus, disksize, and memory, matching the values embedded in the partition name. See /etc/clic/example.sh for an example.

## Submitting Jobs

Partitions are named X-cpu-Y-disk-memtype (dashes inserted for clarity) where X is the number of cpus and Y is the size of the disk in GB. To submit a job for a particular machine architecture, you may specify any combination of architecture charictaristics in the job file or on the command line, eg:  
&nbsp;&nbsp;`sbatch --mincpus=4 --tmp=102400 --mem=15360 job.sh`  
The Lua script /etc/slurm/job\_submit.lua places the job in a partition that meets the requirements while minimizing cpus, memory, and disk size, in that order.

Equivalently, the name of the partition can be specified:  
&nbsp;&nbsp;`sbatch --partition=4cpu100diskstandard job.sh`  
