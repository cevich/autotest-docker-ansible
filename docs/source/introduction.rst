Introduction
=============

Both Autotest_ and `Docker Autotest`_ represent excellent and comprehensive testing
frameworks. However, they are lacking in modern system configuration and orchestration
capabilities. Especially, those required for Continuous Integration testing systems.

This project aims to fill in that gap, from the provisioning of test systems, to
test execution, result collection and cleanup.  It will manage and configure all
the target systems up to and through execution of  `Docker Autotest`_.  All
Red Hat based flavors are supported due to Autotest_'s low dependency requirements.

The included ``adept.py`` program, along with a file containing a simple set of
YAML directives, guides the whole operation.  It's primary purpose is to act as
the single entry-point, and to coordinate state-transitions between playbooks for:

*  Setup - Creates VMs, setup services, deploy configurations.
*  Run - When setup was successful, execute all necessary testing and
   result collection steps.
*  Cleanup - Unconditionally, attempt to clean up and restore
   any allocated resources back to their original state.

All this work is performed by first bootstrapping into a controlled environment.
Referred to as the "kommandir" (because it sounds much more important than
"slave").  Here, specific, additional dependencies are configured, and utilized
to perform all remaining operations.

Finally, in addition to tearing down / cleaning up testing resources,
all the runtime details and results are synchronized back to the initial
system - the "exekutir" (again, hammer and chisel spelling to convey importance)

.. _autotest: http://autotest.github.io/
.. _`docker autotest`: https://github.com/autotest/autotest-docker
