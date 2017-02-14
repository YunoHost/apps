#!/bin/bash

set -ex

if [ ! "$1" ]
then
    echo "I need a github <username>:<token> to run as first argument"
    exit 1
fi

before_official=$(sha256sum official.json)
before_community=$(sha256sum community.json)
before_dev=$(sha256sum dev.json)

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
