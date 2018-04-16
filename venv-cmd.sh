#!/bin/bash

# This wrapper-script reduces the number of python-dependencies needed to execute a command
# and always executes from a fixed-version / verified environment. This means, no matter
# what happens on the host package-wise, the nested command should behave in a very predictable
# way (including, known bugs).  The last part is important, because bugs can be worked around
# easier than unpredictable code-changes.
#
# It only requires the following (or equivalent) be installed for all platforms (unless I missed one):
#
#    python3 python3-devel python34 python34-devel python2-virtualenv gcc
#    openssl-devel redhat-rpm-config libffi-devel python-devel python3-pycurl
#    python-pycurl python2-simplejson util-linux
#
# Example usage:
#
#   $ ./bin/venv-cmd ansible-playbook --version
#
# N/B: You may set $WORKSPACE and/or $ARTIFACTS to control where things are written

# All errors are fatal
set -e

echo
if [ "$#" -lt "1" ]
then
    echo "No command and command-line options specified."
    echo "usage: $0 <COMMAND> [OPTIONS...]"
    exit 3
fi

if [[ "${DEBUG:-false}" == "true" ]]
then
    set -x
else
    set +x
fi

# Don't leave __pycache__ directories everywhere
PYTHONDONTWRITEBYTECODE="true"
PYTHON3SUPPORT="${PYTHON3SUPPORT:-false}"  # Only required for CI/Unittesting
VENV_DIRNAME=".venv"
LOCKTIMEOUT_MINUTES="10"
SCRIPT_NAME=$(basename "$0")
SCRIPT_DIR=$(dirname `realpath "$0"`)
REPO_DIR=$(realpath "$SCRIPT_DIR")

export WORKSPACE="${WORKSPACE:-$REPO_DIR}"
export WORKSPACE=$(realpath $WORKSPACE)
export PIPCACHE="$WORKSPACE/.cache/pip"
MARKERFILE="$WORKSPACE/$VENV_DIRNAME/.complete"

export ARTIFACTS="${ARTIFACTS:-$WORKSPACE/artifacts}"
export ARTIFACTS=$(realpath "$ARTIFACTS")
mkdir -p "$ARTIFACTS"
export LOGFILEPATH="$ARTIFACTS/$SCRIPT_NAME.log"

REQUIREMENTS="$REPO_DIR/requirements.txt"
# Boot-strap requirements are very minimal
BSREQ="$(mktemp -p "" $(basename $0)_XXXX)"
cat << EOF > "$BSREQ"
pip==9.0.1 --hash=sha256:690b762c0a8460c303c089d5d0be034fb15a5ea2b75bdf565f40421f542fefb0
virtualenv==15.1.0 --hash=sha256:39d88b533b422825d644087a21e78c45cf5af0ef7a99a1fc9fbb7b481e5c85b0
EOF

# (Line-delineated)
CLEANUP_PATHS="$BSREQ
               $PIPCACHE
               $WORKSPACE/${VENV_DIRNAME}bootstrap
               $WORKSPACE/${VENV_DIRNAME}"

cd "$WORKSPACE"

cleanup() {
    RET2="$?"  # prior exit code
    set +x
    set -e
    echo "$CLEANUP_PATHS" |
    while read LINE
    do
        rm -rf "$LINE"
    done
    if [ "${RET2:-1}" -ne "0" ]
    then
        echo "Exiting: $RET2"
        exit $RET2
    fi
}

handle_log_and_cleanup() {
    RET="$?"  # prior exit code
    set +x
    set -e
    cleanup
    if [ "${RET:-2}" -ne "0" ]
    then
        echo "An error ($RET) occurred, displaying log contents:"
        cat "$LOGFILEPATH"
        exit ${RET:-3}
    fi
}
trap handle_log_and_cleanup EXIT

# All command failures from now on are fatal
echo "Bootstrapping trusted virtual environment, this may take a few minutes, depending on networking."
echo
echo "-----> Log: \"$LOGFILEPATH\")"
echo

(
  set -e
  if ! flock --nonblock 42
  then
      echo "Another $SCRIPT_NAME virtual environment creation process is running."
      echo "Waiting up to $LOCKTIMEOUT_MINUTES minutes for it to exit."
      echo
      if ! flock --timeout $[60 * LOCKTIMEOUT_MINUTES] 42
      then
          echo "Could not obtain lock on virtual environment creation"
          echo
          exit 9
      fi
  fi
  echo "Virtual environment creation lock acquired"
  echo
  set -ex
  (
    # When running more than once, make it fast by skipping the bootstrap
    if [ ! -d "./$VENV_DIRNAME" ] || [ ! -r "$MARKERFILE" ]
    then  # Don't allow previously broken cache to break fresh setup
        echo "Setting up a new virtual environment"
        rm -rf "$PIPCACHE"
        rm -rf "$VENV_DIRNAME"
        # N/B: local system's virtualenv binary - uncontrolled version fixed below
        virtualenv --python=python2 "./${VENV_DIRNAME}bootstrap"
        python3 -m venv "./${VENV_DIRNAME}bootstrap"
        # Set up paths to install/operate out of $WORKSPACE/${VENV_DIRNAME}bootstrap
        source "./${VENV_DIRNAME}bootstrap/bin/activate"
        # N/B: local system's pip binary - uncontrolled version fixed below
        # pip may not support --cache-dir, force it's location into $WORKSPACE the ugly-way
        OLD_HOME="$HOME"
        export HOME="$WORKSPACE"
        # Newer pip required to support hash-checking
        pip install --force-reinstall --upgrade pip==9.0.1
        # Undo --cache-dir workaround
        export HOME="$OLD_HOME"
        # Install fixed, trusted, hashed versions of pip and virtualenv
        ARGS="--cache-dir="$PIPCACHE" install --force-reinstall --require-hashes --isolated --requirement"
        pip $ARGS "$BSREQ"
        [ "$PYTHON3SUPPORT" == 'false' ] || \
            python3 -m pip $ARGS "$BSREQ"
        # Setup trusted virtualenv using hashed packages from $REQUIREMENTS
        [ "$PYTHON3SUPPORT" == 'false' ] || \
            "./${VENV_DIRNAME}bootstrap/bin/python3" -m venv "./$VENV_DIRNAME"
        "./${VENV_DIRNAME}bootstrap/bin/virtualenv" --python=python2 "./$VENV_DIRNAME"
    else
        echo "Using existing virtual environment"
    fi
    echo "$@" > "$MARKERFILE"  # $VENV_DIRNAME and $PIPCACHE are now trusted

    # Enter trusted virtualenv with trusted cache
    source "./$VENV_DIRNAME/bin/activate"
    # Install actual reqirements
    ARGS="--cache-dir="$PIPCACHE" install --require-hashes --isolated --requirement"
    pip $ARGS "$REQUIREMENTS"
    [ "$PYTHON3SUPPORT" == 'false' ] || \
        python3 -m pip $ARGS "$REQUIREMENTS"
  ) &>> "$LOGFILEPATH"
) 42>>"$LOGFILEPATH"

# Since setup is complete, preserve environment and cache on exit
CLEANUP_PATHS="$BSREQ
$WORKSPACE/${VENV_DIRNAME}bootstrap"
trap cleanup EXIT

source "./$VENV_DIRNAME/bin/activate"

if [[ -r "./requirements.yml" ]] && [[ ! -r "./galaxy_roles/.installed" ]]
then
    echo "Installing Ansible-Galaxy Roles from requirements.yml"
    mkdir -p ./galaxy_roles
    ansible-galaxy install --roles-path="./galaxy_roles" --role-file="./requirements.yml"
    touch "./galaxy_roles/.installed"
fi

echo "Executing $@"
echo
"$@"
deactivate  # just in case
