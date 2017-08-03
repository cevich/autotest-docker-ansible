Operational Overview
=====================

This is a general, high-level outline of key steps performed during the three
standard transitions (*setup*, *run* and *cleanup*).  It omits many
small details, but the overall sequence should more/less match reality.

The names in parenthesis following each bullet's text denote the ``adept.py``
transition file (``*.xn``), or the source Ansible role or script.

.. _tsct:

The *setup* context transition
-------------------------------

#. Fundamental setup of *exekutir's* ssh keys, and copying the ``exekutir/`` directory
   into `workspace`_.  (``exekutir.xn``)

    * Copy local ``exekutir/*`` (form repo.) to `workspace`_.

    * Drop default ``{{workspace}}/exekutir_vars.yml`` if not present.

    * Copy ``$ANSIBLE_PRIVATE_KEY_FILE`` (and ``.pub``) or
      generate new ``{{workspace}}/ssh/exekutir_key``.

#. Intermediate *exekutir* setup, check Ansible version, setup
   separate `kommandir_workspace`_ directory.
   (``exekutir/roles/exekutir_workspace_setup`` role)

    * Copy ``kommandir/*`` (form repo.) to local ``{{kommandir_workspace}}``

    * Duplicate all default playbooks so they may be both overridden, and re-used if needed.
      i.e.,
      ``{{kommandir_workspace}}/*.yml --> {{kommandir_workspace}}/default_*.yml``

    * Copy directory contents pointed to by `job_path`_ to `kommandir_workspace`_,
      overwriting any files already there (i.e., from the ``kommandir/*`` source).

    * Check/Modify/Lock-down ``{{workspace}}/exekutir_vars.yml`` and
      ``{{kommandir_workspace}}/kommandir_vars.yml``.

    * Generate unique ssh key for *kommandir* to use for accessing *peons*
      in ``{{workspace}}/kommandir_workspace/ssh/kommandir_key``

.. _kommandir_discovered:

#. Create or discover the *kommandir*.
   (``exekutir/roles/kommandir_discovered`` role)

    * The *exekutir* has set the *kommandir's* Ansible group membership from contents
      of the `kommandir_groups`_ list.  (``exekutir/roles/common`` role)

    * The `cloud_provisioning_command`_ is executed,
      with its ``stdout`` parsed as a YAML dictionary, updating
      ``{{workspace}}/inventory/host_vars/kommandir.yml``

    * Membership in `the ``nocloud`` Ansible group <local_kommandir>`_ will
      always cause the *kommandir* to be the same host as the *exekutir*
      (i.e., ``ansible_host: localhost``).

#. Complete *kommandir* VM setup (if needed), install packages,
   setup storage, etc. (``exekutir/roles/installed`` and ``kommandir_setup`` roles)

#. Finalize the local or remote workspace for the *kommandir*.
   (``exekutir/roles/kommandir_workspace_update`` role)

    * A remote *kommandir* has a `user named ``{{uuid}}`` created <uuid>`_.  The
      user's ssh ``authorized_keys`` is updated with the contents from
      ``$WORKSPACE/ssh/exekutir_key.pub``

    * Remote *kommandir's* ``/home/{{uuid}}`` (its `workspace`_) destructively
      synchronized from the *exekutir's* ``{{kommandir_workspace}}`` copy.

    * Shell-module arguments in `extra_kommandir_setup`_ are executed.

#. Run ``job.xn`` on *kommandir* (local or remote).
   (``exekutir.xn``)

    * This transition file may have been overridden by a copy from `job_path`_.

    * The default executes the ``setup.yml`` playbook, which creates and
      configures any *peons* that are members of the "*peons*" Ansible group

    * For a remote *kommandir*, the `uuid`_ user is used for execution.

#. For a remote *kommandir*, synchronize ``/home/{{uuid}}`` (its `workspace`_)
   back down to the *exekutir's* ``{{kommandir_workspace}}`` copy.
   (``exekutir/roles/kommandir_to_exekutir_sync`` role)

.. _trct:

The *run* context transition
-----------------------------

#. Create or discover the *kommandir* VM (if needed), set it up,
   install packages, etc.

#. Run ``job.xn`` on *kommandir* (local or remote).
   The default copy simply executes the ``run.yml`` playbook.
   (``exekutir.xn``)

#. For a remote *kommandir*, synchronize ``/home/{{uuid}}`` (its `workspace`_)
   back down to the *exekutir's* ``{{kommandir_workspace}}`` copy.
   (``exekutir/roles/kommandir_to_exekutir_sync`` role)

.. _tcct:

The *cleanup* context transition.
----------------------------------

**N/B:** This should always run, whether or not any other contexts were
successful.  It may not exit successfully, but it must never orphan
a remote *kommandir* or any *peons*.

#. Create or discover the *kommandir* VM (if needed), set it up,
   install packages, etc.

#. Run ``job.xn`` on *kommandir* (local or remote).
   The default copy simply executes the ``cleanup.yml`` playbook.
   (``exekutir.xn``)

#. For a remote *kommandir*, synchronize ``/home/{{uuid}}`` (its `workspace`_)
   back down to the *exekutir's* ``{{kommandir_workspace}}`` copy.
   (``exekutir/roles/kommandir_to_exekutir_sync`` role)

#. Examine the state of the remote *kommandir*.  If it was installed/setup more than a
   few days ago (or the `stonith`_ flag is ``True``) then
   destroy it by executing the `cloud_destruction_command`_.
   (``exekutir/roles/kommandir_destroyed/`` role)

#. If the *kommandir* was remote, or `adept_debug`_ is not set,
   prune the workspace of any unnecessary or files with sensitive
   contents (usernames/passwords) as set by the `cleanup_globs`_.
   (``exekutir/roles/workspace_cleanup`` role)
