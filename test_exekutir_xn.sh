#!/bin/bash

set -e

# When running manually, allow command-line passthrough to adept.py
[ -z "$@" ] || ADEPT_OPTIONAL="$@"

export WORKSPACE=$(mktemp -d --suffix=.adept.workspace)
trap 'rm -rf $WORKSPACE' EXIT

cat << EOF > $WORKSPACE/variables.yml
---
job_path: $PWD/jobs/travis_ci
uuid: something_i_made_up_for_travis_ci
cloud_type: nocloud
repo_rpms: []
enable_repos: []
disable_repos: []
install_rpms: []
git_cache_args: []
some_magic_variable_for_testing: value_for_magic_variable
EOF

# Setup a dummy-cache to prevent needing to clone repos from travis
mkdir -p $WORKSPACE/cache && date > $WORKSPACE/cache/junk.txt

./adept.py setup $WORKSPACE exekutir.xn $ADEPT_OPTIONAL && \
    ./adept.py run $WORKSPACE exekutir.xn $ADEPT_OPTIONAL && \
    ./adept.py cleanup $WORKSPACE exekutir.xn $ADEPT_OPTIONAL

echo "$(basename $0) Exit: $?"
echo "Workspace contents:"
ls -la $WORKSPACE
echo "Kommandir's workspace contents:"
ls -la $WORKSPACE/kommandir_workspace
echo "Variables.yml contents:"
cat $WORKSPACE/kommandir_workspace/variables.yml

for context in setup run cleanup
do
    for name in exekutir kommandir
    do
        echo "Checking $name exit files for $context context contains 0"
        EXIT_CODE=$(cat $WORKSPACE/${name}_${context}.exit)
        [ "$EXIT_CODE" -eq "0" ] || exit 1
    done

    echo "Checking contents of test_file_from_${context}.txt"
    grep -q "This is the travis_ci job's test play, running on kommandir for the $context context" $WORKSPACE/kommandir_workspace/test_file_from_${context}.txt
done

echo "All checks pass"
