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

        * Complete kommandir VM setup, install packages, setup storage, etc.

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
          provision and install all peon VMs, deploying cache contents
          to them, and prepare them for testing.

        * For remote kommandir's, rsync workspace back to exekutir's
          copy.

    * Exekutir releases shared lock
