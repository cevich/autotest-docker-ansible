=====================================================
Autotest-Docker Enabled Product Testing (A.D.E.P.T.)
=====================================================

Not So Simple overview:
=======================

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

Definitions:
=============

``context``:
             The label given to the end-state upon completion of a transition.
             Analogous to a "phase", or collection of related steps. The context
             label (string) is assumed to pass unmodified, through all
             facilities (adept.py files, playbooks, scripts, etc.) and through
             all layers (original calling host, through slave, and into testing
             hosts). No facility or layer will alter the context label from
             the one originally passed into the first, lowest-level call of
             ``adept.py``.

``transition``:
                The collection of steps necessary to realize a context.
                Analogous to the act of performing all described tasks
                within a "phase" to reach some end-state of the entire
                macro-level system.  There is exactly one transition
                per context.

``setup``, ``run``, and ``cleanup``:
                                     The three context labels currently
                                     used in ADEPT.  Operationally,
                                     the ``run`` context is dependent (to some degree)
                                     on a successful ``setup`` transition.  However,
                                     the ``cleanup`` context transition must not
                                     depend on success or failure of either
                                     ``setup`` or ``run``.

``job``:
         A single, top-level invocation through all context transitions,
         concluding in a resource-clean, final end-state.  Independent
         of the existence of any results or useful data.  Assumed to not
         share any runtime data with any other job.  Except the name and
         IP address of the slave VM and perhaps the source of some
         configuration details.

``kommandir``:
               The name of the "slave" VM as referenced from within playbooks,
               adept files, and configurations.  Currently based on CentOS
               Atomic.  One kommandir VM supports use by multiple concurrent jobs.
               It is identified by a unique name - which is the means
               for concurrent jobs to obtain it's IP address.

``peon``:
          The lowest-level VM used for testing (running docker autotest).
          Assumed to only be controlled by a one-way connection by kommandir.
          Cannot and must not be able to access the kommandir or original
          execution host on it's own (i.e. top-down control only).

``slave image``:
                 Container image setup with all runtime dependencies but no data.
                 Lives on the ``kommandir``, re-built on demand. Forced to
                 have a limited lifetime to guarantee exercise of the building
                 mechanism.

``slave container``:
                     A throw-away docker container of the slave image.
                     Expected there will be possibly many of them starting,
                     running, and being removed on the ``kommandir``
                     host throughout the durations of multiple concurrent
                     jobs.  One container per transition, per job.  Guarantees
                     separation between concurrent jobs contexts.  Runtime data
                     is isolated from container image by volume mounts.

.. The quickstart section begins next

Quickstart:
===========

This is assumed to be done manually, by-hand.  For hints/techniques to automate running
jobs, see the `scripting/automation hints`_ section
 
Credentials/Secrets required: Openstack, RHSM, RHBZ, any ssh private/public key pair.

The built-in default setup executes all tests on a single CentOS peon.

Variables:
-----------

``JOB_NAME``:
              An environment variable and file-name, both with the same content.
              Should be a short, human-readable job name like: "smoke",
              "full", or "latest-build".  Should reflect some collection of
              static inputs that don't change from run to run of the same job.
              Need not be unique.  For non-automated runs, including your name
              as part of the job name will make identifying resources easier.
              e.g ``cevich_testing``

``UNIQUE_JOB_ID``:
                   An environment variable and file-name, both with the same content.
                   Should contain $JOB_NAME and some extra unique characters that
                   distinguish a single run of this job, from the next (or previous)
                   run.  "Bad Things Happen" (tm) if there is ever a clash.
                   e.g. ``cevich_testing_0001``

``KOMMANDIR_NAME``:
                    An environment variable and file-name, both with the same content.
                    The value should be unique per cloud, and a human-readable name
                    for the kommandir VM.  This value can/should be reused across
                    jobs, even concurrent executions. For testing purposes, including
                    your name in the value will make identifying the VM easier.
                    e.g. ``cevich_kommandir``

``WORKSPACE``:
               An environment variable that always points to a writable directory.
               The underlying directory path may be different depending on where
               it's referenced (i.e. which system/VM).  However, the contents are
               assumed to persist throughout the duration of a job - meaning
               all contexts and all transitions.  The exact location on the
               executing node doesn't matter. 

Preperation 
--------------

Setup ``$WORKSPACE``, bits, and keys
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

::

    $ export WORKSPACE=$(mktemp -d)
    $ cd $WORKSPACE
    $ mkdir cache
    $ git clone https://github.com/autotest/autotest.git cache/autotest
    $ git clone https://github.com/autotest/autotest-docker.git cache/autotest-docker
    $ git clone https://github.com/cevich/autotest-docker-enabled-product-testing.git cache/adept
    $ cp $HOME/.ssh/id_rsa ssh_private_key
    $ cp $HOME/.ssh/id_rsa.pub ssh_private_key.pub
    $ chmod 600 ssh_private*

Define Job Variables
~~~~~~~~~~~~~~~~~~~~~~~

::

    $ cd $WORKSPACE
    $ export JOB_NAME=$(echo "cevich_testing" | tee JOB_NAME)
    $ export UNIQUE_JOB_ID=$(echo "${JOB_NAME}_0001" | tee UNIQUE_JOB_ID)
    $ export KOMMANDIR_NAME=$(echo "cevich_kommandir" | tee KOMMANDIR_NAME)
    $ cp cache/adept/roles/subscribed/defaults/main.yml cache/adept/group_vars/all/rhsm

Setup secrets / credentials
~~~~~~~~~~~~~~~~~~~~~~~~~~~~

**N/B:** *replace all variable values that begin with* ``_private``.  For ``rhsm``, fill
in username/password at a minimum. ``$EDITOR`` is assumed set to vim, emacs, etc.

::

    $ cd $WORKSPACE/cache/adept/group_vars
    $ $EDITOR  all/rhsm openstack kommandir


Setup and Test Execution:
---------------------------


::

    $ cd $WORKSPACE
    $ cache/adept/adept.py setup . cache/adept/files/kommandir.xn
    $ cache/adept/adept.py run . cache/adept/files/kommandir.xn


Cleanup (optional; does **not** remove kommandir VM)
--------------------------------------------------------------------------

::

    $ cd $WORKSPACE
    $ ssh -tt -i ssh_private_key -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null \
        root@$(cat KMNDRIP) \
        /mnt/workspaces/$UNIQUE_JOB_ID/adept/adept.py \
        cleanup \
        /mnt/workspaces/$UNIQUE_JOB_ID/ \
        /mnt/workspaces/$UNIQUE_JOB_ID/adept/files/slave_container.xn
    $ cache/adept/adept.py cleanup . cache/adept/files/kommandir.xn


Debuggging Hints
-----------------

*  Add one or more ``-v`` to the **end** of any/all ``adept.py`` command lines.
*  You can override the contents of ``variables.yml`` by adding ``-e`` (Ansible)
   options to the **end** of any ``adept.py`` command line.
*  Ssh into the kommandir VM (an Atomic host) and inspect files under
   ``/mnt/workspaces/$UNIQUE_JOB_ID/``.
*  Make sure the contents of all ``VARIABLES`` (e.g. ``UNIQUE_JOB_ID``) files is correct.
*  Within all playbooks, the variable ``adept_job`` holds the value of ``$UNIQUE_JOB_ID``.
*  Within the containers on the kommandir, ``/var/lib/workspace`` and ``/var/lib/adept``
   are volumes (bind mounts).  Both come from corresponding directories on the
   kommandir host under ``/mnt/workspace/$UNIQUE_JOB_ID``.
*  Never, ever, ever, ever recycle ``$UNIQUE_JOB_ID`` with the same kommandir VM,
   and especially for concurrent jobs (don't do it!).
*  It's perfectly safe to destroy the kommandir VM and it's storage volume at
   any time.  Preferably when there are no jobs running.  It will be re-created
   the next time the ``setup`` context completes.


Scripting/Automation Hints
---------------------------

* Use a directory (outside of ``$WORKSPACE``) named by the ``$JOB_NAME`` to store
  configuration details.
* Customize your jobs with their own ``variables.yml`` file (copy into workspace as
  part of preparation).  This is the primary mechanism by which Ansible variables are
  overridden.
* Store credential values outside of ``variables.yml`` in a file shared between jobs.
  e.g. ``secrets.yml``.  Copy this file into ``$WORKSPACE/cache/adept/group_vars/all/``
  as part of preparation steps.
* When no kommandir VM exists, it's possible for concurrent jobs to clash during
  the ``setup`` context transition.  External (to ``adept.py``) locking (e.g. ``flock``)
  can be used to prevent this.
* You can quickly customize Docker Autotest's ``control.ini`` and/or ``subtests.ini``
  on all peons by setting ``custom_subtests_ini_j2`` in your ``variables.yml`` file.
  It's value must be the path to a directory containing Jinja2 templates for either/both
  template files. The default templates are under
  ``$WORKSPACE/cache/adept/roles/autotested/templates/``.
* The definitions for peons is maintained in ``$WORKSPACE/cache/adept/vars/``.
  Their mapping to cloud images is maintained in
  ``$WORKSPACE/cache/adept/group_vars/openstack`` (keyed by peon ``defaults`` and
  ``version`` value).
* There are hooks for customizing nearly every aspect of peon and Docker Autotest
  installation/setup.  e.g. overwriting/changing files under
  ``$WORKSPACE/cache/adept/group_vars``.
* Custom groups may be added with their own Ansible variable values by creating
  a directory under ``$WORKSPACE/cache/adept/group_vars/``.  Any peons which should
  receive those variables must be made a group member by adding the group (directory)
  name to it's ``extra_groups`` list.
