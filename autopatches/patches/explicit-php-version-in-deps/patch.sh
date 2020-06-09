PHP_DEPS="php-bcmath php-cli php-curl php-dev php-gd php-gmp php-imap php-intl php-json php-ldap php-mbstring php-mysql php-soap php-sqlite3 php-tidy php-xml php-xmlrpc php-zip php-dom php-opcache php-xsl php-apcu php-geoip php-imagick php-memcached php-redis php-ssh2 php-common"

grep -q -nr "php-" scripts/* || exit 0

for DEP in $PHP_DEPS
do
    NEWDEP=$(echo $DEP | sed 's/php-/php7.0-/g')
    [ ! -e ./scripts/_common.sh ] || sed "/^\s*#/!s/$DEP/$NEWDEP/g" -i ./scripts/_common.sh
    [ ! -e ./scripts/install ]    || sed "/^\s*#/!s/$DEP/$NEWDEP/g" -i ./scripts/install
    [ ! -e ./scripts/upgrade ]    || sed "/^\s*#/!s/$DEP/$NEWDEP/g" -i ./scripts/upgrade
    [ ! -e ./scripts/restore ]    || sed "/^\s*#/!s/$DEP/$NEWDEP/g" -i ./scripts/restore
done
