=====================================================
Autotest-Docker Enabled Product Testing (A.D.E.P.T.)
=====================================================

ADEPT includes a small python program and a collection of Ansible playbooks, and
related configurations.  Together, they help orchestrate parallel
creation, configuration, use and cleanup of ephemeral virtual machines.

.. _the_beginning:

.. _prerequisites:

Prerequisites
==============

*  Red Hat based host (RHEL_, CentOS_, Fedora_, etc), subscribed and fully updated.
*  Python 2.7
*  PyYAML 3.10 or later
*  libselinux-python 2.0 or later
*  rsync 2.5 or later
*  Ansible_ 2.1 or later (EPEL)
*  Root access **not** required

Testing/Development
--------------------

*  Ansible_ 2.3 or later
*  python-unittest2 1.0 or later
*  python2-mock 1.8 or later
*  pylint 1.4 or later
*  python-virtualenv or python2-virtualenv (EPEL)
*  Optional (for building documentation), ``make``, ``python-sphinx``,
   and ``docutils`` or equivalent for your platform.

OpenStack support:
-------------------

*  redhat-rpm-config
*  gcc
*  python-virtualenv or python2-virtualenv (EPEL)
*  openssl-devel
*  `OpenStack client configuration credentials`_

.. _Ansible: http://docs.ansible.com/index.html
.. _RHEL: http://www.redhat.com/rhel
.. _CentOS: http://www.centos.org
.. _Fedora: http://www.fedoraproject.org
.. _`OpenStack client configuration credentials`: https://docs.OpenStack.org/developer/os-client-config/


Quickstart
===========

Ansible 2.3 or later is required, along with the items listed under prerequisites_.

This demonstration doesn't do anything extraordinarily useful. However, it does
demonstrate ADEPT's essential functions.  The tasks to be performed (the *job*)
exist as a sparse `standard Ansible directory layout <directory_layout>`_,
under ``jobs/quickstart``.  All files in the job directory, overwrite identically
named files under ``kommandir/`` (after a working copy is made).

::

    # Optional: set $ANSIBLE_PRIVATE_KEY_FILE
    # if unset, a new temporary key will be generated in workspace
    $ export ANSIBLE_PRIVATE_KEY_FILE="$HOME/.ssh/id_rsa"

    # Create a place for runtime details and results to be stored
    $ export WORKSPACE="$(mktemp -d --suffix=.workspace)"

    # Run the ADEPT-three-step (keyboard finger-dance)
    $ ./adept.py setup $WORKSPACE exekutir.xn
    $ ./adept.py run $WORKSPACE exekutir.xn
    $ ./adept.py cleanup $WORKSPACE exekutir.xn

    # Cleanup the workspace, when you're done looking at it.
    $ rm -rf $WORKSPACE

**Notes:**

#. To see select debugging output (select variable values and infos),
   append ``-e adept_debug=true`` onto any of the ``adept.py`` lines above.

#. Setting ``-e adept_debug=true`` will prevent roles in the cleanup context
   from removing any leftover files in the workspaces.

#. To see massive amounts of ugly details, append one or more ``--verbose``,
   options onto any of the ``adept.py`` lines above.

.. _latest_documentation:

Latest Documentation
======================

For the latest, most up to date documentation please visit
http://autotest-docker-enabled-product-testing.readthedocs.io/en/simplify/

The latest `Docker Autotest`_ documentation is located at:
http://docker-autotest.readthedocs.io

.. _Docker Autotest: https://github.com/autotest/autotest-docker
