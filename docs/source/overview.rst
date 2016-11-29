Operational Overview
=====================

FIXME: rough-draft

* The 'setup' context transition

    * Fundimental setup of exekutir's ssh keys, and copying ``exekutir`` dir.
      into ``$WORKSPACE``.  (``exekutir.xn``)

    * Intermediate exekutir setup, check ansible version, setup
      separate kommandir workspace source directory. (``setup_before_job.yml``)

    * Exekutir acquires exclusive lock 

        * Create or discover the kommandir VM by running a script.  YAML
          output from script updates kommandir's host_vars in inventory.

        * Wait for Kommandir to ping, and test ability to run ``sleep 0.1``.

        * Complete kommandir VM setup (if needed), install packages, 
          setup storage, etc.

    * Exekutir releases exclusive lock (maintaining shared lock)

        * Exekutir acquires shared lock 

        * Create user on kommandir named ``$UUID``, home dir is workspace.
          (or just keep using the local kommandir_workspace sub-directory
          if ``nocloud`` kommandir).

        * Recursively copy contents of ``job_path`` into kommandir's workspace.

        * Fill kommandir workspace cache with bits common across all
          (eventual) peons- autotest, docker autotest, etc.

        * For remote kommandir's, rsync workspace back to exekutir's
          copy (in case the next step fails).

        * Remotely run ``job.xn`` on kommandir.  Presumed this will
          provision and install all peon VMs (in parallel), deploying
          cache contents to them, and prepare them for testing. (exekutir.xn)

        * For remote kommandir's, rsync workspace back to exekutir's
          copy. (``setup_after_job.yml``)

    * Exekutir releases shared lock (``setup_after_job.yml``)


* The 'run' context transition

    * Exekutir acquires exclusive lock (``run_before_job.yml``)

        * Create or discover the kommandir VM by running a script.  YAML
          output from script updates kommandir's variables. 

        * Wait for Kommandir to ping, and test ability to run ``sleep 0.1``.

        * Complete kommandir VM setup (if needed), install packages, 
          setup storage, etc.

    * Exekutir releases exclusive lock (maintaining shared lock)

        * Exekutir acquires shared lock 

        * For remote kommandir's, rsync exekutir's
          copy of kommandir's workspace to kommandir.

        * Remotely run ``job.xn`` on kommandir.  Presumed this will
          execute testing on all peons in parallel, then package
          up all result files in kommandir's workspace.
          (``exekutir.xn`` -> ``job.xn``)

        * For remote kommandir's, rsync workspace back to exekutir's
          copy. (``run_after_job.yml``)

    * Exekutir releases shared lock

* The 'cleanup' context transition.  This always runs, whether or
   not setup or run happened or completed successfully.  Must be
   very tolerant of missing files and unexpected state.

    * Exekutir acquires exclusive lock (``cleanup_before_job.yml``)

        * Create or discover the kommandir VM by running a script.  YAML
          output from script updates kommandir's variables.

        * Wait for Kommandir to ping, and test ability to run ``sleep 0.1``.

        * Complete kommandir VM setup (if needed), install packages, 
          setup storage, etc.

    * Exekutir releases exclusive lock (maintaining shared lock)

        * Exekutir acquires shared lock 

        * For remote kommandir's, rsync exekutir's
          copy of kommandir's workspace to kommandir.  Failure
          blocks next step. 

        * Remotely run ``job.xn`` on kommandir.  Presumed this will
          destroy all peons and release any other resources
          (extra storage volumes, networking, etc.).  Failure
          does NOT block next step. (exekutir.xn -> job.xn)

        * For remote kommandir's, rsync workspace back to exekutir's
          copy.  (cleanup_after_job.yml)

    * Exekutir releases shared lock

    * For remote kommandir's only.  

        * Exekutir acquires exclusive lock (wait for other jobs to finish).

        * Check remote kommandir's install time.

        * If install time > 3 days (or something reasonable)
          destroy kommandir VM.  Release all resources.  Forcing
          new kommandir (every once in a while) reveals kommandir
          provisioning and package update bugs, prevents unbounded
          disk filling.

    * Exekutir releases exclusive lock

    * Exekutir prunes it's copy of Kommandir's workspace, then it's own.
      Removes cache, symlinks, copy of exekutir roles, exekutir playbooks,
      and exekutir ``variables.yml`` (preserving kommandir's copy).
