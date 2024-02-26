#!/bin/bash

workdir=$(dirname "$0")
log=$workdir/app_sources_auto_update.log

cd $workdir
date >> $log
git pull &>/dev/null
cat cron | sed "s@__BASEDIR__@$workdir@g" > /etc/cron.d/app_list

./tools/app_caches.py -j40 &>> $log || sendxmpppy "[appsourcesautoupdate] Downloading the apps caches failed miserably"

python3 tools/autoupdate_app_sources/autoupdate_app_sources.py \
    --edit --commit --pr --paste -j1 \
&> $log || sendxmpppy "[appsourcesautoupdate] App sources auto-update failed miserably"
