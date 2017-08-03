Hacking
===========

Run the unittests
-------------------

This requires the additional test/development `prerequisites`_
These tests run relatively quickly, and only do a self-sanity check
to verify major operational areas.

::

    $ unit2
    ...............................s......................
    ----------------------------------------------------------------------
    Ran 54 tests in 9.998s

    OK (skipped=1)


Run the CI test job
--------------------

This is a special ADEPT-job which runs entirely on the local machine,
and verifies the operations of most major *exekutir* and *kommandir* plays.
It does not have perfect coverage, for example, no cloud-based resources
used.   It can be run with ``adept_debug`` and/or ``--verbose`` modes
to retain the temporary workspace for examination.

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

.. _local_kommandir:

Local Kommandir
----------------

Having a *kommandir* ("slave") node is useful in production because it offloads
much of the grunt-work onto a dedicated system, with dedicated resources.  It also
decouples the job environment/setup from the execution environment.  Using one
only makes sense in production-environments where the 5-minute setup cost can
be spread over tens or hundreds of jobs.

However, for local testing/development purposes, the extra *kommandir* setup time
can be excessive.  If the local system (the *exekutir*) meets all the chosen cloud,
*kommandir*, and job :ref:`Prerequisites`, it's possible to use the *exekutir* also as the
*kommandir*.  Note, however, the *kommandir's* ``job.xn`` transition file and playbooks will
still run from a dedicated workspace (created by the Exekutir).

Set the `Exekutir's ``kommandir_groups`` variable <kommandir_groups>`_
to include ``nocloud``.  If required, also enable
`the flag to create network-accessable peons <public_peons>`_.

::

    kommandir_groups: ["nocloud"]
    public_peons: True

.. _repeat_contexts:

Avoid repeating any context transition more than once, against the same
workspace or manually running Ansible.  Either can be done if needed,
but require some manual manipulations of files in the workspace.
It's safer to apply the ``cleanup`` context, then start over again
with ``setup`` against a fresh workspace, with a fresh `uuid`_


OpenStack Cloud
------------------

This requires that you either set the ``$OS_*`` environment variables
correctly, or dropped a ``clouds.yml`` file in the correct workspace(s).


#. Setup your OpenStack credentials via the standard ``os-client-config``
   file ``clouds.yml``, in the workspace, as show below.  The
   options are specific to your particular OpenStack setup.  See the
   `format and options, documented here <https://docs.OpenStack.org/developer/os-client-config/>`_.

    .. include:: ex_ws_setup.inc.rst

    .. include:: clouds_yml.inc.rst

#. Populate `the *exekutir's* variables <variables_reference>`_.
   In this example, the default (bundled) *peon*
   definitions are used (from ``kommandir/inventory/host_vars/``). The other values
   select the job, name the kommandir VM, enable debugging and setup subscriptions.
   The final value makes sure the *kommandir* VM has access to the same cloud for
   creating the *peons*

    ::

        $ cat << EOF > $WORKSPACE/exekutir_vars.yml
        ---
        job_path: $PWD/jobs/basic
        kommandir_name_prefix: "$USER"
        adept_debug: True
        rhsm:
            username: nobody@example.com
            password: thepassword
        extra_kommandir_setup:
            command: >
                cp "{{ hostvars.exekutir.workspace }}/clouds.yml"
                   "{{ hostvars.exekutir.kommandir_workspace }}/"
        EOF

   *Note:* If you want/need access to the peons as well, be sure to enable the
   `public_peons`_ flag.

#. Apply the ADEPT ``setup`` context.  Once this completes, a copy of all runtime
   source material will have been transferred to the workspace.  This includes
   updating initial ``exekutir_vars.yml`` and inventory files.  `As noted,
   manual changes made to the source <repeat_contexts>`_, will not be reflected
   at runtime unless the workspace is manually updated.

    .. include:: adept_setup.inc.rst

#. Apply the ADEPT ``run`` context and/or inspect the workspace state.

    .. include:: adept_run.inc.rst

#. Whether or not ``setup`` or ``run`` were successful, always apply ``cleanup``
   to release cloud resources.

    .. include:: adept_cleanup.inc.rst
