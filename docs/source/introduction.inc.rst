.. _introduction:

Introduction
=============

Both Autotest_ and `Docker Autotest`_ represent excellent and comprehensive testing
frameworks. However, they are lacking in modern system configuration and orchestration
capabilities. Especially, those required for Continuous Integration testing systems.

This project aims to bridge those gaps, supporting any available cloud provisioning,
or management system.  Along with a highly configurable, Ansible-based system
configuration, test execution, and artifact collection.  While not tightly
bound to `Docker Autotest`_, it is the default framework employed.

Finally, since entry-point capabilities often unknown and fixed, ADEPT has
very low initial dependency and resource requirements.  The included ``adept.py``
program, along with a simple YAML input file directives, guides the entire whole
operation.

.. _autotest: http://autotest.github.io/
.. _`docker autotest`: https://github.com/autotest/autotest-docker
