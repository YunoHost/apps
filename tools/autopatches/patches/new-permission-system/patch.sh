
cd scripts/

if grep -q 'ynh_legacy_permissions' upgrade || grep -q 'ynh_permission_' install
then
    # App already using the new permission system - not patching anything
    exit 0
fi

if ! grep -q "protected_\|skipped_" install
then
    # App doesn't has any (un)protected / skipped setting ?
    # Probably not a webapp or permission ain't relevant for it ?
    exit 0
fi

CONFIGURE_PERMISSION_DURING_INSTALL='
# Make app public if necessary
if [ \"\$is_public\" -eq 1 ]
then
	ynh_permission_update --permission=\"main\" --add=\"visitors\"
fi
'

MIGRATE_LEGACY_PERMISSIONS='
#=================================================
# Migrate legacy permissions to new system
#=================================================
if ynh_legacy_permissions_exists
then
	ynh_legacy_permissions_delete_all

	ynh_app_setting_delete --app=\$app --key=is_public
fi'

for SCRIPT in "remove upgrade backup restore change_url"
do
    [[ -e $SCRIPT ]] || continue

    perl -p0e 's@.*ynh_app_setting_.*protected_.*@@g' -i $SCRIPT
    perl -p0e 's@.*ynh_app_setting_.*skipped_.*@@g' -i $SCRIPT
    perl -p0e 's@\s*if.*-z.*is_public.*(.|\n)*?fi\s@\n@g' -i $SCRIPT
    perl -p0e 's@\s*if.*is_public.*(-eq|=).*(.|\n)*?fi\s@\n@g' -i $SCRIPT
    perl -p0e 's@is_public=.*\n@@g' -i $SCRIPT
    perl -p0e 's@ynh_app_setting_.*is_public.*@@g' -i $SCRIPT
    perl -p0e 's@.*# Make app .*@@g' -i $SCRIPT
    perl -p0e 's@.*# Fix is_public as a boolean.*@@g' -i $SCRIPT
    perl -p0e 's@.*# If app is public.*@@g' -i $SCRIPT
    perl -p0e 's@.*# .*allow.*credentials.*anyway.*@@g' -i $SCRIPT
    perl -p0e 's@.*ynh_script_progression.*SSOwat.*@@g' -i $SCRIPT
    perl -p0e 's@#=*\s#.*SETUP SSOWAT.*\s#=*\s@@g' -i $SCRIPT
done


perl -p0e 's@.*domain_regex.*@@g' -i install
perl -p0e 's@.*# If app is public.*@@g' -i install
perl -p0e 's@.*# Make app .*@@g' -i install
perl -p0e 's@.*# .*allow.*credentials.*anyway.*@@g' -i install
perl -p0e "s@if.*is_public.*(-eq|=)(.|\n){0,100}setting(.|\n)*?fi\n@$CONFIGURE_PERMISSION_DURING_INSTALL@g" -i install
perl -p0e 's@.*ynh_app_setting_.*is_public.*\s@@g' -i install
perl -p0e 's@.*ynh_app_setting_.*protected_.*@@g' -i install
perl -p0e 's@.*ynh_app_setting_.*skipped_.*@@g' -i install

grep -q 'is_public=' install || perl -p0e 's@(.*Configuring SSOwat.*)@\1\nynh_permission_update --permission=\"main\" --add=\"visitors\"@g' -i install

perl -p0e "s@ynh_abort_if_errors@ynh_abort_if_errors\n$MIGRATE_LEGACY_PERMISSIONS@g" -i upgrade
