
cd scripts/

if [ ! -e change_url ] || grep -q 'ynh_abort_if_errors' change_url
then
    # The app doesn't has any change url script or already has ynh_abort_if_error
    exit 0
fi

sed 's@\(source /usr/share/yunohost/helpers\)@\1\nynh_abort_if_errors@g' -i change_url
