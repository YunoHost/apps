#!/usr/bin/env bash

sed -E "/(ynh_secure_remove|ynh_safe_rm|rm).*(\/var\/log\/)/d" --i scripts/remove

git add scripts/remove
