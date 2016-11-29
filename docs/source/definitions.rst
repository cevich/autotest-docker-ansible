Definitions
==============

``context``:
             The label given to the end-state upon completion of a transition.
             Analogous to a "phase", or collection of related steps. The context
             label (string) is assumed to pass unmodified, through all
             facilities (adept.py files, playbooks, scripts, etc.) and through
             all layers (original calling host, through slave, and into testing
             hosts). No facility or layer will alter the context label from
             the one originally passed into the first, lowest-level call of
             ``adept.py``.

``transition``:
                The collection of steps necessary to realize a context.
                Analogous to the act of performing all described tasks
                within a "phase" to reach some end-state of the entire
                macro-level system.  There is exactly one transition
                per context.

``setup``, ``run``, and ``cleanup``:
                                     The three context labels currently
                                     used in ADEPT.  Operationally,
                                     the ``run`` context is dependent (to some degree)
                                     on a successful ``setup`` transition.  However,
                                     the ``cleanup`` context transition must not
                                     depend on success or failure of either
                                     ``setup`` or ``run``.

``job``:
         A single, top-level invocation through all context transitions,
         concluding in a resource-clean, final end-state.  Independent
         of the existence of any results or useful data.  Assumed to not
         share any runtime data with any other job.  Except the name and
         IP address of the slave VM and perhaps the source of some
         configuration details.

``kommandir``:
               The name of the "slave" VM as referenced from within playbooks,
               adept files, and configurations.  Currently based on CentOS
               Atomic.  One kommandir VM supports use by multiple concurrent jobs.
               It is identified by a unique name - which is the means
               for concurrent jobs to obtain it's IP address.

``peon``:
          The lowest-level VM used for testing (running docker autotest).
          Assumed to only be controlled by a one-way connection by kommandir.
          Cannot and must not be able to access the kommandir or original
          execution host on it's own (i.e. top-down control only).

``slave image``:
                 Container image setup with all runtime dependencies but no data.
                 Lives on the ``kommandir``, re-built on demand. Forced to
                 have a limited lifetime to guarantee exercise of the building
                 mechanism.

``slave container``:
                     A throw-away docker container of the slave image.
                     Expected there will be possibly many of them starting,
                     running, and being removed on the ``kommandir``
                     host throughout the durations of multiple concurrent
                     jobs.  One container per transition, per job.  Guarantees
                     separation between concurrent jobs contexts.  Runtime data
                     is isolated from container image by volume mounts.
