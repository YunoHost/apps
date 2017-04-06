#!/bin/bash

install_hub() {
    wget https://github.com/github/hub/releases/download/v2.3.0-pre9/hub-linux-amd64-2.3.0-pre9.tgz
    tar xf hub-linux-amd64-2.3.0-pre9.tgz
    hub-linux-amd64-2.3.0-pre9/bin/hub pull-request
}

set -ex

if [ ! "$1" ]
then
    echo "I need a github <username>:<token> to run as first argument"
    exit 1
fi

before_pull_commit=$(git show HEAD | head -n 1)

git pull


if [ "$before_pull_commit" != "$(git show HEAD | head -n 1)" ]
then
    python ./list_builder.py -g $1 official.json
    python ./list_builder.py -g $1 community.json
    python ./list_builder.py -g $1 dev.json

    python ./update_translations.py official-build.json community-build.json dev-build.json

    if [ "$(git status -s| grep 'M locales/en.json')" ]
    then
        git add locales/en.json
        git commit -m "[mod] update en.json with new translations"
        git pull
        git push yunohost-bot master

        # uses hub/git-spindle from pypi
        # to install:
        #   $ virtualenv ve
        #   $ ve/bin/pip install "hub==2.0"

        if [ ! -e hub-linux-amd64-2.3.0-pre9/bin/hub ]
        then
            install_hub
        fi

        hub-linux-amd64-2.3.0-pre9/bin/hub pull-request -h master -m "Update locales/en.json"
    fi
fi
