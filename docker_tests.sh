#!/bin/bash
# Test script for the EMPD-admin in the docker container
#
# This script is accessible as /run_tests.sh in the EMPD-admin container and
# can be run with
#
#     docker run empd2/empd-admin test-empd-admin
start_pg_server

# activate conda
. "/opt/conda/etc/profile.d/conda.sh"
conda activate empd-admin

git config --global user.name "EMPD-admin"

if [ -w /opt/empd-admin ]; then
    cd /opt/empd-admin
    py.test $@
else
    cp -r /opt/empd-admin $HOME
    cd $HOME/empd-admin
    py.test $@
fi
