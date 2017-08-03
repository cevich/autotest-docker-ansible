
::

    $ ./adept.py cleanup $WORKSPACE exekutir.xn

    localhost ######################################
    Parameters:
        optional = ''
        xn = 'exekutir.xn'
        workspace = '/tmp/workspace'
        context = 'cleanup'

    ...cut...many...lines...

    $ ls $WORKSPACE

    ansible.cfg             exekutir_ansible.log           roles
    cache                   exekutir_setup_after_job.exit  run_after_job.yml
    callback_plugins        exekutir_vars.yml              run_before_job.yml
    cleanup_after_job.yml   inventory                      setup_after_job.yml
    cleanup_before_job.yml  kommandir_setup.exit           setup_before_job.yml
    clouds.yml              kommandir_workspace            ssh
    dockertest              results

