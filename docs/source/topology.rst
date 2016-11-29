Topology
==========

::

    | starting | queen bee | worker bees
       host

    exekutir --> kommandir --> peon
                           \
                            -> peon
                           \
                            -> peon

some notes:

* There may be zero - two clouds involved
    * ``exekutir/inventory/host_vars/exekutir.yml`` file's
      ``cloud_type`` determines the cloud for the kommandir.
    * ``exekutir/inventory/host_vars/kommandir.yml`` file's
      ``cloud_type`` determines the cloud for the peons.
    * Any ``cloud_type`` may be ``nocloud``
