# CLIC
## CLuster In the Cloud

__NOTE:__ This software is under heavy development and should only be used for testing purposes!

CLIC creates a virtual, automatically resizing cluster in a cloud environment (currently GCE). The technologies that CLIC uses are:
  * Supported OS's: Ubuntu, Debian, CentOS
  * Queueing system: SLURM
  * Cloud environment: Google Compute Engine

## Quickstart

1. Create a GCE instance

2. Execute the `install` script  
&nbsp;&nbsp;`./install --user USER --namescheme NAME [--cloud]`  
where
  * USER is a user on the GCE instance
  * NAME is the hostname of the GCE instance
  * The `--cloud` flag is set if `install` is being run from NAME in GCE

3. If installing using a cloud headnode, shut down, snapshot, and re-start the headnode.

4. Use sbatch to submit jobs. It takes about 2 minutes for CLIC to create cloud instances to handle jobs.
