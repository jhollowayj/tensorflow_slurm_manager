# tensorflow_slurm_manager
working on a cluster manager for TF

Since graduating from the university that provided a slurm cluster, I no longer have access to a slurm cluster.  Therefore, I haven't been maintaining this code base.

The general idea of the script is to grab the data provided by slurm in the form of environmental variables.  From there,  it will assign servers to each hostname, trying to not place multiple `ps`'s on the same node.  The remaining nodes will be made `worker` nodes.

I have not tested this on any other slurm clusters apart from https://marylou.byu.edu/
There may be environement variable differences that you may need to look into on your specific cluster.
