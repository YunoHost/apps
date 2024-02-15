#!/bin/bash

workdir=$(dirname "$0")
log=$workdir/app_sources_auto_update.log

cd $workdir
date >> $log
git pull &>/dev/null
cat cron | sed "s@__BASEDIR__@$workdir@g" > /etc/cron.d/app_list

python3 tools/autoupdate_app_sources/autoupdate_app_sources.py \
    --edit --commit --pr --paste -j10 \
&> $log || sendxmpppy "[appsourcesautoupdate] App sources auto-update failed miserably"
