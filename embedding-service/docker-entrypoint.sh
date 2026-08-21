#!/bin/sh
set -eu

# A named volume mounted at /data keeps ownership from the deployment where it
# was first created. Repair it before dropping privileges so upgrades also work
# with volumes that were originally created as root.
mkdir -p /data/model-cache /data/result-cache /home/app
chown -R app:app /data /home/app

exec gosu app "$@"
