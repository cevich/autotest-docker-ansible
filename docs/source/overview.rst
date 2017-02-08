Operational Overview
=====================

FIXME: rough-draft

* Fundimental setup of exekutir's ssh keys, and copying __exekutir__ dir.
  into $WORKSPACE.

* The 'setup' context transition

    * Intermediate exekutir setup, check ansible version, setup
      separate kommandir workspace source directory.

    * Exekutir acquires exclusive lock

        * Create or discover the kommandir VM by running a script.  YAML
          output from script updates kommandir's variables.

        * Wait for Kommandir to ping, and test ability to run "sleep 0.1".

        * Complete kommandir VM setup (if needed), install packages, 
          setup storage, etc.

        * Exekutir acquires shared lock 

    * Exekutir releases exclusive lock (maintaining shared lock)

        * Create user on kommandir named $UUID, home dir is workspace.
          (or just keep using the local kommandir_workspace sub-directory
          if "nocloud" kommandir).

        * Recursively copy contents of job_path into kommandir's workspace.

        * Fill kommandir workspace cache with bits common across all
          (eventual) peons- autotest, docker autotest, etc.

        * For remote kommandir's, rsync workspace back to exekutir's
          copy (in case the next step fails).

        * Remotely run job.xn on kommandir.  Presumed this will
          provision and install all peon VMs (in parallel), deploying
          cache contents to them, and prepare them for testing.

        * For remote kommandir's, rsync workspace back to exekutir's
          copy.

    * Exekutir releases shared lock


* The 'run' context transition

    * Exekutir acquires exclusive lock

        * Create or discover the kommandir VM by running a script.  YAML
          output from script updates kommandir's variables.

        * Wait for Kommandir to ping, and test ability to run "sleep 0.1".

        * Complete kommandir VM setup (if needed), install packages, 
          setup storage, etc.

        * Exekutir acquires shared lock 

    * Exekutir releases exclusive lock (maintaining shared lock)

        * For remote kommandir's, destructive rsync exekutir's
          copy of kommandir's workspace to kommandir.

        * Remotely run job.xn on kommandir.  Presumed this will
          execute testing on all peons in parallel, then package
          up all result files in kommandir's workspace.

        * For remote kommandir's, rsync workspace back to exekutir's
          copy.

    * Exekutir releases shared lock

* The 'cleanup' context transition.  This always runs, whether or
   not setup or run happened or completed successfully.  Must be
   very tolerant of missing files and unexpected state.

    * Exekutir acquires exclusive lock

        * Create or discover the kommandir VM by running a script.  YAML
          output from script updates kommandir's variables.

        * Wait for Kommandir to ping, and test ability to run "sleep 0.1".

        * Complete kommandir VM setup (if needed), install packages, 
          setup storage, etc.

        * Exekutir acquires shared lock 

    * Exekutir releases exclusive lock (maintaining shared lock)

        * For remote kommandir's, destructive rsync exekutir's
          copy of kommandir's workspace to kommandir.  Failure
          blocks next step.

        * Remotely run job.xn on kommandir.  Presumed this will
          destroy all peons and release any other resources
          (extra storage volumes, networking, etc.).  Failure
          does NOT block next step.

        * For remote kommandir's, rsync workspace back to exekutir's
          copy.  Failure possible, but unlikely

    * Exekutir releases shared lock

    * For remote kommandir's only.  Exekutir acquires exclusive
      lock (wait for other jobs to finish).

        * Check remote kommandir's install time.

        * If install time > 3 days (or something reasonable)
          destroy kommandir VM.  Release all resources.  Forcing
          new kommandir (every once in a while) reveals kommandir
          provisioning and package update bugs, prevents unbounded
          disk filling.

    * Exekutir releases exclusive lock
