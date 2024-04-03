#!/usr/bin/env bash

workdir=$(realpath $(dirname "$0"))
log=$workdir/app_list_auto_update.log

cd $workdir
date >> $log
git pull &>/dev/null
cat cron | sed "s@__BASEDIR__@$workdir@g" > /etc/cron.d/app_list

./tools/list_builder.py &>> $log || sendxmpppy "[listbuilder] Rebuilding the application list failed miserably"
