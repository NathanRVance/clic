# CLIC
## CLuster In the Cloud

__NOTE:__ This software is under heavy development and should only be used for testing purposes!

CLIC creates a virtual, automatically resizing cluster in a cloud environment (currently supports only GCE). The technologies that CLIC uses are:
  * Supported OS's: Ubuntu, Debian, CentOS
  * Queueing system: SLURM
  * File sharing: NFS through a SSH tunnel
  * Implementation languages: bash scripts for installation and python 3 for execution
  * Cloud environment: Google Compute Engine

## Quickstart

1. Create a GCE instance. The name given this instance will become the base name of the cluster. For example, if you name it NAME, then instances created by CLIC will be NAME00, NAME01, and so forth.

2. Execute the `install` script  
&nbsp;&nbsp;`./install --user USER --namescheme NAME [--cloud]`  
where
    * USER is a user on the GCE instance
    * NAME is the hostname of the GCE instance
    * The `--cloud` flag is set if `install` is being run from NAME in GCE

3. If installing using a cloud headnode, then shut down, snapshot, and re-start the headnode. The snapshot must have the same name as the headnode so that CLIC can use it to create additional instances.

4. Use sbatch to submit jobs. It takes about 2 minutes for CLIC to create cloud instances to handle jobs.

## Behind the Scenes

CLIC is a daemon that monitors the SLURM queue. If CLIC detects that the cluster is overwhelmed by jobs, it creates new instances to handle these jobs. When the new instances come online, CLIC notifies SLURM that they are able to recieve jobs, and SLURM incorporates them into the cluster. If CLIC detects that the cluster is underutilized, it notifies SLURM that it is removing some of the idle instances, then deletes those intances from the cloud.
