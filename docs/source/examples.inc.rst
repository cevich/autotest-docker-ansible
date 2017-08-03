Examples
==============

This section provides examples covering various usages and scenarios.
They should all be taken as general guidelines, since they easily
become out of date. If you notice a discrepancy, raise an issue
regarding it.

Adding a public job
--------------------

This example shows how to add a new public job into the ADEPT repository.
It's possible to store job details elsewhere, as
`documented here <Adding a private job>`_.

#.  The first step for any new job is to decide on its `name <job_name>`_,
    and what its speciality is.  Begin by creating a subdirectory,
    and a ``README`` (jinja2 template) to describe its purpose.  The ``README``
    will be rendered into the results directory of the workspace for
    reference.  In this example, a job called ``example`` will be created.

    ::

        $ mkdir -p jobs/example

        $ cat << EOF > jobs/example/README
        This job ({{ job_name }}) is intended to demonstrate
        adding a simple job.  If it's found in production,
        somebody has made a terrible, terrible mistake.

        (src: {{ job_path }}/{{ job_docs_template_src }})
        EOF

#.  Now you need to determine which aspects of
    `the kommandir directory you want overwritten <directory_layout>`_.
    Start with identifying the *peons* you need created and setup.
    For this example, we'll limit the selection to only a single peon.
    Note, it's also possible to use custom *peon* definitions
    by also adding/overriding files in the job's ``inventory/host_vars``
    subdirectory.

    ::

        $ ls kommandir/inventory/host_vars
        ...many...
        fedora-25-docker-latest.yml    # The one we'll use here
        ...others...

        $ mkdir -p jobs/example/inventory

        $ cat << EOF > jobs/example/inventory/peons
        [peons]
        fedora-25-docker-latest
        EOF

#.  In this example, there's an additional Ansible Role we'd like
    to apply after all the default plays.  Since the
    default playbooks are all renamed with a ``default_`` prefix
    (``exekutir/roles/exekutir_workspace_setup`` role),
    we can simply overwrite ``setup.yml`` to include ``default_setup.yml``
    and then apply our special role.

    ::

        $ mkdir -p jobs/example/roles/frobnicated/tasks

        $ cat << EOF > jobs/example/roles/frobnicated/tasks/main.yml
        ---

        - name: Make docker daemon run in debug mode
          lineinfile:
            path: /etc/sysconfig/docker
            regexp: "^OPTIONS=[\\'\\"]?(.*)[\\'\\"]?"
            line: "OPTIONS='\\1 --debug=true --log-level=debug'"

        - name: Docker daemon is restarted to reload changed options
          service:
            name: docker
            state: restarted

        EOF

        $ cat << EOF > jobs/example/setup.yml
        ---

        # First do all the original, default plays.
        - include: default_setup.yml

        # Now apply the new frobnicated role
        - hosts: peons
          vars_files:
            - kommandir_vars.yml
          roles:
            - frobnicated
        EOF

#.  There's no reason to go crazy with debug-mode tests, so
    we'll just re-use whatever the basic job has going for it.

    ::

        $ ln -s ../basic/kommandir_vars.yml ../basic/templates jobs/example/


#.  Finally, the last step is to make sure the new job works.  This
    should be performed on a system which meets the
    `Testing/Development prerequisites <prerequisites>`_.

    .. include:: ex_ws_setup.inc.rst

    .. include:: clouds_yml.inc.rst

    A simple ``$WORKSPACE/exekutir_vars.yml`` causes the *exekutir*
    to run the example job.  See the `variables_reference`_ for
    more details.

    ::

        $ cat << EOF > $WORKSPACE/exekutir_vars.yml
        kommandir_groups: ["nocloud"]
        public_peons: True
        job_path: $PWD/jobs/example
        kommandir_name_prefix: "$USER"
        extra_kommandir_setup:
            command: >
                cp "{{ hostvars.exekutir.workspace }}/clouds.yml"
                   "{{ hostvars.exekutir.kommandir_workspace }}/"
        EOF

    Then we kick it off.

    .. include:: adept_setup.inc.rst

    .. include:: adept_run.inc.rst

    .. include:: adept_cleanup.inc.rst


Adding a private job
----------------------

In certain cases, it's desireable for the details of a particular job to live outside of the
ADEPT repository.  In this case, the steps are exactly the same as `Adding a public job`_
except for one / possibly-two variables in ``exekutir_vars.yml``:

    ::

        job_path: /path/to/job/something/else
        job_name: something

Here, it was necessary to set both `job_name`_ and `job_path`_.  If only the later was set,
the ``job_name`` would have default to ``else`` instead of ``something``.  See the
`variables_reference`_ for more information
