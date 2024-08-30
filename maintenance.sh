#!/usr/bin/env bash

workdir=$(realpath $(dirname "$0"))
cd $workdir

function update_venv()
{
    if [ -d "venv" ]; then
        venv/bin/pip install -r requirements.txt
    fi
}

function git_pull_and_update_cron_and_restart_services_if_needed()
{
    git pull &>/dev/null

    # Cron
    cat cron | sed "s@__BASEDIR__@$workdir@g" > /etc/cron.d/app_list

    # App store
    chown -R appstore store
    pushd store >/dev/null
    modified_after_service_start="$(find *.py translations/ templates/ assets/ -newermt "$(systemctl show --property=ActiveEnterTimestamp appstore | cut -d= -f2 | cut -d' ' -f2-3)")"
    if [ -n "$modified_after_service_start" ]
    then
        update_venv

        pushd assets >/dev/null
            ./tailwindcss-linux-x64 --input tailwind-local.css --output tailwind.css --minify
        popd >/dev/null
        systemctl restart appstore
        sleep 3
    fi
    popd >/dev/null

    systemctl --quiet is-active appstore || sendxmpppy "[appstore] Uhoh, failed to (re)start the appstore service?"

    # App generator
    chown -R appgenerator tools/app_generator
    pushd tools/app_generator >/dev/null
    modified_after_service_start="$(find *.py translations/ templates/ static/ -newermt "$(systemctl show --property=ActiveEnterTimestamp appgenerator | cut -d= -f2 | cut -d' ' -f2-3)")"
    if [ -n "$modified_after_service_start" ]
    then
        update_venv
        pushd assets >/dev/null
            ./tailwindcss-linux-x64 --input tailwind-local.css --output tailwind.css --minify
        popd >/dev/null
        systemctl restart appgenerator
        sleep 3
    fi
    popd >/dev/null

    systemctl --quiet is-active appgenerator || sendxmpppy "[appgenerator] Uhoh, failed to (re)start the appgenerator service?"

    # Autoreadme
    pushd tools/readme_generator >/dev/null
    modified_after_service_start="$(find *.py translations/ templates/ -newermt "$(systemctl show --property=ActiveEnterTimestamp webhooks | cut -d= -f2 | cut -d' ' -f2-3)")"
    if [ -n "$modified_after_service_start" ]
    then
        update_venv
        systemctl restart webhooks
        sleep 3
    fi
    popd >/dev/null

    # Autoreadme
    pushd tools/webhooks >/dev/null
    modified_after_service_start="$(find *.py -newermt "$(systemctl show --property=ActiveEnterTimestamp webhooks | cut -d= -f2 | cut -d' ' -f2-3)")"
    if [ -n "$modified_after_service_start" ]
    then
        update_venv
        systemctl restart webhooks
        sleep 3
    fi
    popd >/dev/null

    pushd tools/autoupdate_app_sources >/dev/null
    update_venv
    popd >/dev/null

    systemctl --quiet is-active webhooks || sendxmpppy "[autoreadme] Uhoh, failed to (re)start the autoreadme service?"
}

function rebuild_catalog()
{
    log=$workdir/app_list_auto_update.log
    date >> $log
    git_pull_and_update_cron_and_restart_services_if_needed
    ./tools/list_builder.py &>> $log || sendxmpppy "[listbuilder] Rebuilding the application list failed miserably"
}

function autoupdate_app_sources()
{
    log=$workdir/app_sources_auto_update.log
    date >> $log
    git_pull_and_update_cron_and_restart_services_if_needed
    tools/autoupdate_app_sources/venv/bin/python3 tools/autoupdate_app_sources/autoupdate_app_sources.py \
        --latest-commit-weekly --edit --commit --pr --paste -j1 \
    &> $log || sendxmpppy "[appsourcesautoupdate] App sources auto-update failed miserably"
}

function update_app_levels()
{
    pushd tools/update_app_levels >/dev/null
        python3 update_app_levels.py
    popd >/dev/null
}

function fetch_main_dashboard()
{
    pushd store >/dev/null
        venv/bin/python3 fetch_main_dashboard.py 2>&1 | grep -v 'Following Github server redirection'
    popd >/dev/null
}


function fetch_level_history()
{
    pushd store >/dev/null
        venv/bin/python3 fetch_level_history.py
    popd >/dev/null
}

$1
