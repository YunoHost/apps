#!/bin/bash

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
        git push
    fi
fi
