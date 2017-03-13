from __future__ import print_function
import os
import hostlist
import tensorflow as tf
import re

## it may be useful to know that slurm_nodeid tells you which node you are one (in case there is more than one task on any given node...)
## Perhaps you could better assign parameter servers be distributed across all nodes before doubleing up on one.
class SlurmClusterManager():
    def __init__(self, num_param_servers=1, num_workers=None, starting_port=None):
        
        # Check Environment for all needed SLURM varialbes
        assert 'SLURM_JOB_NODELIST' in os.environ # SLURM_NODELIST for backwards compatability if needed.
        assert 'SLURM_TASKS_PER_NODE' in os.environ
        assert 'SLURM_PROCID' in os.environ
        assert 'SLURM_NPROCS' in os.environ
        assert 'SLURM_NNODES' in os.environ

        # Grab SLURM variables
        self.hostnames = hostlist.expand_hostlist(os.environ['SLURM_JOB_NODELIST']) # expands 'NAME1(x2),NAME2' -> 'NAME1,NAME1,NAME2'
        self.num_tasks_per_host = self._parse_slurm_tasks_per_node(os.environ['SLURM_TASKS_PER_NODE']) # expands '1,2(x2)' -> '1,2,2'
        self.my_proc_id = int(os.environ['SLURM_PROCID']) # index into hostnames/num_tasks_per_host lists
        self.num_processes = int(os.environ['SLURM_NPROCS'])
        self.nnodes = int(os.environ['SLURM_NNODES'])

        # Sanity check that everything has been parsed correctly
        assert len(self.hostnames) == len(self.num_tasks_per_host)
        assert len(self.hostnames) == self.nnodes
        assert self.num_processes == sum(self.num_tasks_per_host)

        # Numbber of PS/Workers
        # Note: I'm making the assumption that having more than one PS/node
        #       doesn't add any benefit.  It makes code simpler in self.build_cluster_spec()
        self.num_parameter_servers = min(num_param_servers, len(self.hostnames))
        if num_workers is None:
            # Currently I'm not using num_workers'
            # TODO What happens to num_workers once I allocate less PS than they requested?
            self.num_workers = self.num_processes - self.num_parameter_servers # default to all other nodes doing something

        # Default port to use
        if starting_port is not None:
            self.starting_port = starting_port # use user specified port
        else:
            self.starting_port = 2222
        

    def build_cluster_spec(self):
        # tuples of (str(Hostname:Port), JobName, TaskID) for each process
        proc_info = []
        for _ in range(self.num_processes):
            proc_info.append([None, None, None]) 

        # Assign Port# to each process according to Hostname 
        # Note: if there are multiple processes on the same hostname, 
        #       each one needs it's own port number, hence the variable name starting_port)
        pid = 0
        first_pid_per_host = {} # Reverse-Lookup map
        for cnt, hostname in zip(self.num_tasks_per_host, self.hostnames):
            first_pid_per_host[hostname] = pid
            for i in range(cnt):
                proc_info[pid][0] = "{}:{}".format(hostname, self.starting_port + i)
                pid += 1

        # Assign PSs to different physical hosts
        # TODO Maybe sorting by hostnames/task_per_hostname by tasks_per_hostname my increase performance?
        # NOTE: this code requires that the num_parameter_servers be less than or equalto the number of indificial physical nodes
        ps_strings = []
        for ps_id in range(self.num_parameter_servers):
            pid = first_pid_per_host[self.hostnames[ps_id]]
            ps_strings.append(proc_info[pid][0])
            proc_info[pid][1] = 'ps'
            proc_info[pid][2] = ps_id

        # Assign workers to the remaining open spots 
        wk_id = 0
        wk_strings = []
        for info in proc_info:
            if info[1] == None: # It's not a ps
                wk_strings.append(info[0])
                info[1] = 'worker'
                info[2] = wk_id
                wk_id += 1
        
        # Each processor: Grab your Job/TaskID
        job     = proc_info[self.my_proc_id][1]
        task_id = proc_info[self.my_proc_id][2]

        # Return it all!  :D
        cluster_spec = tf.train.ClusterSpec({'worker': wk_strings, 'ps': ps_strings})
        return cluster_spec, job, task_id

    def _parse_slurm_tasks_per_node(self, num_tasks_per_nodes):
        '''
        SLURM_TASKS_PER_NODE Comes in compressed, so we need to uncompress it:
          e.g: if slurm gave us the following setup:
                   Host 1: 1 process
                   Host 2: 3 processes
                   Host 3: 3 processes
                   Host 4: 4 processes
        Then the environment variable SLURM_TASKS_PER_NODE = '1,3(x2),4'
        But we need it to become this => [1, 3, 3, 4]
        '''
        final_list = []
        num_tasks_per_nodes = num_tasks_per_nodes.split(',')

        for node in num_tasks_per_nodes:
            if 'x' in node: # "n(xN)"; n=tasks, N=repeats
                n_tasks, n_nodes = [int(n) for n in re.findall('\d+', node)]
                final_list += [n_tasks] * n_nodes
            else:
                final_list.append(int(node))
        return final_list
