#!/bin/bash

# start postgres server
start_pg_server

# create and populate the EMPD2 database from the latest master branch
createdb -U postgres EMPD2
curl -fsSL https://raw.githubusercontent.com/EMPD2/EMPD-data/master/postgres/EMPD2.sql | psql EMPD2 -U postgres

# activate conda
conda -h > /dev/null || source /root/.bashrc

# start the webapp
echo 'Starting EMPD-admin webapp...'
python -m empd_admin.webapp
