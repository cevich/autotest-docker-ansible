=====================================================
Autotest-Docker Enabled Product Testing (A.D.E.P.T.)
=====================================================

ADEPT includes a python program, a collection of ansible playbooks, and
related configurations.  Together, they help orchestrate a complete
run of Docker Autotest over one or more local or cloud-based systems.

.. The quickstart section begins next

Prerequisites
==============

*  Red Hat based host (RHEL_, Atomic_, CentOS_, Fedora_, etc), subscribed and fully updated.
*  Python 2.7
*  PyYAML 3.10
*  Ansible_ 2.1 or later
*  Root access **not** required

.. _Ansible: http://docs.ansible.com/index.html
.. _RHEL: http://www.redhat.com/rhel
.. _Atomic: http://www.redhat.com/en/resources/red-hat-enterprise-linux-atomic-host
.. _CentOS: http://www.centos.org
.. _Fedora: http://www.fedoraproject.org

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

**Note:** To see select debugging output (variable values, loop
items, etc), here and there, append ``-e adept_debug=true`` onto
any of the three ``adept.py`` lines above.  This will show
only the details we thought important enough to include.  Instead
(or in addition) you may also add one or more ``-v`` options,
to place Ansible itself into verbose mode.  Un/fortunately,
this means you'll see details about ***ALL*** tasks, useful or not.

.. The current documentation section begins next

Latest Documentation
======================

For the latest, most up to date documentation please visit
http://autotest-docker-enabled-product-testing.readthedocs.io

The latest `Docker Autotest`_ documentation is located at:
http://docker-autotest.readthedocs.io

.. _Docker Autotest: https://github.com/autotest/autotest-docker
