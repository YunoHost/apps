#!/usr/bin/env python3

import argparse
import os
import re


def cleanup():

    comment_blocks_to_cleanup = [
        r"#=+\s*\n# GENERIC START\S*\s*\n#=+\s*\n# IMPORT GENERIC HELPERS\n#=+\s*\n",
        r"#=+\s*\n# EXPERIMENTAL HELPERS\s*\n#=+\s*\n",
        r"#=+\s*\n# FUTURE OFFICIAL HELPERS\s*\n#=+\s*\n",
        r"#=+\s*\n# PERSONAL HELPERS\s*\n#=+\s*\n",
        r"#=+\s*\n# GENERIC FINALIZATION\s*\n",
        r"#=+\s*\n# GENERIC FINALISATION\s*\n",
        r"#=+\s*\n# STANDARD MODIFICATIONS\s*\n",
        r"#=+\s*\n# STANDARD UPGRADE STEPS\s*\n",
        r"#=+\s*\n# SPECIFIC UPGRADE\s*\n",
        r"#=+\s*\n# CHECK VERSION\s*\n#=+\s*\n",
        r"#=+\s*\n# DECLARE DATA AND CONF FILES TO BACKUP\s*\n#=+\s*\n",
    ]

    removememaybes = [
        "ynh_legacy_permissions_exists",
        "ynh_legacy_permissions_delete_all",
        "ynh_webpath_available",
        "ynh_webpath_register",
        "ynh_psql_test_if_first_run",
        "ynh_backup_before_upgrade",
        "ynh_restore_upgradebackup",
        "ynh_find_port",
        "ynh_port_available",
        "ynh_require_ram",
        "--ignore_swap",
        "--only_swap",
        "ynh_print_log",
        "ynh_print_OFF",
        "ynh_print_ON",
        "fpm_usage=low",
        "fpm_usage=\"low\"",
        "fpm_footprint=low",
        "fpm_footprint=\"low\"",
        "fpm_free_footprint=",
    ]

    replaces = [
        # Unecessary exec_warn_less
        (r"ynh_exec_warn_less ynh_secure_remove", "ynh_secure_remove"),
        (r"ynh_exec_warn_less ynh_systemd_action", "ynh_systemctl"),
        (r"ynh_exec_warn_less ynh_install_nodejs", "ynh_install_nodejs"),
        (r"ynh_exec_warn_less ynh_install_go", "ynh_install_go"),
        (r"ynh_exec_warn_less ynh_install_ruby", "ynh_install_ruby"),
        (r"ynh_exec_warn_less ynh_composer_exec", "ynh_composer_exec"),
        (r"ynh_exec_warn_less ynh_install_composer", "ynh_install_composer"),
        # Setting get/set
        (r" ?--app=? ?\"?\$app\"?", ""),
        # Misc
        (r"ynh_validate_ip4", "ynh_validate_ip --family=4"),
        (r"ynh_validate_ip4", "ynh_validate_ip --family=6"),
        (r"\$\(ynh_get_debian_release\)", "$YNH_DEBIAN_VERSION"),
        (r"ynh_read_manifest --manifest\S*", "ynh_read_manifest"),
        (r"--manifest_key", "--key"),
        (r"COMMON VARIABLES", "COMMON VARIABLES AND CUSTOM HELPERS"),
        (r"ynh_string_random ([0-9])", "ynh_string_random --length=\\1"),
        (r"ynh_backup_if_checksum_is_different --file=?", "ynh_backup_if_checksum_is_different "),
        (r"ynh_store_file_checksum --file=?", "ynh_store_file_checksum "),
        (r"ynh_delete_file_checksum --file=?", "ynh_delete_file_checksum "),
        # ynh_setup_source
        (r"--full_replace=1", "--full_replace"),
        (r"sources/patches", "patches"),
        (r"sources/extra_files/app", "sources"),
        (r"sources/extra_files", "sources"),
        # Logging
        (r"ynh_print_err", "ynh_print_warn"),
        (r"ynh_exec_quiet ?", ""),
        (r"ynh_exec_fully_quiet ?", ""),
        (r"ynh_exec_warn_less", "ynh_hide_warnings"),
        (r"--message=?", ""),
        (r"--time ", ""),
        (r"--last", ""),
        (r"--weight=?\S*", ""),
        # rm
        (r"ynh_secure_remove( --file=?)? ?", "ynh_safe_rm "),
        # Conf / templating
        (r"__NAME__", "__APP__"),
        (r"__NAMETOCHANGE__", "__APP__"),
        (r"ynh_render_template", "ynh_config_add --jinja"),
        (r"ynh_add_config", "ynh_config_add"),
        (r'--template="../conf/', '--template="'),
        # Upgrade stuff
        (r"ynh_compare_current_package_version.*lt.*version\s?=?\"?([0-9\.]+~ynh[0-9])\"?", "ynh_app_upgrading_from_version_before \\1"),
        (r"ynh_compare_current_package_version.*le.*version\s?=?\"?([0-9\.]+~ynh[0-9])\"?", "ynh_app_upgrading_from_version_before_or_equal_to \\1"),
        (r"upgrade_type=\S*", ""),
        ('\[\s+"?\$upgrade_type"?\s+==\s+"?UPGRADE_APP"? ]', "ynh_app_upstream_version_changed"),
        # Backup/store
        (r"ynh_restore\s*$", "ynh_restore_everything"),
            # -> Specific trick to remove the --not_mandatory here, but replace it with || true for the other occurences
        (r'ynh_restore_file --origin_path="\$data_dir" \S*', 'ynh_restore "$data_dir"'),
        (r"ynh_restore_file", "ynh_restore"),
        (r"--src_path=?", ""),
        (r"--origin_path=?", ""),
        (r"--is_big\S*", ""),
        (r"--not_mandatory", "|| true"),
        # Fail2ban
        (r"--max_retry=\S*", ""),
        (r"--ports\S*", ""),
        (r"ynh_add_fail2ban_config --use_template", "ynh_config_add_fail2ban"),
        (r"ynh_add_fail2ban_config", "ynh_config_add_fail2ban"),
        (r"ynh_remove_fail2ban_config", "ynh_config_remove_fail2ban"),
        # MySQL/Postgresql
        (r"ynh_mysql_dump_db \S*\$db_name\"?\s", "ynh_mysql_dump_db "),
        (r"ynh_psql_dump_db \S*\$db_name\"?\s", "ynh_psql_dump_db "),
        (r"ynh_mysql_connect_as [^<\\]*\s", "ynh_mysql_db_shell "),
        (r"ynh_psql_connect_as [^<\\]*\s", "ynh_psql_db_shell "),
        (r'ynh_mysql_execute_as_root --sql=?', 'ynh_mysql_db_shell <<< '),
        (r'ynh_psql_execute_as_root --sql=?', 'ynh_psql_db_shell <<< "'),
        (r'ynh_mysql_execute_as_root "', 'ynh_mysql_db_shell <<< "'),
        (r'ynh_psql_execute_as_root "', 'ynh_psql_db_shell <<< "'),
        (r"ynh_mysql_execute_as_root '", "ynh_mysql_db_shell <<< '"),
        (r"ynh_psql_execute_as_root '", "ynh_psql_db_shell <<< '"),
        (r"ynh_psql_execute_as_root --database=?", "ynh_psql_db_shell "),
        (r"ynh_mysql_execute_as_root --database=?", "ynh_psql_db_shell "),
        (r"--sql=", "<<< "),
        (r'ynh_mysql_execute_file_as_root --database=\"?(\S+)\"? --file=\"?(\S+)\"?', 'ynh_mysql_db_shell "\\1" < "\\2"'),
        (r'ynh_mysql_execute_file_as_root --file=\"?(\S+)\"? --database=\"?(\S+)\"?', 'ynh_mysql_db_shell "\\2" < "\\1"'),
        (r'ynh_psql_execute_file_as_root --database=\"?(\S+)\"? --file=\"?(\S+)\"?', 'ynh_psql_db_shell "\\1" < "\\2"'),
        (r'ynh_psql_execute_file_as_root --file=\"?(\S+)\"? --database=\"?(\S+)\"?', 'ynh_psql_db_shell "\\2" < "\\1"'),
        (r'sql_db_shell "?\$db_name"?', "sql_db_shell "),
        (r'--database="?\$db_name"?', ""),
        (r'--database="?\$app"?', ""),
        (r"ynh_mysql_setup_db", "# FIXME ynh_mysql_create_db"),
        (r"ynh_mysql_remove_db", "# FIXME ynh_mysql_drop_db && ynh_mysql_drop_user"),
        (r"ynh_psql_setup_db", "# FIXME ynh_psql_create_db"),
        (r"ynh_psql_remove_db", "# FIXME ynh_psql_drop_db && ynh_psql_drop_user"),
        # PHP / composer
        (r" ?--phpversion=\S*", ""),
        (r" ?--composerversion=\S*", ""),
        (r" ?--usage=\S*", ""),
        (r" ?--footprint=\S*", ""),
        (r"YNH_COMPOSER_VERSION=", "composer_version="),
        (r' --workdir="\$install_dir"', ""),
        (r'--workdir=\$install_dir ', ""),
        (r'--workdir', "# FIXME (replace with composer_workdir=... prior to calling this helper, default is $intall_dir) --workdir"),
        (r'phpversion', "php_version"),
        (r'PHPVERSION', "PHP_VERSION"),
        (r"ynh_add_fpm_config", "ynh_config_add_phpfpm"),
        (r"ynh_remove_fpm_config", "ynh_config_remove_phpfpm"),
        (r"ynh_install_composer", "ynh_composer_install\nynh_composer_exec install --no-dev "),
        (r'--install_args="?([^"]+)"?(\s|$)', "\\1\\2"),
        (r'--commands="([^"]+)"(\s|$)', "\\1\\2"),
        # Nodejs
        (r"NODEJS_VERSION=", "nodejs_version="),
        (r"ynh_install_nodejs \S*", "ynh_nodejs_install"),
        (r"ynh_install_nodejs", "ynh_nodejs_install"),
        (r"ynh_remove_nodejs", "ynh_nodejs_remove"),
        (r"ynh_use_nodejs", "# REMOVEME? ynh_use_nodejs"),
        (r'"?\$ynh_node_load_PATH"?', ""),
        (r'"?\$ynh_node_load_path"?', ""),
        (r'"?\$?ynh_npm"?', "npm"),
        (r'"?\$?ynh_node"?', "node"),
        (r'(export )?COREPACK_ENABLE_DOWNLOAD_PROMPT=0', ""),
        (r'env\s+npm', "npm"),
        (r'env\s+pnpm', "pnpm"),
        (r'env\s+yarn', "yarn"),
        (r'env\s+corepack', "corepack"),
        # Ruby
        (r"RUBY_VERSION=", "ruby_version="),
        (r"ynh_install_ruby \S*", "ynh_ruby_install"),
        (r"ynh_install_ruby", "ynh_ruby_install"),
        (r"ynh_remove_ruby", "ynh_ruby_remove"),
        (r"ynh_use_ruby", "# REMOVEME? ynh_use_ruby"),
        (r'"?\$ynh_ruby_load_PATH"?', ""),
        (r'"?\$ynh_ruby_load_path"?', ""),
        (r'"?\$?ynh_ruby"?', "ruby"),
        (r'"?\$?ynh_gem"?', "gem"),
        # Go
        (r"^\s*GO_VERSION=", "go_version="),
        (r"ynh_install_go \S*", "ynh_go_install"),
        (r"ynh_install_go", "ynh_go_install"),
        (r"ynh_remove_go", "ynh_go_remove"),
        (r"ynh_use_go", "# REMOVEME? ynh_use_go"),
        (r'"?\$?ynh_go"?', "go"),
        # Mongodb
        (r"YNH_MONGO_VERSION", "mongo_version"),
        (r"ynh_install_mongo \S*", "ynh_install_mongo"),
        # ynh_replace_string
        (r"ynh_replace_string", "ynh_replace"),
        (r"--match_string", "--match"),
        (r"--replace_string", "--replace"),
        (r"--target_file", "--file"),
        # Nginx
        (r"ynh_add_nginx_config", "ynh_config_add_nginx"),
        (r"ynh_remove_nginx_config", "ynh_config_remove_nginx"),
        (r"ynh_change_url_nginx_config", "ynh_config_change_url_nginx"),
        # Systemd
        (r'--log_path="/var/log/\$app/\$app.log"', ""),
        (r'--service="?\$app"?(\s|$)', "\\1"),
        (r"--service_name", "--service"),
        (r"--line_match", "--wait_until"),
        (r' --template="systemd.service"', ""),
        (r"ynh_add_systemd_config", "ynh_config_add_systemd"),
        (r"ynh_remove_systemd_config --service=?", "ynh_config_remove_systemd"),
        (r"ynh_remove_systemd_config", "ynh_config_remove_systemd"),
        (r"ynh_systemd_action", "ynh_systemctl"),
        # Logrotate
        (r"ynh_use_logrotate", "ynh_config_add_logrotate"),
        (r"ynh_remove_logrotate", "ynh_config_remove_logrotate"),
        (r"--specific_user\S*", ""),
        (r"--logfile=?", ""),
        (r" ?--non-?append", ""),
        # Apt
        (r"ynh_package_is_installed (--package=)?", "_ynh_apt_package_is_installed"),
        (r"ynh_package_version (--package=)?", "_ynh_apt_package_version"),
        (r"ynh_package_install", "_ynh_apt_install"),
        (r"ynh_install_extra_app_dependencies", "ynh_apt_install_dependencies_from_extra_repository"),
        (r"ynh_install_app_dependencies", "ynh_apt_install_dependencies"),
        (r"ynh_remove_app_dependencies", "ynh_apt_remove_dependencies"),
        (r"ynh_package_autopurge", "_ynh_apt autoremove --purge"),
        # Exec as / sudo
        (r'ynh_exec_as "?\$app"?( env)?', "ynh_exec_as_app"),
        (r'sudo -u "?\$app"?( env)?', "ynh_exec_as_app"),
        # Cringy messages?
        ("Modifying a config file...", "Updating configuration..."),
        ("Updating a configuration file...", "Updating configuration..."),
        ("Adding a configuration file...", "Adding $app's configuration..."),
        ("Restoring the systemd configuration...", "Restoring $app's systemd service..."),
        ("Configuring a systemd service...", "Configuring $app's systemd service..."),
        ("Stopping a systemd service...", "Stopping $app's systemd service..."),
        ("Starting a systemd service...", "Starting $app's systemd service..."),
        # Trailing spaces
        (r"\s+$", "\n"),
    ]

    conf_replaces = [
        (r"__NAME__", "__APP__"),
        (r"__NAMETOCHANGE__", "__APP__"),
        ("__YNH_NODE__", "node"),
        ("__YNH_NPM__", "npm"),
        ("__YNH_NODE_LOAD_PATH__", "PATH=__PATH_WITH_NODEJS__"),
        ("__YNH_RUBY_LOAD_PATH__", "PATH=__PATH_WITH_RUBY__"),
        ("__YNH_GO_LOAD_PATH__", "PATH=__PATH_WITH_GO__"),
        ("__YNH_RUBY__", "ruby"),
        ("__PHPVERSION__", "__PHP_VERSION__"),
    ]

    replaces = [(re.compile(pattern, flags=re.M), replace) for pattern, replace in replaces]
    comment_blocks_to_cleanup = [re.compile(pattern, flags=re.M) for pattern in comment_blocks_to_cleanup]

    for s in [
        "_common.sh",
        "install",
        "remove",
        "upgrade",
        "backup",
        "restore",
        "change_url",
        "config",
    ]:

        script = f"scripts/{s}"

        if not os.path.exists(script):
            continue

        content = open(script).read()

        if s == "remove":
            content = re.sub(r'(ynh_secure_remove .*/var/log/\$app.*)', r"#REMOVEME? (Apps should not remove their log dir during remove ... this should only happen if --purge is used, and be handled by the core...) \1", content)

        for pattern in comment_blocks_to_cleanup:
            content = pattern.sub("", content)

        for pattern, replace in replaces:
            content = pattern.sub(replace, content)

        for remove in removememaybes:
            content = content.replace(remove, r"#REMOVEME? " + remove)

        # Remove trailing spaces, for some reason we gotta have re.M flag ...
        #content = re.sub(r"\s+$", "\n", content, flags=re.M)

        open(script, "w").write(content)

    for pattern, replace in conf_replaces:
        os.system(f"sed 's@{pattern}@{replace}@g' -i $(find conf/ -type f)")

    git_cmds = [
        "git rm --quiet sources/extra_files/*/.gitignore 2>/dev/null",
        "git rm --quiet sources/patches/.gitignore 2>/dev/null",
        "git mv sources/extra_files/* sources/ 2>/dev/null",
        "git mv sources/app/* sources/ 2>/dev/null",
        "git mv sources/patches patches/ 2>/dev/null",
        "test -e conf/app.sh && git rm --quiet conf/app.src",
        "test -e check_process && git rm --quiet check_process",
        "test -e scripts/actions && git rm -rf --quiet scripts/actions",
        "test -e config_panel.json && git rm --quiet config_panel.json",
        "test -e config_panel.toml.example && git rm --quiet config_panel.toml.example",
        "git rm $(find ./ -name .DS_Store) 2>/dev/null",
        "grep -q '\*\~' .gitignore  2>/dev/null || echo '*~' >> .gitignore",
        "grep -q '\~.sw\[op\]' .gitignore || echo '~.sw[op]' >> .gitignore",
        "grep -q '\.DS_Store' .gitignore || echo '.DS_Store' >> .gitignore",
        "git add .gitignore",
    ]

    for cmd in git_cmds:
        os.system(cmd)

    # If there's a config panel but the only options are the stupid php usage/footprint stuff
    if os.path.exists("config_panel.toml") and os.system(r"grep -oE '^\s*\[\S+\.\S+\.\S+]' config_panel.toml | grep -qv php_fpm_config") != 0:
        os.system("git rm --quiet -f config_panel.toml")
        os.system("git rm --quiet -f scripts/config")

    # Add helpers_version = '2.1' after yunohost requirement in manifest
    os.system('sed -i \'/^yunohost =/a helpers_version = "2.1"\' manifest.toml')


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Attempt to automatically apply changes to use YunoHost helpers v2.1 on a v2 app"
    )
    parser.add_argument("app_path", help="Path to the app to convert")

    args = parser.parse_args()

    if not os.path.exists(args.app_path + "/manifest.toml"):
        raise Exception("There is no manifest.toml. Is this really an app directory ?")

    os.chdir(args.app_path)

    cleanup()
