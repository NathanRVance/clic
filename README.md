# CLIC
## CLuster In the Cloud

__NOTE:__ This software is under heavy development and should only be used for testing purposes!

CLIC creates a virtual, automatically resizing cluster in a cloud environment. The technologies that CLIC uses are:
  * Supported OS's: Ubuntu, Debian, CentOS
  * Queueing system: SLURM
  * File sharing: NFS through a SSH tunnel
  * Implementation languages: bash scripts for installation and python3 for execution
  * Cloud environment: Google Compute Engine

The CLIC daemon monitors the SLURM queue. If CLIC detects that the cluster is overwhelmed by jobs, it creates new instances to handle these jobs. When the new instances come online, CLIC notifies SLURM that they are able to recieve jobs, and SLURM incorporates them into the cluster. If CLIC detects that the cluster is underutilized, it notifies SLURM that it is removing some of the idle instances, then deletes those intances from the cloud.

## Quickstart

1. Create a GCE instance. The name given this instance will become the base name of the cluster. For example, if you name it NAME, then instances created by CLIC will follow the pattern NAME-PARTITION-ID, where PARTITION is the SLURM partition that the node belongs to, and ID differentiates between nodes in a partition.

2. Execute the `install` script  
&nbsp;&nbsp;`./install --namescheme NAME [--cloud]`  
where
    * NAME is the hostname of the GCE instance
    * The `--cloud` flag is set if `install` is being run from NAME in GCE

3. If installing using a cloud headnode, then shut down, snapshot, and re-start the headnode. The snapshot must have the same name as the headnode so that CLIC can use it to create additional instances.

4. Use sbatch to submit jobs. It takes about 2 minutes for CLIC to create cloud instances to handle jobs.

## Configuration
### clic.conf

The main configuration file is /etc/clic/clic.conf. Normally, the only part of this file that must be edited is the [Nodes] section, which describes the charictaristics of cloud nodes created by CLIC. There are 3 points of configuration for cloud nodes:
  * cpus
  * disksize (GB)
  * memory (standard, highmem, highcpu)

Each of these fields allows for comma separated values, and SLURM partitions will be created by CLIC for every valid combination of values. Things are done this way so that SLURM doesn't run jobs on overprovisioned nodes, which would make CLIC unable to delete them when scaling the cluster.

Partitions are named X-cpu-Y-disk-memtype (dashes inserted for clarity) where X is the number of cpus and Y is the size of the disk in GB. To submit a job for a particular machine architecture, you may specify the corresponding partition, eg:  
&nbsp;&nbsp;`sbatch --partition=4cpu100diskstandard job.sh`  
Equivalently, specify individual node charictaristsics:  
&nbsp;&nbsp;`sbatch --mincpus=4 --tmp=102400 --mem=15360 job.sh`  
The Lua script /etc/slurm/job\_submit.lua places the job in the correct partition if none is specified with the --partition flag.

### Init scripts

When cloud nodes are created, all executable files in /etc/clic/ are copied to the node and run with command line arguments cpus, disksize, and memory, matching the values embedded in the partition name. See /etc/clic/example.sh for an example.
