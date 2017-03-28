#!/bin/bash

cd $(dirname $0)

# When running manually, allow command-line passthrough to adept.py
ADEPT_OPTIONAL="$@"

export WORKSPACE=$(mktemp -d --suffix=.adept.workspace)
# Allow workspace inspection in debug mode
echo "$@" | grep -q 'adept_debug' || trap 'rm -rf $WORKSPACE' EXIT

cat << EOF > $WORKSPACE/exekutir_vars.yml
---
job_path: $PWD/jobs/ci
no_log_synchronize: False
uuid: something_i_made_up_for_ci
kommandir_groups:
    - nocloud
repo_rpms: []
enable_repos: []
disable_repos: []
install_rpms: []
git_cache_args: []
# Command-line option to setup (below) should override this:
some_magic_variable_for_testing: THE_WRONG_VALUE
EOF

ADEPT_OPTIONAL="$ADEPT_OPTIONAL -e some_magic_variable_for_testing='value_for_magic_variable'"

# Setup a dummy-cache to prevent needing to clone repos
mkdir -p $WORKSPACE/cache && date > $WORKSPACE/cache/junk.txt

./adept.py setup $WORKSPACE exekutir.xn $ADEPT_OPTIONAL && \
        ./adept.py run $WORKSPACE exekutir.xn $ADEPT_OPTIONAL

# Cleanup always runs
./adept.py cleanup $WORKSPACE exekutir.xn $ADEPT_OPTIONAL

# All/any non-zero exits are now fatal
set -e

echo "adept.py exit: $?"
echo
echo "Workspace contents:"
ls -la $WORKSPACE
echo
echo "Kommandir's workspace contents:"
ls -la $WORKSPACE/kommandir_workspace
echo
echo "results contents:"
ls -la $WORKSPACE/results/
echo
echo "kommandir_vars.yml contents:"
cat $WORKSPACE/kommandir_workspace/kommandir_vars.yml

echo
echo "Examining exit files"

echo "Checking kommandir discovery (before job.xn) cleanup exit file contains 0"
[ "$(cat ${WORKSPACE}/exekutir_cleanup_before_job.exit)" == "0" ] || exit 1

for context in setup run cleanup
do
    echo "Checking $context exit files"
    for name in exekutir_${context}_after_job kommandir_${context}
    do
        echo "Verifying ${name}.exit file contains 0"
        EXIT_CODE=$(cat $WORKSPACE/${name}.exit)
        [ "$EXIT_CODE" -eq "0" ] || exit 1
    done

    echo "Checking contents of test_file_from_${context}.txt"
    grep -q "This is the ci job's test play, running on kommandir for the $context context" $WORKSPACE/kommandir_workspace/results/test_file_from_${context}.txt
    grep -q "This is the ci job's test play, running on kommandir for the $context context" $WORKSPACE/results/test_file_from_${context}.txt
done

echo "All checks pass"
