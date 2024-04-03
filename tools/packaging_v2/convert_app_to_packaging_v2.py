#!/usr/bin/env python3

import argparse
import json
import os
import re
import subprocess
from glob import glob


def check_output(cmd):
    return subprocess.check_output(cmd, shell=True).decode("utf-8").strip()


def convert_app_sources(folder):

    def parse_and_convert_src(filename):

        D = {}
        raw = open(filename).read()
        for line in raw.split("\n"):
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, value = line.split("=", 1)
            key = key.replace("SOURCE_", "").lower()
            D[key] = value

        new_D = {
            "url": D["url"],
            "sha256": D["sum"],
        }

        if D.get("format", "tar.gz") not in [
            "zip",
            "tar.gz",
            "tar.xz",
            "tgz",
            "tar.bz2",
        ]:
            new_D["format"] = D["format"]
            if "filename" in D:
                new_D["rename"] = D["filename"]
        elif "in_subdir" in D and D["in_subdir"] != "true":
            new_D["in_subdir"] = False

        return new_D

    sources = {}

    remap_id = {
        "app": "main",
        "amd64": "main.amd64",
        "i386": "main.i386",
        "arm64": "main.arm64",
        "armhf": "main.armhf",
        "arm7": "main.armhf",
        "app.arm64": "main.arm64",
        "app.x86_64": "main.amd64",
        "app.x64": "main.amd64",
        "app.arm": "main.armhf",
        "app.armhf": "main.armhf",
        "app.armv7": "main.armhf",
        "app.386": "main.i386",
        "app.x86": "main.i386",
        "app.armel": "main.armel",
        "armel": "main.armel",
        "aarch64": "main.arm64",
        "x86-64": "main.amd64",
        "armv6": "main.armel",
        "armv7": "main.armhf",
    }

    for filename in glob(folder + "/conf/*.src"):
        id_ = os.path.basename(filename).rsplit(".", 1)[0]
        if id_ in remap_id:
            id_ = remap_id[id_]

        sources[id_] = parse_and_convert_src(filename)

        if id_.startswith("main."):
            if "main" not in sources:
                sources["main"] = sources[id_]
            arch = id_.split(".")[1]
            sources["main"][arch + ".url"] = sources[id_]["url"]
            sources["main"][arch + ".sha256"] = sources[id_]["sha256"]
            del sources[id_]["url"]
            del sources[id_]["sha256"]
            del sources[id_]

        os.system(f"rm '{filename}'")

    return sources


def _convert_v1_manifest_to_v2(app_path):

    manifest = json.load(open(app_path + "/manifest.json"))

    if "upstream" not in manifest:
        manifest["upstream"] = {}

    if "license" in manifest and "license" not in manifest["upstream"]:
        manifest["upstream"]["license"] = manifest["license"]

    if "url" in manifest and "website" not in manifest["upstream"]:
        manifest["upstream"]["website"] = manifest["url"]

    manifest["upstream"]["cpe"] = "???"
    manifest["upstream"]["fund"] = "???"

    manifest["integration"] = {
        "yunohost": manifest.get("requirements", {}).get("yunohost"),
        "architectures": "all",
        "multi_instance": manifest.get("multi_instance", False),
        "ldap": "?",
        "sso": "?",
        "disk": "50M",
        "ram.build": "50M",
        "ram.runtime": "50M",
    }

    maintainers = manifest.get("maintainer", {})
    if isinstance(maintainers, list):
        maintainers = [m["name"] for m in maintainers]
    else:
        maintainers = [maintainers["name"]] if maintainers.get("name") else []

    manifest["maintainers"] = maintainers

    install_questions = manifest["arguments"]["install"]
    manifest["install"] = {}
    for question in install_questions:
        name = question.pop("name")
        if "ask" in question and name in [
            "domain",
            "path",
            "admin",
            "is_public",
            "password",
        ]:
            question.pop("ask")
        if question.get("example") and question.get("type") in [
            "domain",
            "path",
            "user",
            "boolean",
            "password",
        ]:
            question.pop("example")

        manifest["install"][name] = question

    # Rename is_public to init_main_permission
    manifest["install"] = {
        (k if k != "is_public" else "init_main_permission"): v
        for k, v in manifest["install"].items()
    }

    if "init_main_permission" in manifest["install"]:
        manifest["install"]["init_main_permission"]["type"] = "group"
        if manifest["install"]["init_main_permission"].get("default") is True:
            manifest["install"]["init_main_permission"]["default"] = "visitors"
        elif manifest["install"]["init_main_permission"].get("default") is True:
            manifest["install"]["init_main_permission"]["default"] = "all_users"

    manifest["resources"] = {}

    sources = convert_app_sources(app_path)
    if sources:
        manifest["resources"]["sources"] = sources

    manifest["resources"]["system_user"] = {}
    manifest["resources"]["install_dir"] = {}

    if os.system(f"grep -q 'datadir=' {app_path}/scripts/install") == 0:
        manifest["resources"]["data_dir"] = {}

    manifest["resources"]["permissions"] = {}

    if os.system(f"grep -q 'ynh_webpath_register' '{app_path}/scripts/install'") == 0:
        manifest["resources"]["permissions"]["main.url"] = "/"

    # FIXME: Parse ynh_permission_create --permission="admin" --url="/wp-login.php" --additional_urls="/wp-admin.php" --allowed=$admin_wordpress

    ports = check_output(
        f"sed -nr 's/(\\w+)=.*ynh_find_port[^0-9]*([0-9]+)\\)/\\1,\\2/p' '{app_path}/scripts/install'"
    )
    if ports:
        manifest["resources"]["ports"] = {}
        for port in ports.split("\n"):
            name, default = port.split(",")
            exposed = check_output(
                f"sed -nr 's/.*yunohost firewall allow .*(TCP|UDP|Both).*${name}/\\1/p' '{app_path}/scripts/install'"
            )
            if exposed == "Both":
                exposed = True

            name = name.replace("_port", "").replace("port_", "")
            if name == "port":
                name = "main"

            if not default.isdigit():
                print(
                    f"Failed to parse '{default}' as a port number ... Will use 12345 instead"
                )
                default = 12345

            manifest["resources"]["ports"][f"{name}.default"] = int(default)
            if exposed:
                manifest["resources"]["ports"][f"{name}.exposed"] = exposed

    maybequote = "[\"'\"'\"']?"
    apt_dependencies = check_output(
        f"sed -nr 's/.*_dependencies={maybequote}(.*){maybequote}? *$/\\1/p' '{app_path}/scripts/_common.sh' 2>/dev/null | tr -d '\"' | sed 's@ @\\n@g'"
    )
    php_version = check_output(
        f"sed -nr 's/^ *YNH_PHP_VERSION={maybequote}(.*){maybequote}?$/\\1/p' '{app_path}/scripts/_common.sh' 2>/dev/null | tr -d \"\\\"'\""
    )
    if apt_dependencies.strip():
        if php_version:
            apt_dependencies = apt_dependencies.replace(
                "${YNH_PHP_VERSION}", php_version
            )
        apt_dependencies = ", ".join([d for d in apt_dependencies.split("\n") if d])
        manifest["resources"]["apt"] = {"packages": apt_dependencies}

    extra_apt_repos = check_output(
        r"sed -nr 's/.*_extra_app_dependencies.*repo=\"(.*)\".*package=\"(.*)\".*key=\"(.*)\"/\1,\2,\3/p' %s/scripts/install"
        % app_path
    )
    if extra_apt_repos:
        for i, extra_apt_repo in enumerate(extra_apt_repos.split("\n")):
            repo, packages, key = extra_apt_repo.split(",")
            packages = packages.replace("$", "#FIXME#$")
            if "apt" not in manifest["resources"]:
                manifest["resources"]["apt"] = {}
            if "extras" not in manifest["resources"]["apt"]:
                manifest["resources"]["apt"]["extras"] = []
            manifest["resources"]["apt"]["extras"].append(
                {
                    "repo": repo,
                    "key": key,
                    "packages": packages,
                }
            )

    if os.system(f"grep -q 'ynh_mysql_setup_db' {app_path}/scripts/install") == 0:
        manifest["resources"]["database"] = {"type": "mysql"}
    elif os.system(f"grep -q 'ynh_psql_setup_db' {app_path}/scripts/install") == 0:
        manifest["resources"]["database"] = {"type": "postgresql"}

    keys_to_keep = [
        "packaging_format",
        "id",
        "name",
        "description",
        "version",
        "maintainers",
        "upstream",
        "integration",
        "install",
        "resources",
    ]

    keys_to_del = [key for key in manifest.keys() if key not in keys_to_keep]
    for key in keys_to_del:
        del manifest[key]

    return manifest


def _dump_v2_manifest_as_toml(manifest):

    import re

    from tomlkit import comment, document, dumps, nl, table

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
    upstream["cpe"].comment(
        "FIXME: optional but recommended if relevant, this is meant to contain the Common Platform Enumeration, which is sort of a standard id for applications defined by the NIST. In particular, Yunohost may use this is in the future to easily track CVE (=security reports) related to apps. The CPE may be obtained by searching here: https://nvd.nist.gov/products/cpe/search. For example, for Nextcloud, the CPE is 'cpe:2.3:a:nextcloud:nextcloud' (no need to include the version number)"
    )
    upstream["fund"].comment(
        "FIXME: optional but recommended (or remove if irrelevant / not applicable). This is meant to be an URL where people can financially support this app, especially when its development is based on volunteers and/or financed by its community. YunoHost may later advertise it in the webadmin."
    )
    toml_manifest["upstream"] = upstream

    integration = table()
    for key, value in manifest["integration"].items():
        integration.add(key, value)
    integration["architectures"].comment(
        'FIXME: can be replaced by a list of supported archs using the dpkg --print-architecture nomenclature (amd64/i386/armhf/arm64), for example: ["amd64", "i386"]'
    )
    integration["ldap"].comment(
        'FIXME: replace with true, false, or "not_relevant". Not to confuse with the "sso" key : the "ldap" key corresponds to wether or not a user *can* login on the app using its YunoHost credentials.'
    )
    integration["sso"].comment(
        'FIXME: replace with true, false, or "not_relevant". Not to confuse with the "ldap" key : the "sso" key corresponds to wether or not a user is *automatically logged-in* on the app when logged-in on the YunoHost portal.'
    )
    integration["disk"].comment(
        "FIXME: replace with an **estimate** minimum disk requirement. e.g. 20M, 400M, 1G, ..."
    )
    integration["ram.build"].comment(
        "FIXME: replace with an **estimate** minimum ram requirement. e.g. 50M, 400M, 1G, ..."
    )
    integration["ram.runtime"].comment(
        "FIXME: replace with an **estimate** minimum ram requirement. e.g. 50M, 400M, 1G, ..."
    )
    toml_manifest["integration"] = integration

    install = table()
    for key, value in manifest["install"].items():
        install[key] = table()
        install[key].indent(4)

        if key in ["domain", "path", "admin", "is_public", "password"]:
            install[key].add(
                comment(
                    "this is a generic question - ask strings are automatically handled by Yunohost's core"
                )
            )

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
            if not isinstance(value2, dict):
                resources[key].add(key2, value2)
            else:
                t = table()
                t.indent(4)
                resources[key].add(key2, t)
                for key3, value3 in value2.items():
                    t.add(key3, value3)
                t.add(nl())

            if key == "apt" and key2 == "extras":
                for extra in resources[key][key2]:
                    extra.indent(8)

    toml_manifest["resources"] = resources

    toml_manifest_dump = dumps(toml_manifest)

    regex = re.compile(r"\"((description|ask|help)\.[a-z]{2})\"")
    toml_manifest_dump = regex.sub(r"\1", toml_manifest_dump)
    toml_manifest_dump = toml_manifest_dump.replace('"ram.build"', "ram.build")
    toml_manifest_dump = toml_manifest_dump.replace('"ram.runtime"', "ram.runtime")
    toml_manifest_dump = toml_manifest_dump.replace('"main.url"', "main.url")
    toml_manifest_dump = toml_manifest_dump.replace('"main.default"', "main.default")
    toml_manifest_dump = toml_manifest_dump.replace('"armhf.url"', "armhf.url")
    toml_manifest_dump = toml_manifest_dump.replace('"armhf.sha256"', "armhf.sha256")
    toml_manifest_dump = toml_manifest_dump.replace('"arm64.url"', "arm64.url")
    toml_manifest_dump = toml_manifest_dump.replace('"arm64.sha256"', "arm64.sha256")
    toml_manifest_dump = toml_manifest_dump.replace('"amd64.url"', "amd64.url")
    toml_manifest_dump = toml_manifest_dump.replace('"amd64.sha256"', "amd64.sha256")
    toml_manifest_dump = toml_manifest_dump.replace('"i386.url"', "i386.url")
    toml_manifest_dump = toml_manifest_dump.replace('"i386.sha256"', "i386.sha256")
    toml_manifest_dump = toml_manifest_dump.replace('"armel.url"', "armel.url")
    toml_manifest_dump = toml_manifest_dump.replace('"armel.sha256"', "armel.sha256")

    if "ports" in manifest["resources"]:
        for port_thing in manifest["resources"]["ports"].keys():
            toml_manifest_dump = toml_manifest_dump.replace(
                f'"{port_thing}"', f"{port_thing}"
            )

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
        "^old_domain=.*$",
        "^new_domain=.*$",
        "^old_path=.*$",
        "^new_path=.*$",
        r"change_path=(0|1)\s*$",
        r"change_domain=(0|1)\s*$",
        r"^\s*if.*old_domain.*new_domain.*$",
        r"^\s*if.*old_path.*new_path.*$",
        "^datadir=.*$",
        "^phpversion=.*$",
        "^YNH_PHP_VERSION=.*$",
        "^.*ynh_psql_test_if_first_run.*$",
        "^.*ynh_mysql_setup_db.*$",
        "^.*ynh_psql_setup_db.*$",
        "^.*ynh_mysql_remove_db.*$",
        "^.*ynh_psql_remove_db.*$",
        "^.*ynh_find_port.*$",
        "^.*ynh_script_progression.*Finding an available port",
        "^.*ynh_script_progression.*Backing up the app before upgrading",
        "^.*ynh_script_progression.*Backing up the app before changing its URL",
        "^.*ynh_script_progression.*Creating data directory",
        "^.*ynh_script_progression.*system user",
        "^.*ynh_script_progression.*installation settings",
        "^.*ynh_print_info.*installation settings",
        r"^.*ynh_script_progression.*\w+ dependencies",
        "^.*ynh_script_progression.*Removing app main dir",
        "^.*ynh_script_progression.*Validating.*parameters",
        "^.*ynh_script_progression.*SQL database",
        "^.*ynh_script_progression.*Configuring permissions",
        "^.*ynh_script_progression.*Reloading NGINX web server",
        "^.*ynh_systemd_action --service_name=nginx --action=reload",
    ]
    patterns_to_remove_in_scripts = [
        re.compile(f"({p})", re.MULTILINE) for p in patterns_to_remove_in_scripts
    ]

    replaces = [
        ("path_url", "path"),
        ("PATH_URL", "PATH"),
        ("final_path", "install_dir"),
        ("FINALPATH", "INSTALL_DIR"),
        ("datadir", "data_dir"),
        ("DATADIR", "DATA_DIR"),
        ('--source_id="$architecture"', ""),
        ('--source_id="$YNH_ARCH"', ""),
        ("--source_id=app", ""),
        ('--source_id="app.$architecture"', ""),
    ]

    for s in [
        "_common.sh",
        "install",
        "remove",
        "upgrade",
        "backup",
        "restore",
        "change_url",
    ]:

        script = f"{folder}/scripts/{s}"

        if not os.path.exists(script):
            continue

        content = open(script).read()

        for pattern in patterns_to_remove_in_scripts:
            if (
                "^.*ynh_script_progression.*Reloading NGINX web server"
                in pattern.pattern
                and s == "restore"
            ):
                # This case is legit
                continue
            if (
                "^.*ynh_systemd_action --service_name=nginx --action=reload"
                in pattern.pattern
                and s == "restore"
            ):
                # This case is legit
                continue
            content = pattern.sub(r"#REMOVEME? \1", content)

        for pattern, replace in replaces:
            content = content.replace(pattern, replace)

        if s == "change_url":

            pattern = re.compile("(^.*nginx.*$)", re.MULTILINE)
            content = pattern.sub(r"#REMOVEME? \1", content)

            pattern = re.compile(
                "(^.*ynh_script_progress.*Updat.* NGINX.*conf.*$)", re.MULTILINE
            )
            content = pattern.sub(r"\1\n\nynh_change_url_nginx_config", content)

            pattern = re.compile(r"(ynh_clean_check_starting)", re.MULTILINE)
            content = pattern.sub(r"#REMOVEME? \1", content)
            pattern = re.compile(r"(^\s+domain=.*$)", re.MULTILINE)
            content = pattern.sub(r"#REMOVEME? \1", content)
            pattern = re.compile(r"(^\s+path=.*$)", re.MULTILINE)
            content = pattern.sub(r"#REMOVEME? \1", content)

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
    parser.add_argument("app_path", help="Path to the app to convert")

    args = parser.parse_args()

    manifest = _convert_v1_manifest_to_v2(args.app_path)
    with open(args.app_path + "/manifest.toml", "w") as manifest_file:
        manifest_file.write(
            "#:schema https://raw.githubusercontent.com/YunoHost/apps/master/schemas/manifest.v2.schema.json\n\n"
        )
        manifest_file.write(_dump_v2_manifest_as_toml(manifest))

    cleanup_scripts_and_conf(args.app_path)
