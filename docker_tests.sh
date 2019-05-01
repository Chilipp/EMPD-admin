#!/bin/bash
# Test script for the EMPD-admin in the docker container
#
# This script is accessible as /run_tests.sh in the EMPD-admin container and
# can be run with
#
#     docker run empd2/empd-admin test-empd-admin

# activate conda
. "/opt/conda/etc/profile.d/conda.sh"
conda activate empd-admin

set -xe

start_pg_server


if [[ $ONHEROKU ]]; then
    git -C /opt/empd-data remote set-url origin https://github.com/EMPD2/EMPD-data.git &&
    git -C /opt/empd-data remote set-branches origin master &&
    git -C /opt/empd-data fetch origin &&
    git -C /opt/empd-data pull origin master;
fi

git config --global user.name "EMPD-admin"

if [ -w /opt/empd-admin ]; then
    cd /opt/empd-admin
    py.test $@
else
    cp -r /opt/empd-admin $HOME
    cd $HOME/empd-admin
    py.test $@
fi
