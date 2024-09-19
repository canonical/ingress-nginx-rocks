#!/bin/bash

set -eux -o pipefail

# Required to prevent Pebble from considering the service to have
# exited too quickly to be worth restarting or respecting the
# "on-failure: shutdown" directive and thus hanging indefinitely:
# https://github.com/canonical/pebble/issues/240#issuecomment-1599722443
sleep 1.1

# NOTE(aznashwan): the controller image includes a
# number of dynamic libs which must be indexed:
ldconfig

ARGS="$@"
if [ $# -eq 0 ]; then
    # https://github.com/kubernetes/ingress-nginx/blob/controller-v1.10.1/rootfs/Dockerfile#L87
    ARGS="/nginx-ingress-controller"
fi

# https://github.com/kubernetes/ingress-nginx/blob/controller-v1.10.1/rootfs/Dockerfile#L86
exec /usr/bin/dumb-init -- $ARGS

