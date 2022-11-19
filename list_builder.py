#!/usr/bin/python3

import copy
import sys
import os
import re
import json
import toml
import subprocess
import yaml
import time

from collections import OrderedDict
from tools.packaging_v2.convert_v1_manifest_to_v2_for_catalog import convert_v1_manifest_to_v2_for_catalog

now = time.time()

catalog = json.load(open("apps.json"))
catalog = {
    app: infos for app, infos in catalog.items() if infos.get("state") != "notworking"
}

my_env = os.environ.copy()
my_env["GIT_TERMINAL_PROMPT"] = "0"

os.makedirs(".apps_cache", exist_ok=True)
os.makedirs("builds/", exist_ok=True)


def error(msg):
    msg = "[Applist builder error] " + msg
    if os.path.exists("/usr/bin/sendxmpppy"):
        subprocess.call(["sendxmpppy", msg], stdout=open(os.devnull, "wb"))
    print(msg + "\n")


# Progress bar helper, stolen from https://stackoverflow.com/a/34482761
def progressbar(it, prefix="", size=60, file=sys.stdout):
    count = len(it)

    def show(j, name=""):
        name += "          "
        x = int(size * j / count)
        file.write(
            "%s[%s%s] %i/%i %s\r" % (prefix, "#" * x, "." * (size - x), j, count, name)
        )
        file.flush()

    show(0)
    for i, item in enumerate(it):
        yield item
        show(i + 1, item[0])
    file.write("\n")
    file.flush()


###################################
# App git clones cache management #
###################################


def app_cache_folder(app):
    return os.path.join(".apps_cache", app)


def git(cmd, in_folder=None):

    if in_folder:
        cmd = "-C " + in_folder + " " + cmd
    cmd = "git " + cmd
    return subprocess.check_output(cmd.split(), env=my_env).strip().decode("utf-8")


def refresh_all_caches():

    for app, infos in progressbar(sorted(catalog.items()), "Updating git clones: ", 40):
        app = app.lower()
        if not os.path.exists(app_cache_folder(app)):
            try:
                init_cache(app, infos)
            except Exception as e:
                error("Failed to init cache for %s" % app)
        else:
            try:
                refresh_cache(app, infos)
            except Exception as e:
                error("Failed to not refresh cache for %s" % app)


def init_cache(app, infos):

    if infos["state"] == "notworking":
        depth = 5
    if infos["state"] == "inprogress":
        depth = 20
    else:
        depth = 40

    git(
        "clone --quiet --depth {depth} --single-branch --branch {branch} {url} {folder}".format(
            depth=depth,
            url=infos["url"],
            branch=infos.get("branch", "master"),
            folder=app_cache_folder(app),
        )
    )


def refresh_cache(app, infos):

    # Don't refresh if already refreshed during last hour
    fetch_head = app_cache_folder(app) + "/.git/FETCH_HEAD"
    if os.path.exists(fetch_head) and now - os.path.getmtime(fetch_head) < 3600:
        return

    branch = infos.get("branch", "master")

    try:
        git("remote set-url origin " + infos["url"], in_folder=app_cache_folder(app))
        # With git >= 2.22
        # current_branch = git("branch --show-current", in_folder=app_cache_folder(app))
        current_branch = git(
            "rev-parse --abbrev-ref HEAD", in_folder=app_cache_folder(app)
        )
        if current_branch != branch:
            # With git >= 2.13
            # all_branches = git("branch --format=%(refname:short)", in_folder=app_cache_folder(app)).split()
            all_branches = git("branch", in_folder=app_cache_folder(app)).split()
            all_branches.remove("*")
            if branch not in all_branches:
                git(
                    "remote set-branches --add origin %s" % branch,
                    in_folder=app_cache_folder(app),
                )
                git(
                    "fetch origin %s:%s" % (branch, branch),
                    in_folder=app_cache_folder(app),
                )
            else:
                git("checkout --force %s" % branch, in_folder=app_cache_folder(app))

        git("fetch --quiet origin %s --force" % branch, in_folder=app_cache_folder(app))
        git("reset origin/%s --hard" % branch, in_folder=app_cache_folder(app))
    except:
        # Sometimes there are tmp issue such that the refresh cache ..
        # we don't trigger an error unless the cache hasnt been updated since more than 24 hours
        if (
            os.path.exists(fetch_head)
            and now - os.path.getmtime(fetch_head) < 24 * 3600
        ):
            pass
        else:
            raise


################################
# Actual list build management #
################################


def build_catalog():

    result_dict = {}

    for app, infos in progressbar(sorted(catalog.items()), "Processing: ", 40):

        app = app.lower()

        try:
            app_dict = build_app_dict(app, infos)
        except Exception as e:
            error("Processing %s failed: %s" % (app, str(e)))
            continue

        result_dict[app_dict["id"]] = app_dict

    #############################
    # Current catalog API v2    #
    #############################

    result_dict_with_manifest_v1 = copy.deepcopy(result_dict)
    result_dict_with_manifest_v1 = {name: infos for name, infos in result_dict_with_manifest_v1.items() if float(str(infos["manifest"].get("packaging_format", "")).strip() or "0") < 2}

    categories = yaml.load(open("categories.yml").read())
    antifeatures = yaml.load(open("antifeatures.yml").read())
    os.system("mkdir -p ./builds/default/v2/")
    with open("builds/default/v2/apps.json", "w") as f:
        f.write(
            json.dumps(
                {
                    "apps": result_dict_with_manifest_v1,
                    "categories": categories,
                    "antifeatures": antifeatures,
                },
                sort_keys=True,
            )
        )

    #############################################
    # Catalog catalog API v3 (with manifest v2) #
    #############################################

    result_dict_with_manifest_v2 = copy.deepcopy(result_dict)
    for app in result_dict_with_manifest_v2.values():
        packaging_format = float(str(app["manifest"].get("packaging_format", "")).strip() or "0")
        if packaging_format < 2:
            app["manifest"] = convert_v1_manifest_to_v2_for_catalog(app["manifest"])

    # We also remove the app install question and resources parts which aint needed anymore by webadmin etc (or at least we think ;P)
    for app in result_dict_with_manifest_v2.values():
        if "manifest" in app and "install" in app["manifest"]:
            del app["manifest"]["install"]
        if "manifest" in app and "resources" in app["manifest"]:
            del app["manifest"]["resources"]

    os.system("mkdir -p ./builds/default/v3/")
    with open("builds/default/v3/apps.json", "w") as f:
        f.write(
            json.dumps(
                {
                    "apps": result_dict_with_manifest_v2,
                    "categories": categories,
                    "antifeatures": antifeatures,
                },
                sort_keys=True,
            )
        )

    ##############################
    # Version for catalog in doc #
    ##############################
    categories = yaml.load(open("categories.yml").read())
    os.system("mkdir -p ./builds/default/doc_catalog")

    def infos_for_doc_catalog(infos):
        level = infos.get("level")
        if not isinstance(level, int):
            level = -1
        return {
            "id": infos["id"],
            "category": infos["category"],
            "url": infos["git"]["url"],
            "name": infos["manifest"]["name"],
            "description": infos["manifest"]["description"],
            "state": infos["state"],
            "level": level,
            "broken": level <= 0,
            "good_quality": level >= 8,
            "bad_quality": level <= 5,
            "antifeatures": infos["antifeatures"],
            "potential_alternative_to": infos.get("potential_alternative_to", []),
        }

    result_dict_doc = {
        k: infos_for_doc_catalog(v)
        for k, v in result_dict.items()
        if v["state"] == "working"
    }
    with open("builds/default/doc_catalog/apps.json", "w") as f:
        f.write(
            json.dumps(
                {"apps": result_dict_doc, "categories": categories}, sort_keys=True
            )
        )


def build_app_dict(app, infos):

    # Make sure we have some cache
    this_app_cache = app_cache_folder(app)
    assert os.path.exists(this_app_cache), "No cache yet for %s" % app

    infos["branch"] = infos.get("branch", "master")
    infos["revision"] = infos.get("revision", "HEAD")

    # If using head, find the most recent meaningful commit in logs
    if infos["revision"] == "HEAD":
        relevant_files = [
            "manifest.json",
            "manifest.toml",
            "config_panel.toml",
            "hooks/",
            "scripts/",
            "conf/",
            "sources/",
        ]
        most_recent_relevant_commit = (
            "rev-list --full-history --all -n 1 -- " + " ".join(relevant_files)
        )
        infos["revision"] = git(most_recent_relevant_commit, in_folder=this_app_cache)
        assert re.match(r"^[0-9a-f]+$", infos["revision"]), (
            "Output was not a commit? '%s'" % infos["revision"]
        )
    # Otherwise, validate commit exists
    else:
        assert infos["revision"] in git(
            "rev-list --all", in_folder=this_app_cache
        ).split("\n"), ("Revision ain't in history ? %s" % infos["revision"])

    # Find timestamp corresponding to that commit
    timestamp = git(
        "show -s --format=%ct " + infos["revision"], in_folder=this_app_cache
    )
    assert re.match(r"^[0-9]+$", timestamp), (
        "Failed to get timestamp for revision ? '%s'" % timestamp
    )
    timestamp = int(timestamp)

    # Build the dict with all the infos
    if os.path.exists(this_app_cache + "/manifest.toml"):
        manifest = toml.load(open(this_app_cache + "/manifest.toml"), _dict=OrderedDict)
    else:
        manifest = json.load(open(this_app_cache + "/manifest.json"))

    return {
        "id": manifest["id"],
        "git": {
            "branch": infos["branch"],
            "revision": infos["revision"],
            "url": infos["url"],
        },
        "lastUpdate": timestamp,
        "manifest": manifest,
        "state": infos["state"],
        "level": infos.get("level", "?"),
        "maintained": infos.get("maintained", True),
        "high_quality": infos.get("high_quality", False),
        "featured": infos.get("featured", False),
        "category": infos.get("category", None),
        "subtags": infos.get("subtags", []),
        "potential_alternative_to": infos.get("potential_alternative_to", []),
        "antifeatures": list(
            set(list(manifest.get("antifeatures", {}).keys()) + infos.get("antifeatures", []))
        ),
    }


if __name__ == "__main__":
    refresh_all_caches()
    build_catalog()
