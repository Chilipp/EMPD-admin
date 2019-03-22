#!/bin/bash
# Test script for the EMPD-admin in the docker container
#
# This script is accessible as /run_tests.sh in the EMPD-admin container and
# can be run with
#
#     docker run empd2/empd-admin test-empd-admin
start_pg_server
/opt/test-env/bin/pip install --user gitpython PyGithub xlrd openpyxl
cd /opt/empd-admin
/opt/test-env/bin/py.test -v
