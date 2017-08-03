ADEPT Variables Reference
==========================

From the perspective of a task in a playbook, the `lookup order is defined
by Ansible's documentation`_.  This reference is just an overview of some
of the common variables used throughout ADEPT's plays and tasks.

.. _`lookup order is defined by Ansible's documentation`: http://docs.ansible.com/ansible/playbooks_variables.html#variable-precedence-where-should-i-put-a-variable

High-level Variables
---------------------

Use of variable-overrides on the Ansible command-line is highly discouraged.
It has a very hard, non-obvious side-effect, which can make debugging very
difficult:  It forces those variables to be read-only, and silently
fails to change their contents.  Instead, there are two high-level
YAML-dictionary variable files guaranteed to exist in `workspace`_.

``exekutir_vars.yml``
    This file's variables are included in every play that runs on the *exekutir*.
    Whatever its original source, the *exekutir's* ``exekutir_workspace_setup``
    role will manipulate its contents during *setup*, to ensure consistency of
    critical variables like `uuid`_.

``kommandir_vars.yml``
    This only resides within the `kommandir_workspace`_,
    but may have originated from inside `job_path`_, copied by `extra_exekutir_setup`_,
    or `extra_kommandir_setup`_. It is included by every default play that runs on
    the *kommandir*.  In all cases, the *exekutir's* ``exekutir_workspace_setup``
    role will always create and manipulate its contents `during *setup* <tsct>`_ along
    with hard-coding critical values, like `uuid`_.

.. _variables_reference:

Low-level Variables
--------------------

Descriptions of specific, widely used or very important variables are defined below.
This includes variables defined by tasks, playbooks, ``host_vars`` and ``group_vars``
files.  General guidance is to define a variable in one place, which is as close
to its usage-context as possible.

For example, if a variable is specific to a...

*  ...playbook, it should wind up in ``kommandir_vars.yml`` or ``exekutir_vars.yml``.
*  ...role, place it in that role's ``defaults/main.yml`` or ``vars/main.yml``.
*  ...group of hosts, define it under a named group (subdirectory) of ``inventory/group_vars``.
*  ...specific host, define it under that hosts ``inventory/host_vars``.
*  ...one or more tasks, use ``set_facts`` in the specific role, or the "common" role.

..

.. _adept_debug:

``adept_debug``
    Boolean, defaults to ``False``.
    *Exekutir's* value copied to and overrides *kommandir's*.
    Enables many Ansible ``debug``
    statements across many roles that display variable values.  Also disables
    removing files during `the *cleanup* transition <tcct>`_.

``cleanup``
    Boolean, defaults to ``True``
    *Exekutir's* value copied to *kommandir's*.
    Enables/Disables removal of all *peons* by the *kommandir*,
    during `the *cleanup* transition <tcct>`_.
    See also, `stonith`_.

.. _cleanup_globs:

``cleanup_globs``
    List, defaults to ``[]``.
    Not shared between *exekutir* and *kommandirs*
    A list of strings, each interpreted as a shell-glob, relative to ``workspace``.
    Intended to mark certain sensitive files/directories for removal during
    `the *cleanup* transition <tcct>`_.  See `adept_debug`_.

.. _cloud_environment:

``cloud_environment``
    Dictionary, defaults to ``{}``.
    Not shared between *exekutir* and *kommandir*.
    Defines the environment variable names and values that should be set
    when executing `cloud_provisioning_command`_ and
    `cloud_destruction_command`_.

``cloud_asserts``
    List, defaults to ``[]``.
    Not shared between *exekutir* and *kommandir*.
    List of Ansible conditionals (with jinja2 template resolution) which must all
    evaluate true, prior to executing `cloud_provisioning_command`_
    and `cloud_destruction_command`_.

.. _cloud_provisioning_command:

``cloud_provisioning_command``
    Dictionary, defaults to ``Null``.
    Not shared between *exekutir* and *kommandir*.
    Same keys/values used for the Ansible ``shell`` module, excluding ``environment`` which is
    brought in by `cloud_environment`_.  Upon success, ``stdout`` is expected to be a valid
    YAML dictionary document.  All values in that document will replace the corresponding keys
    in the `hostvarsfile`_ variable.

.. _cloud_destruction_command:

``cloud_destruction_command``
    Dictionary, defaults to ``Null``.
    Not shared between *exekutir* and *kommandir*.
    Same as `cloud_provisioning_command`_, but defines the command
    for removing the host.

``empty``
    Defines the set of values which are to be considered "not set" or "blank".  This
    is used as a convenience value for quickly testing whether or not a variable is
    not a boolean, and contains something useful.

.. _extra_exekutir_setup:

``extra_exekutir_setup``
    Dictionary, defaults to ``Null``.
    Not shared between *exekutir* and *kommandir*.
    Same keys/values used for the Ansible ``shell`` module.  Represents a command to execute
    on the *exekutir* during the ``exekutir_workspace_setup``
    role.  Its purpose is to allow additional files to be copied into the workspace, such as
    cloud or access credentials.  **N/B:** Ensure any copied
    files are also listed in the `cleanup_globs`_ so they don't persist `after *cleanup* <tcct>`_.

.. _extra_kommandir_setup:

``extra_kommandir_setup``
    Dictionary, defaults to ``Null``.
    Not shared between *exekutir* and *kommandir*.
    Same as `extra_exekutir_setup`_.  It is executed on the *kommandir*, after
    every time the ``kommandir_workspace_update`` role is applied.

.. _hostvarsfile:

``hostvarsfile``
    Not shared between any host.
    String, set to the current host's YAML variables file.
    Nominally ``{{invendory_dir}}/host_vars/{{inventory_hostname}}.yml``.

.. _job_name:

``job_name``
    String, defaults to the ``basename`` of `job_path`_.
    *Exekutir's* value overrides *kommandir's*.
    The value of this variable is primarily used to identify job-specific resources.
    For example, it is appended to the end of all *peon* names when they are created
    in an *OpenStack* cloud.

.. _job_path:

``job_path``
    String, defaults to ``jobs/quickstart``.
    *Exekutir's* value copied to *kommandir*.
    This is the absolute path containing all files, which should overwrite or support
    contents from the directory referenced by `kommandir_workspace`_.  This is the
    primary method to specialize a jobs activities.  This is where
    you will find the job's ``kommandir_vars.yml`` file.

.. _kommandir_groups:

``kommandir_groups``
    List, defaults to ``["nocloud"]``. Not shared between *exekutir* and *kommandir*.
    Any Ansible groups the *kommandir* should be made a member of on the *exekutir*.  The
    listed groups indicate which ``inventory/group_vars`` files should be used on that host.

.. _kommandir_workspace:

``kommandir_workspace``
    String, defaults to ``{{ workspace }}/kommandir_workspace`` on the *exekutir*.
    Only used in the ``exekutir/`` playbooks.  From the *exekutir's* perspective,
    it represents the local path which contains the authoritative copy of
    the *kommandir's* `workspace`_.  When the *kommandir* is a member of the ``nocloud``
    group no synchronization is done, so this will also be the *kommandir's* actual
    ``{{workspace}}``.

``kommandir_name_prefix``
    String, defaults to ``null``.
    Not shared between *exekutir* and *kommandir*.
    When non-null, this is used as a prefix when discovering or creating a *kommandir*.
    It's mainly used to control which *kommandir* is used for the job.  For example,
    CI jobs testing ADEPT changes, should never use a production *kommandir*.

``needs_reboot``
    Boolean, defaults to ``False``.
    Only used by *peons*.
    If any role sets this to ``True``, subsequent application of the ``rebooted`` role will
    result in that host being rebooted, and then confirmed accessible.  Afterwards,
    the value is always reset back to ``False``.

``no_log_synchronize``
    Boolean, defaults to ``True``
    *Exekutir's* value overrides *kommandi'r*.
    When ``False`` and ``adept_debug`` (above) is ``True`` or ``--verbose`` was used,
    the Ansible ``synchronize`` module will output the full contents of its operation.
    This can be a ***HUGE*** number (many hundreds) of output lines.
    Even when debugging, it's recommended to keep this ``True`` unless the details are
    really needed.

.. _public_peons:

``public_peons``
    Boolean, defaults to ``False``
    Only used by *peons*.
    When ``True``, the `cloud_provisioning_command`_ should
    make every effort to allow unrestricted network access to created *peons*.
    Otherwise, when ``False``, unrestricted access is optional, except by
    the *kommandir*.

.. _stonith:

``stonith``
    Boolean, defaults to ``False``
    Only used  by *kommandir* during the ``exekutir/roles/kommandir_destroyed`` role.
    When ``True`` during the *cleanup* context, it forces removal of the *kommandir*.
    This is used primarily during CI jobs for ADEPT itself,
    to ensure that a temporary *kommandir* is destroyed.

.. _uuid:

``uuid``
    DNS & Username compatible string, defaults to a random number.
    *Exekutir's* value overrides *kommandir's*.
    This is a critical value.  It must never change throughout the duration of
    all context transitions, and for the lifetime of any *kommandir*.  Its primary
    purpose is to prevent resource contention (hostnames, usernames, and directory names).
    However, for cloud-based *kommandir's*, it is also utilized to prevent `workspace`_
    location clashes.

.. _workspace:

``workspace``
    String, the path set by the ``$WORKSPACE`` environment variable by ``adept.py``.
    This is the place where all runtime state and results are stored.  See
    also `kommandir_workspace`_.
