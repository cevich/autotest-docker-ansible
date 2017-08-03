Topology
==========

Systems
--------

    ::

        exekutir --> kommandir --> peon
                               \
                                -> peon
                               \
                                -> peon

**-or-**

    ::

        exekutir/kommandir --> peon
                           \
                            -> peon
                           \
                            -> peon

.. _directory_layout:

Directory Layout
------------------

``docs/``
    Source for all documentation input and output.

``exekutir/``
    `Standard Ansible directory layout`_, dedicated
    specifically for use by the *exekutir* host.  Some roles are shared by
    the *kommandir*, but all contents are limited by a reduced set of :ref:`prerequisites`.
    This directory is transferred verbatim to the *exekutir's* `workspace`_
    during :ref:`The setup context transition <tsct>`.

``kommandir/``
    `Standard Ansible directory layout`_, dedicated
    specifically for use by the *kommandir* and *peons*.  This
    directory is transferred to `kommandir_workspace`_ on the *exekutir*
    and becomes `workspace`_ on the *kommandir*.

    Any/all files in the copy may be overridden by files
    from `job_path`_.  The most important of which is ``job.xn``.
    This is the primary entry point on the *kommandir* for the job.

.. _job_path_dir:

`job_path`_
    Sparse `standard Ansible directory layout`_, dedicated
    to one or more jobs.  Its contents will overwrite any identically named files
    already copied to the `kommandir_workspace`_, on the *exekutir*.  However,
    copies of all the default playbooks are made with a ``default_`` prefix.
    This allows customized ``setup.yml``, ``run.yml``, and ``cleanup.yml`` to
    re-use the defaults if/where needed.

``jobs/``
    Default directory containing public job definition subdirectories,
    e.g., subdirectories that `job_path`_ could reference.
