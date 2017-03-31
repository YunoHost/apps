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

before_official=$(sha256sum official.json)
before_community=$(sha256sum community.json)
before_dev=$(sha256sum dev.json)
before_pull_commit=$(git show HEAD | head -n 1)

git pull

if [ "$before_official" != "$(sha256sum official.json)" ]
then
    python ./list_builder.py -g $1 official.json
fi

if [ "$before_community" != "$(sha256sum community.json)" ]
then
    python ./list_builder.py -g $1 community.json
fi

if [ "$before_dev" != "$(sha256sum dev.json)" ]
then
    python ./list_builder.py -g $1 dev.json
fi

if [ "$before_pull_commit" != "$(git show HEAD | head -n 1)" ]
then
    python ./update_translations.py
    if [ "$(git status -s| grep 'M locales/en.json')" ]
    then
        git add locales/en.json
        git commit -m "[mod] update en.json with new translations"
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
