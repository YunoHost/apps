#!/usr/bin/env bash

MANIFEST_SCHEMA_LINE='#:schema https://raw.githubusercontent.com/YunoHost/apps/master/schemas/manifest.v2.schema.json'
TESTS_SCHEMA_LINE='#:schema https://raw.githubusercontent.com/YunoHost/apps/master/schemas/tests.v1.schema.json'
CONFIGPANEL_SCHEMA_LINE='#:schema https://github.com/YunoHost/apps/raw/master/schemas/config_panel.v1.schema.json'


if [ -f "manifest.toml" ]; then
    if ! grep "#:schema" "manifest.toml" >/dev/null; then
        sed -i "1 s|^|$MANIFEST_SCHEMA_LINE\n|" manifest.toml
    fi
fi

if [ -f "tests.toml" ]; then
    if ! grep "#:schema" "tests.toml" >/dev/null; then
        sed -i "1 s|^|$TESTS_SCHEMA_LINE\n|" tests.toml
    fi
fi

if [ -f "config_panel.toml" ]; then
    if ! grep "#:schema" "config_panel.toml" >/dev/null; then
        sed -i "1 s|^|$CONFIGPANEL_SCHEMA_LINE\n|" tests.toml
    fi
fi

git add manifest.toml tests.toml
