#!/bin/bash
# Test script for the EMPD-admin in the docker container
#
# This script is accessible as /run_tests.sh in the EMPD-admin container and
# can be run with
#
#     docker run empd2/empd-admin test-empd-admin
start_pg_server
git config --global user.name "EMPD-admin"
/opt/test-env/bin/pip install --user gitpython PyGithub xlrd openpyxl
if [ -w /opt/empd-admin ]; then
    cd /opt/empd-admin
    /opt/test-env/bin/py.test $@
else
    cp -r /opt/empd-admin $HOME
    cd $HOME/empd-admin
    /opt/test-env/bin/py.test $@
fi
