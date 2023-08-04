
[ ! -e manifest.toml ] && exit 0

sed -i '/full_domain =/d' manifest.toml
