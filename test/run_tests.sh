#!/bin/bash

# When running the tests, we need to ensure Python picks up the right environment.
# For this reason ,it's worth having a test wrapper.
cd "`dirname $0`"/..

# Most tests currently pass using the system Python3 but really you should test with
# the VEnv Python3. Let's activate this for you now, before we 'set -eu'.
if [ -n "$VIRTUAL_ENV" ] ; then
    echo "Virtual Env already active: $VIRTUAL_ENV"
elif [ -e _smrtino_venv ] ; then
    echo "Running: source ./_smrtino_venv/bin/activate"
    source ./_smrtino_venv/bin/activate
    if [ "$(which python3)" != "$(readlink -f _smrtino_venv)/bin/python3" ] ; then
        echo "FAILED - python3 is $(which python3) not $(readlink -f _smrtino_venv)/bin/python3"
        exit 1
    fi
else
    echo "No ./_smrtino_venv; will proceeed using the default $(which python3)"
fi

# This needs to come after the VEnv activation
set -euo pipefail

export RUN_SLOW_TESTS=${RUN_SLOW_TESTS:-0}
export RUN_NETWORK_TESTS=${RUN_NETWORK_TESTS:-1}

#Test in Py3 only
if [ "$*" == "" ] ; then
    python3 -munittest discover
else
    set -e
    python3 -munittest test.test_"$@"
fi


# Pyflakes is my favoured static analyser for regression testing because it
# just looks at one file at a time, thought it wouldn't hurt to cast
# pylint over the code too.
files_to_flake="*.py smrtino/*.py"

if [ "$*" == "" ] ; then
    if which pyflakes ; then
        for f in $files_to_flake ; do
            echo "### Running pyflakes $f"
            pyflakes "$f" || true
        done
    else
        echo "Unable to run pyflakes!"
    fi
fi
