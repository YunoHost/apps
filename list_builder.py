#!/usr/bin/python3

import copy
import sys
import os
import re
import json
from shutil import which
import toml
import subprocess
import time
from typing import TextIO, Generator, Any
from pathlib import Path

from collections import OrderedDict
from tools.packaging_v2.convert_v1_manifest_to_v2_for_catalog import convert_v1_manifest_to_v2_for_catalog

now = time.time()

REPO_APPS_PATH = Path(__file__).parent

# Load categories and reformat the structure to have a list with an "id" key
categories = toml.load((REPO_APPS_PATH / "categories.toml").open("r", encoding="utf-8"))
for category_id, infos in categories.items():
    infos["id"] = category_id
    for subtag_id, subtag_infos in infos.get("subtags", {}).items():
        subtag_infos["id"] = subtag_id
    infos["subtags"] = list(infos.get('subtags', {}).values())

categories = list(categories.values())

# (Same for antifeatures)
antifeatures = toml.load((REPO_APPS_PATH / "antifeatures.toml").open("r", encoding="utf-8"))
for antifeature_id, infos in antifeatures.items():
    infos["id"] = antifeature_id
antifeatures = list(antifeatures.values())

# Load the app catalog and filter out the non-working ones
catalog = toml.load((REPO_APPS_PATH / "apps.toml").open("r", encoding="utf-8"))
catalog = {
    app: infos for app, infos in catalog.items() if infos.get("state") != "notworking"
}

my_env = os.environ.copy()
my_env["GIT_TERMINAL_PROMPT"] = "0"

(REPO_APPS_PATH / ".apps_cache").mkdir(exist_ok=True)
(REPO_APPS_PATH / "builds").mkdir(exist_ok=True)


def error(msg: str) -> None:
    msg = "[Applist builder error] " + msg
    if which("sendxmpppy") is not None:
        subprocess.call(["sendxmpppy", msg], stdout=open(os.devnull, "wb"))
    print(msg + "\n")


# Progress bar helper, stolen from https://stackoverflow.com/a/34482761
def progressbar(it: list[Any], prefix: str = "", size: int = 60, file: TextIO = sys.stdout
                ) -> Generator[Any, None, None]:
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


def app_cache_folder(app: str) -> Path:
    return REPO_APPS_PATH / ".apps_cache" / app


def git(cmd: str, in_folder: Path | None = None):

    if in_folder:
        cmd = "-C " + str(in_folder) + " " + cmd
    cmd = "git " + cmd
    return subprocess.check_output(cmd.split(), env=my_env).strip().decode("utf-8")


def refresh_all_caches() -> None:
    for app, infos in progressbar(sorted(catalog.items()), "Updating git clones: ", 40):
        app = app.lower()
        if not app_cache_folder(app).exists():
            try:
                init_cache(app, infos)
            except Exception as e:
                error("Failed to init cache for %s" % app)
        else:
            try:
                refresh_cache(app, infos)
            except Exception as e:
                error("Failed to not refresh cache for %s" % app)


def init_cache(app: str, infos: dict[str, str]) -> None:

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


def refresh_cache(app: str, infos: dict[str, str]) -> None:

    # Don't refresh if already refreshed during last hour
    fetch_head = app_cache_folder(app) / ".git" / "FETCH_HEAD"
    if fetch_head.exists() and (now - fetch_head.stat().st_mtime) < 3600:
        return

    branch = infos.get("branch", "master")

    try:
        git("remote set-url origin " + infos["url"], in_folder=app_cache_folder(app))
        # With git >= 2.22
        # current_branch = git("branch --show-current", in_folder=app_cache_folder(app))
        current_branch = git(
            "rev-parse --abbrev-ref HEAD", app_cache_folder(app)
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
        if (fetch_head.exists() and (now - fetch_head.stat().st_mtime) < 24 * 3600):
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

    for appid, app in result_dict_with_manifest_v2.items():
        appid = appid.lower()
        if (REPO_APPS_PATH / "logos" / f"{appid}.png").exists():
            logo_hash = subprocess.check_output(["sha256sum", f"logos/{appid}.png"]).strip().decode("utf-8").split()[0]
            os.system(f"cp logos/{appid}.png builds/default/v3/logos/{logo_hash}.png")
            # FIXME: implement something to cleanup old logo stuf in the builds/.../logos/ folder somehow
        else:
            logo_hash = None
        app["logo_hash"] = logo_hash

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
            "antifeatures": infos.get("antifeatures"),
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
    assert this_app_cache.exists(), "No cache yet for %s" % app

    commit_timestamps_for_this_app_in_catalog = git(f'log -G "{app}"|\[{app}\] --first-parent --reverse --date=unix --format=%cd -- apps.json apps.toml')
    # Assume the first entry we get (= the oldest) is the time the app was added
    infos["added_in_catalog"] = int(commit_timestamps_for_this_app_in_catalog.split("\n")[0])

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
    if (this_app_cache / "manifest.toml").exists():
        manifest = toml.load((this_app_cache / "manifest.toml").open("r"), _dict=OrderedDict)
    else:
        manifest = json.load((this_app_cache / "manifest.json").open("r"))

    return {
        "id": manifest["id"],
        "git": {
            "branch": infos["branch"],
            "revision": infos["revision"],
            "url": infos["url"],
        },
        "added_in_catalog": infos["added_in_catalog"],
        "lastUpdate": timestamp,
        "manifest": manifest,
        "state": infos["state"],
        "level": infos.get("level", "?"),
        "maintained": not 'package-not-maintained' in infos.get('antifeatures', []),
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
