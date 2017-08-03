
::

    $ cat << EOF > $WORKSPACE/clouds.yml
    ---
    clouds:
        default:
            auth_type: thepassword
            auth:
                auth_url: http://example.com/v2.0
                password: foobar
                tenant_name: baz
                username: snafu
            regions:
                - Oz
            verify: False

