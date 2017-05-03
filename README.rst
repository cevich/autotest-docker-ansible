=====================================================
Autotest-Docker Enabled Product Testing (A.D.E.P.T.)
=====================================================

ADEPT includes a python program, a collection of ansible playbooks, and
related configurations.  Together, they help orchestrate a complete
run of Docker Autotest over one or more local or cloud-based systems.

.. The quickstart section begins next

Prerequisites
==============

*  Red Hat based host (RHEL_, CentOS_, Fedora_, etc), subscribed and fully updated.
*  Python 2.7
*  PyYAML 3.10
*  Ansible_ 2.1 or later (up to but excluding 2.3)
*  Ansible_ 2.2 is required if the Kommandir node will be local (i.e. "nocloud")
*  Root access **not** required

Openstack support:
-------------------

* redhat-rpm-config (rpm)
* gcc
* python-virtualenv or python2-virtualenv (EPEL rpm)
* `Openstack client config credentials`_

.. _Ansible: http://docs.ansible.com/index.html
.. _RHEL: http://www.redhat.com/rhel
.. _CentOS: http://www.centos.org
.. _Fedora: http://www.fedoraproject.org
.. _`Openstack client config credentials`: https://docs.openstack.org/developer/os-client-config/

Quickstart
===========

::

    # Optional: set $ANSIBLE_PRIVATE_KEY_FILE
    # if unset, a new temporary key will be generated in workspace
    $ export ANSIBLE_PRIVATE_KEY_FILE=$HOME/.ssh/id_rsa

    # Create a place for runtime details and results to be stored
    $ export WORKSPACE=$(mktemp -d --suffix=.workspace)

    # Run the ADEPT-three-step (keyboard finger-dance)
    $ ./adept.py setup $WORKSPACE exekutir.xn
    $ ./adept.py run $WORKSPACE exekutir.xn
    $ ./adept.py cleanup $WORKSPACE exekutir.xn

**Notes:**

#. To see select debugging output (select variable values and infos),
   append ``-e adept_debug=true`` onto any of the ``adept.py`` lines above.

#. Setting ``-e adept_debug=true`` will prevent roles in the cleanup context
   from removing any leftover files in the workspaces.

#. To see massive amounts of ugly details, append one or more ``--verbose``,
   options onto any of the ``adept.py`` lines above.

#. To run a different job, simply override the path on __each__ of the
   ``adept.py`` lines above.  e.g. ``./adept.py ... -e job_path=jobs/basic``

.. The current documentation section begins next

Latest Documentation
======================

For the latest, most up to date documentation please visit
http://autotest-docker-enabled-product-testing.readthedocs.io

The latest `Docker Autotest`_ documentation is located at:
http://docker-autotest.readthedocs.io

.. _Docker Autotest: https://github.com/autotest/autotest-docker
