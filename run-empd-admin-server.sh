#!/bin/bash
set -x
# start postgres server
echo "Starting pg server" > ~/starting_pg_server.lock
echo "Created $HOME/starting_pg_server.lock"
/bin/bash -c "
start_pg_server &&
createdb -U postgres EMPD2 &&
curl -fsSL https://raw.githubusercontent.com/EMPD2/EMPD-data/master/postgres/EMPD2.sql | psql EMPD2 -U postgres &&
rm ~/starting_pg_server.lock
" &

# clone latest version of the EMPD
git -C /opt/empd-data pull origin master &

# activate conda
. "/opt/conda/etc/profile.d/conda.sh"
conda activate empd-admin

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
