#!/bin/bash

set -e

# activate conda
. "/opt/conda/etc/profile.d/conda.sh"
conda activate empd-admin

git config --global user.name "EMPD-admin"

start_pg_server > /dev/null
createdb -U postgres EMPD2
psql EMPD2 -U postgres -f /opt/empd-data/postgres/EMPD2.sql > /dev/null

bash /opt/empd-admin/docs/apigen.sh

sphinx-build /opt/empd-admin/docs "$@"
