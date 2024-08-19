#!/bin/sh

set -eux -o pipefail

# NOTE(aznashwan): the kube-webhook-certgen binary executes extremely
# fast (<1s) which makes Pebble consider it failed and not exiting
# properly after it runs, even if 'on-success: shutdown' is specified,
# so we must create this entrypoint script which sleeps before executing
# the actual entrypoint.
sleep 1.1

/kube-webhook-certgen $@
