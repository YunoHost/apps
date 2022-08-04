import argparse
import os
import re
import json
import subprocess


def check_output(cmd):
    return (
        subprocess.check_output(cmd, shell=True)
        .decode("utf-8")
        .strip()
    )


def _convert_v1_manifest_to_v2(app_path):

    manifest = json.load(open(app_path + "/manifest.json"))

    if "upstream" not in manifest:
        manifest["upstream"] = {}

    if "license" in manifest and "license" not in manifest["upstream"]:
        manifest["upstream"]["license"] = manifest["license"]

    if "url" in manifest and "website" not in manifest["upstream"]:
        manifest["upstream"]["website"] = manifest["url"]

    manifest["integration"] = {
        "yunohost": manifest.get("requirements", {}).get("yunohost"),
        "architectures": "all",
        "multi_instance": manifest.get("multi_instance", False),
        "ldap": "?",
        "sso": "?",
        "disk": "50M",
        "ram.build": "50M",
        "ram.runtime": "50M"
    }

    maintainers = manifest.get("maintainer", {})
    if isinstance(maintainers, list):
        maintainers = [m['name'] for m in maintainers]
    else:
        maintainers = [maintainers["name"]] if maintainers.get("name") else []

    manifest["maintainers"] = maintainers

    install_questions = manifest["arguments"]["install"]
    manifest["install"] = {}
    for question in install_questions:
        name = question.pop("name")
        if "ask" in question and name in ["domain", "path", "admin", "is_public", "password"]:
            question.pop("ask")
        if question.get("example") and question.get("type") in ["domain", "path", "user", "boolean", "password"]:
            question.pop("example")

        manifest["install"][name] = question

    # Rename is_public to init_main_permission
    manifest["install"] = {(k if k != "is_public" else "init_main_permission"): v for k, v in manifest["install"].items()}

    if "init_main_permission" in manifest["install"]:
        manifest["install"]["init_main_permission"]["type"] = "group"
        if manifest["install"]["init_main_permission"].get("default") is True:
            manifest["install"]["init_main_permission"]["default"] = "visitors"
        elif manifest["install"]["init_main_permission"].get("default") is True:
            manifest["install"]["init_main_permission"]["default"] = "all_users"

    if "domain" in manifest["install"] and "path" not in manifest["install"]:
        manifest["install"]["domain"]["full_domain"] = True

    manifest["resources"] = {}
    manifest["resources"]["system_user"] = {}
    manifest["resources"]["install_dir"] = {}

    if os.system(f"grep -q 'datadir=' {app_path}/scripts/install") == 0:
        manifest["resources"]["data_dir"] = {}

    manifest["resources"]["permissions"] = {}

    if os.system(f"grep -q 'ynh_webpath_register' '{app_path}/scripts/install'") == 0:
        manifest["resources"]["permissions"]["main.url"] = "/"

    # FIXME: Parse ynh_permission_create --permission="admin" --url="/wp-login.php" --additional_urls="/wp-admin.php" --allowed=$admin_wordpress

    ports = check_output(f"sed -nr 's/(\\w+)=.*ynh_find_port[^0-9]*([0-9]+)\\)/\\1,\\2/p' '{app_path}/scripts/install'")
    if ports:
        manifest["resources"]["ports"] = {}
        for port in ports.split("\n"):
            name, default = port.split(",")
            exposed = check_output(f"sed -nr 's/.*yunohost firewall allow .*(TCP|UDP|Both).*${name}/\\1/p' '{app_path}/scripts/install'")
            if exposed == "Both":
                exposed = True

            name = name.replace("_port", "").replace("port_", "")
            if name == "port":
                name = "main"

            manifest["resources"]["ports"][f"{name}.default"] = int(default)
            if exposed:
                manifest["resources"]["ports"][f"{name}.exposed"] = exposed

    maybequote = "[\"'\"'\"']?"
    apt_dependencies = check_output(f"sed -nr 's/.*_dependencies={maybequote}(.*){maybequote}? *$/\\1/p' '{app_path}/scripts/_common.sh' 2>/dev/null | tr -d '\"' | sed 's@ @\\n@g'")
    php_version = check_output(f"sed -nr 's/^ *YNH_PHP_VERSION={maybequote}(.*){maybequote}?$/\\1/p' '{app_path}/scripts/_common.sh' 2>/dev/null | tr -d \"\\\"'\"")
    if apt_dependencies.strip():
        if php_version:
            apt_dependencies = apt_dependencies.replace("${YNH_PHP_VERSION}", php_version)
        apt_dependencies = ', '.join([d for d in apt_dependencies.split("\n") if d])
        manifest["resources"]["apt"] = {"packages": apt_dependencies}

    extra_apt_repos = check_output(r"sed -nr 's/.*_extra_app_dependencies.*repo=\"(.*)\".*package=\"(.*)\".*key=\"(.*)\"/\1,\2,\3/p' %s/scripts/install" % app_path)
    if extra_apt_repos:
        for i, extra_apt_repo in enumerate(extra_apt_repos.split("\n")):
            repo, packages, key = extra_apt_repo.split(",")
            packages = packages.replace('$', '#FIXME#$')
            if "apt" not in manifest["resources"]:
                manifest["resources"]["apt"] = {}
            if "extras" not in manifest["resources"]["apt"]:
                manifest["resources"]["apt"]["extras"] = []
            manifest["resources"]["apt"]["extras"].append({
                "repo": repo,
                "key": key,
                "packages": packages,
            })

    if os.system(f"grep -q 'ynh_mysql_setup_db' {app_path}/scripts/install") == 0:
        manifest["resources"]["database"] = {"type": "mysql"}
    elif os.system(f"grep -q 'ynh_psql_setup_db' {app_path}/scripts/install") == 0:
        manifest["resources"]["database"] = {"type": "postgresql"}

    keys_to_keep = ["packaging_format", "id", "name", "description", "version", "maintainers", "upstream", "integration", "install", "resources"]

    keys_to_del = [key for key in manifest.keys() if key not in keys_to_keep]
    for key in keys_to_del:
        del manifest[key]

    return manifest


def _dump_v2_manifest_as_toml(manifest):

    import re
    from tomlkit import document, nl, table, dumps, comment

    toml_manifest = document()
    toml_manifest.add("packaging_format", 2)
    toml_manifest.add(nl())
    toml_manifest.add("id", manifest["id"])
    toml_manifest.add("name", manifest["name"])
    for lang, value in manifest["description"].items():
        toml_manifest.add(f"description.{lang}", value)
    toml_manifest.add(nl())
    toml_manifest.add("version", manifest["version"])
    toml_manifest.add(nl())
    toml_manifest.add("maintainers", manifest["maintainers"])

    upstream = table()
    for key, value in manifest["upstream"].items():
        upstream[key] = value
    toml_manifest["upstream"] = upstream

    integration = table()
    for key, value in manifest["integration"].items():
        integration.add(key, value)
    integration["architectures"].comment('FIXME: can be replaced by a list of supported archs using the dpkg --print-architecture nomenclature (amd64/i386/armhf/arm64/armel), for example: ["amd64", "i386"]')
    integration["ldap"].comment('FIXME: replace with true, false, or "not_relevant"')
    integration["sso"].comment('FIXME: replace with true, false, or "not_relevant"')
    integration["disk"].comment('FIXME: replace with an **estimate** minimum disk requirement. e.g. 20M, 400M, 1G, ...')
    integration["ram.build"].comment('FIXME: replace with an **estimate** minimum ram requirement. e.g. 50M, 400M, 1G, ...')
    integration["ram.runtime"].comment('FIXME: replace with an **estimate** minimum ram requirement. e.g. 50M, 400M, 1G, ...')
    toml_manifest["integration"] = integration

    install = table()
    for key, value in manifest["install"].items():
        install[key] = table()
        install[key].indent(4)

        if key in ["domain", "path", "admin", "is_public", "password"]:
            install[key].add(comment("this is a generic question - ask strings are automatically handled by Yunohost's core"))

        for lang, value2 in value.get("ask", {}).items():
            install[key].add(f"ask.{lang}", value2)

        for lang, value2 in value.get("help", {}).items():
            install[key].add(f"help.{lang}", value2)

        for key2, value2 in value.items():
            if key2 in ["ask", "help"]:
                continue
            install[key].add(key2, value2)

    toml_manifest["install"] = install

    resources = table()
    for key, value in manifest["resources"].items():
        resources[key] = table()
        resources[key].indent(4)
        for key2, value2 in value.items():
            resources[key].add(key2, value2)
            if key == "apt" and key2 == "extras":
                for extra in resources[key][key2]:
                    extra.indent(8)

    toml_manifest["resources"] = resources

    toml_manifest_dump = dumps(toml_manifest)

    regex = re.compile(r'\"((description|ask|help)\.[a-z]{2})\"')
    toml_manifest_dump = regex.sub(r'\1', toml_manifest_dump)
    toml_manifest_dump = toml_manifest_dump.replace('"ram.build"', "ram.build")
    toml_manifest_dump = toml_manifest_dump.replace('"ram.runtime"', "ram.runtime")
    toml_manifest_dump = toml_manifest_dump.replace('"main.url"', "main.url")
    toml_manifest_dump = toml_manifest_dump.replace('"main.default"', "main.default")
    return toml_manifest_dump


def cleanup_scripts_and_conf(folder):

    patterns_to_remove_in_scripts = [
        "^.*ynh_abort_if_errors.*$",
        "^.*YNH_APP_ARG.*$",
        "^.*YNH_APP_INSTANCE_NAME.*$",
        r"^ *final_path=",
        r"^\s*final_path=",
        "^.*test .*-(e|d) .*final_path.*$",
        "^.*ynh_webpath_register.*$",
        "^.*ynh_webpath_available.*$",
        "^.*ynh_system_user_create.*$",
        "^.*ynh_system_user_delete.*$",
        "^.*ynh_permission_update.*$",
        "^.*ynh_permission_create.*$",
        "^.*if .*ynh_permission_exists.*$",
        "^.*if .*ynh_legacy_permissions_exists.*$",
        "^.*ynh_legacy_permissions_delete_all.*$",
        "^.*ynh_app_setting_set .*(domain|path|final_path|admin|password|port|datadir|db_name|db_user|db_pwd).*$",
        "^.*ynh_app_setting_.* is_public.*$",
        r"^.*if.*\$is_public.*$",
        "^.*_dependencies=.*$",
        "^.*ynh_install_app_dependencies.*$",
        "^.*ynh_install_extra_app_dependencies.*$",
        "^.*ynh_remove_app_dependencies.*$",
        r"^.*\$\(ynh_app_setting_get.*$",
        r"^.*ynh_secure_remove .*\$final_path.*$",
        r"^.*ynh_secure_remove .*\$datadir.*$",
        "^.*ynh_backup_before_upgrade.*$",
        "^.*ynh_clean_setup.*$",
        "^.*ynh_restore_upgradebackup.*$",
        "^db_name=.*$",
        "^db_user=.*$",
        "^db_pwd=.*$",
        "^datadir=.*$",
        "^.*ynh_psql_test_if_first_run.*$",
        "^.*ynh_mysql_setup_db.*$",
        "^.*ynh_psql_setup_db.*$",
        "^.*ynh_mysql_remove_db.*$",
        "^.*ynh_psql_remove_db.*$",
        "^.*ynh_find_port.*$",
        "^.*ynh_script_progression.*Finding an available port",
        "^.*ynh_script_progression.*Backing up the app before upgrading",
        "^.*ynh_script_progression.*Creating data directory",
        "^.*ynh_script_progression.*system user",
        "^.*ynh_script_progression.*installation settings",
        "^.*ynh_print_info.*installation settings",
        r"^.*ynh_script_progression.*\w+ dependencies",
        "^.*ynh_script_progression.*Removing app main dir",
        "^.*ynh_script_progression.*Validating.*parameters",
        "^.*ynh_script_progression.*SQL database",
        "^.*ynh_script_progression.*Configuring permissions",
    ]
    patterns_to_remove_in_scripts = [re.compile(f"({p})", re.MULTILINE) for p in patterns_to_remove_in_scripts]

    replaces = [
        ("path_url", "path"),
        ("PATH_URL", "PATH"),
        ("final_path", "install_dir"),
        ("FINALPATH", "INSTALL_DIR"),
        ("datadir", "data_dir"),
        ("DATADIR", "DATA_DIR"),
    ]

    for s in ["_common.sh", "install", "remove", "upgrade", "backup", "restore"]:

        script = f"{folder}/scripts/{s}"

        if not os.path.exists(script):
            continue

        content = open(script).read()

        for pattern in patterns_to_remove_in_scripts:
            content = pattern.sub(r"#REMOVEME? \1", content)

        for pattern, replace in replaces:
            content = content.replace(pattern, replace)

        open(script, "w").write(content)

    for conf in os.listdir(f"{folder}/conf"):

        conf = f"{folder}/conf/{conf}"

        if not os.path.isfile(conf):
            continue

        content = open(conf).read()
        content_init = content

        for pattern, replace in replaces:
            content = content.replace(pattern, replace)

        if content_init != content:
            open(conf, "w").write(content)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Attempt to automatically convert a v1 YunoHost app to v2 (at least as much as possible) : parse the app scripts to auto-generate the manifest.toml, and remove now-useless lines from the app scripts"
    )
    parser.add_argument(
        "app_path", help="Path to the app to convert"
    )

    args = parser.parse_args()

    manifest = _convert_v1_manifest_to_v2(args.app_path)
    open(args.app_path + "/manifest.toml", "w").write(_dump_v2_manifest_as_toml(manifest))

    cleanup_scripts_and_conf(args.app_path)
