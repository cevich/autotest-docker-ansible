Hacking
===========

Run the unittests
-------------------

This requires that ``python-unittest2`` is installed and/or
the ``unit2`` command is available.  These tests run relatively 
quickly, and do a self-sanity check on all major operational areas.

::

    $ unit2
    ...............................s......................
    ----------------------------------------------------------------------
    Ran 54 tests in 9.998s

    OK (skipped=1)


Run the CI test job
--------------------

This is a special ADEPT-job which runs entirely on the local machine,
and verifies the operations of most major plays and roles. It's much
slower than the unittests.  Optionally, it can be run with ``adept_debug``
and/or verbose mode enabled.  This is the best way to confirm the syntax,
variables, and basic playbook operations.  It requires all the prerequisites
listed for both Kommandir and Exekutir systems.

::

    $ ./test_exekutir_xn.sh
    localhost ######################################
    Parameters:
        optional = '-e some_magic_variable_for_testing='value_for_magic_variable''
        xn = 'exekutir.xn'
        workspace = '/tmp/tmp.wfyfHGypgq.adept.workspace'
        context = 'setup'

    ...cut...

    Examining exit files
    Checking kommandir discovery (before job.xn) cleanup exit file contains 0
    Checking setup exit files
    Verifying exekutir_setup_after_job.exit file contains 0
    Verifying kommandir_setup.exit file contains 0
    Checking contents of test_file_from_setup.txt
    Checking run exit files
    Verifying exekutir_run_after_job.exit file contains 0
    Verifying kommandir_run.exit file contains 0
    Checking contents of test_file_from_run.txt
    Checking cleanup exit files
    Verifying exekutir_cleanup_after_job.exit file contains 0
    Verifying kommandir_cleanup.exit file contains 0
    Checking contents of test_file_from_cleanup.txt
    All checks pass


Execution without Kommandir node 
---------------------------------

Having a Kommandir (a.k.a. "Slave") node is useful in production because it offloads
much of the grunt-work onto a dedicated system, with dedicated resources.  It also
decouples the job environment/setup from the execution environment.  However,
for testing/development purposes, the extra Kommandir setup time can be excessive.

If the local system (the Exekutir) meets all the chosen cloud, Kommandir, and job
(software) requirements, it's possible to use a "nocloud" kommandir, but still
provision and use cloud-based Peons.  The essential ingredients are:

#. Set the Exekutir's ``kommandir_groups`` (list) variable to include "nocloud"
#. All peons will be network-accessable following creation, based on
   the group in their ``peon_groups`` (list) which defines/sets
   ``cloud_environment``, ``cloud_asserts``, and ``cloud_provisioning_command``.
#. Avoid repeating any context transition more than once against, the same
   workspace.  Same for recycling ``uuid`` values.  It can be done with
   some careful manipulations, but isn't recommended or straight-forward.

Begin by creating a local workspace directory, and populating the override variables.
In this example, the default (bundled) peon definitions are used, with all
peon's members of the ``openstack`` group.  The ``openstack`` group-specific
variable ``public_peons`` is set to ensure floating IPs are allocated. 

::

    $ rm -rf /tmp/workspace
    $ mkdir /tmp/workspace
    $ export WORKSPACE=/tmp/workspace
    $
    $ vi /tmp/workspace/variables.yml
    ---
    job_path: /path/to/adept/jobs/basic
    kommandir_name_prefix: "peons-came-from-me"
    kommandir_groups:
        - nocloud
    public_peons: True   # openstack peon group specific

Setup your openstack cloud name (``default`` in this case) and credentials.
Most of these are specific to the particular openstack setup.  The file
`format and options are documented here`_.

::

    $ vi /tmp/workspace/clouds.yml
    ---
    clouds:
        default:
            auth_type: password
            auth:
                auth_url: http://example.com/v2.0
                password: foobar
                tenant_name: baz
                username: snafu
            regions:
                - Oz
            verify: False

.. _`format and options are documented here`: https://docs.openstack.org/developer/os-client-config/

Run the ADEPT ``setup`` transition.  Once this completes, a copy of all playbooks
and roles have been transfered to the workspace.  This means, any changes make
to the source, won't be realized unless you manually copy them into the correct
workspace locations.

::

    $ /path/to/adept/adept.py setup /tmp/workspace /path/to/adept/exekutir.xn
    localhost ######################################
    Parameters:
        optional = ''
        xn = 'exekutir.xn'
        workspace = '/tmp/workspace'
        context = 'setup'

    ...cut...

Optionally, execute the the ADEPT ``run`` transition and/or inspect the workspace state.

    $ /path/to/adept/adept.py run /tmp/workspace /path/to/adept/exekutir.xn
    localhost ######################################
    Parameters:
        optional = ''
        xn = 'exekutir.xn'
        workspace = '/tmp/workspace'
        context = 'run'

    ...cut...

When finished, run the ``cleanup`` transition, which should always complete
the release of successfully provisioned cloud resources, even if ``setup``
or ``run`` had failed.  If the ``adept_debug`` flag is set True,
all otherwise extranious state, source copy, and exit files will be preserved.

    $ /path/to/adept/adept.py cleanup /tmp/workspace /path/to/adept/exekutir.xn \
    -e adept_debug=True

    localhost ######################################
    Parameters:
        optional = ''
        xn = 'exekutir.xn'
        workspace = '/tmp/workspace'
        context = 'cleanup'

    ...cut...

    $ ls -la /tmp/workspace
    total 40
    drwx------.  4 user user 4096 Jan  1 00:00 .
    drwxrwxrwt. 16 root root 4096 Jan  1 00:00 ..
    -rw-rw-r--.  1 user user    1 Jan  1 00:00 ansible.cfg
    -rw-rw-r--.  1 user user    1 Jan  1 00:00 exekutir_cleanup_after_job.exit
    -rw-rw-r--.  1 user user    1 Jan  1 00:00 exekutir_cleanup_before_job.exit
    -rw-rw-r--.  1 user user    1 Jan  1 00:00 exekutir_run_after_job.exit
    -rw-rw-r--.  1 user user    1 Jan  1 00:00 exekutir_setup_after_job.exit
    drwxrwxr-x.  4 user user   81 Jan  1 00:00 inventory
    -rw-rw-r--.  1 user user    1 Jan  1 00:00 kommandir_cleanup.exit
    -rw-rw-r--.  1 user user    1 Jan  1 00:00 kommandir_run.exit
    -rw-rw-r--.  1 user user    1 Jan  1 00:00 kommandir_setup.exit
    drwxrwxr-x.  4 user user   56 Jan  1 00:00 kommandir_workspace
    drwxrwxr-x.  4 user user   81 Jan  1 00:00 roles
    lrwxrwxrwx.  1 user user   27 Jan  1 00:00 results -> kommandir_workspace/results
    -r--r--r--.  1 user user  378 Jan  1 00:00 variables.yml


Helpful References
------------------------

*  split-up host/group variables http://docs.ansible.com/ansible/intro_inventory.html#splitting-out-host-and-group-specific-data
*  magic variables http://docs.ansible.com/ansible/playbooks_variables.html#magic-variables-and-how-to-access-information-about-other-hosts
*  scoping http://docs.ansible.com/ansible/playbooks_variables.html#variable-scopes (esp. need a blurb about silent-read-only)
*  roles http://docs.ansible.com/ansible/playbooks_roles.html#roles
