#!/usr/bin/env bash

sed -E "/# remove logs/d" -i scripts/remove
sed -E "/(ynh_secure_remove|ynh_safe_rm|rm).*(\/var\/log\/)/d" -i scripts/remove
