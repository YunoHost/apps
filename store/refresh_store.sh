#!/usr/bin/env bash

workdir=$(realpath "$(dirname "$0")")
log=$workdir/refresh_store.log

cd "$workdir"
date >> "$log"
git pull &>/dev/null
cat cron | sed "s@__BASEDIR__@$workdir@g" > /etc/cron.d/refresh_store

systemctl restart appstore.service 2>&1 | tee "$log"

if systemctl --quiet is-failed appstore.service; then
    sendxmpppy "[refresh_store] Restarting appstore.service failed miserably :scream:"
fi
