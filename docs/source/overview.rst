Overview
===========

FIXME:  rough-draft

ADEPT is an executable (``adept.py``), set of playbooks, and collection of
configurations.  The entry-point is assumed to be a linux host with python 2.7
and ansible 1.9 (or later) and basic/old cloud provisioning tooling.  Currently
only openstack/nova is supported.

On execution from the initial (limited) host, it creates a shared "slave" VM 
if one doesn't already exist.  From the slave VM, it creates further VMs for
testing.  The testing VMs run Docker Autotest, and the results are synchronized
back to the original entry-point host (the one that created the "slave" VM).
Finally / optionally, the test VMs are all destroyed.

The intended use-case is execution from one or more concurrent Jenkins jobs.
Each is expected to add or override various Ansible variables to accomplish
some specific testing goal (unless testing the "everything" default).  There
are also a small number of environment variables used, along with named
files needed for bootstrapping and low-level control.

These and other files are expected to exist in a storage space (``$WORKSPACE``)
which will persist throughout the entire duration of a single job-run.  A
job-run is assumed to contain multiple, separate, shell invocations of the
adept.py executable.  Finally, the primary output is stored under the ``results``
directory.  Though the persistent storage remains synchronized from the slave
throughout the job's lifetime.
