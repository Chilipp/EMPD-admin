#!/bin/bash

# activate conda
. "/opt/conda/etc/profile.d/conda.sh"
conda activate empd-admin

set -ex
# start postgres server
echo "Starting pg server" > ~/starting_pg_server.lock
echo "Created $HOME/starting_pg_server.lock"
bash -c "
start_pg_server &&
createdb -U postgres EMPD2 &&
curl -fsSL https://raw.githubusercontent.com/EMPD2/EMPD-data/master/postgres/EMPD2.sql | psql EMPD2 -U postgres > /dev/null &&
rm ~/starting_pg_server.lock
" &

# clone latest version of the EMPD in the herokuapp
bash -c '
if [[ $ONHEROKU ]]; then
    echo "Cloning master" > ~/cloning_master.lock &&
    git -C /opt/empd-data remote set-url origin https://github.com/EMPD2/EMPD-data.git &&
    git -C /opt/empd-data remote set-branches origin master &&
    git -C /opt/empd-data fetch origin &&
    git -C /opt/empd-data pull origin master &&
    rm ~/cloning_master.lock;
fi' &

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
