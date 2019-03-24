#!/bin/bash

# start postgres server
start_pg_server

# create and populate the EMPD2 database from the latest master branch
createdb -U postgres EMPD2
curl -fsSL https://raw.githubusercontent.com/EMPD2/EMPD-data/master/postgres/EMPD2.sql | psql EMPD2 -U postgres

# activate conda
conda -h > /dev/null || source /root/.bashrc

git config --global user.name "EMPD-admin"

# start the webapp
echo 'Starting EMPD-admin webapp...'
if [ -w /opt/conda ]; then
    python -m empd_admin.webapp
else
    cp -r /opt/empd-admin $HOME
    cd $HOME/empd-admin
    python -m empd_admin.webapp
fi
