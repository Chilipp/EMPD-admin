#!/bin/bash
# Run the EMPD-admin from the local data repository in the docker image
#
# Usage:
#
#     docker run empd2/empd-admin empd-admin help

# activate conda
. "/opt/conda/etc/profile.d/conda.sh"
conda activate empd-admin

git config --global user.name "EMPD-admin"

empd-admin -d /opt/empd-data "$@"
