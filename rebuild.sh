#!/bin/bash

workdir=$(dirname "$0")
log=$workdir/app_list_auto_update.log

cd $workdir
date >> $log
git pull >/dev/null

./list_builder.py &>> $log || sendxmpppy "[listbuilder] Rebuilding the application list failed miserably"
