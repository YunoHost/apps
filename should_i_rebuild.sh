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
    python ./list_builder.py -g $1 apps.json

    # FIXME : this code should probably be moved to "apps.json" nowadays ...
    python ./update_translations.py official-build.json community-build.json

    for i in official community
    do
        if [ "$(git status -s| grep "M locales-$i/en.json")" ]
        then
            git add locales-$i/en.json
            git commit -m "[mod] update locales-$i/en.json with new translations"
            git pull
            git push
        fi
    done
fi
