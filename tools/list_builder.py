#!/usr/bin/env python3

import argparse
import copy
import json
import logging
import multiprocessing
import shutil
import subprocess
import time
from collections import OrderedDict
from functools import cache
from pathlib import Path
from typing import Any, Optional

import toml
import tqdm
from tqdm.contrib.logging import logging_redirect_tqdm
from git import Repo

import appslib.logging_sender  # pylint: disable=import-error
from app_caches import app_cache_folder  # pylint: disable=import-error
from app_caches import apps_cache_update_all  # pylint: disable=import-error
from appslib.utils import (REPO_APPS_ROOT,  # pylint: disable=import-error
                           get_antifeatures, get_catalog, get_categories)
from packaging_v2.convert_v1_manifest_to_v2_for_catalog import \
    convert_v1_manifest_to_v2_for_catalog  # pylint: disable=import-error

now = time.time()


@cache
def categories_list():
    # Load categories and reformat the structure to have a list with an "id" key
    new_categories = get_categories()
    for category_id, infos in new_categories.items():
        infos["id"] = category_id
        for subtag_id, subtag_infos in infos.get("subtags", {}).items():
            subtag_infos["id"] = subtag_id
        infos["subtags"] = list(infos.get('subtags', {}).values())
    return list(new_categories.values())


@cache
def antifeatures_list():
    # (Same for antifeatures)
    new_antifeatures = get_antifeatures()
    for antifeature_id, infos in new_antifeatures.items():
        infos["id"] = antifeature_id
    return list(new_antifeatures.values())


################################
# Actual list build management #
################################

def __build_app_dict(data) -> Optional[tuple[str, dict[str, Any]]]:
    name, info = data
    try:
        return name, build_app_dict(name, info)
    except Exception as err:
        logging.error("Error while updating %s: %s", name, err)


def build_base_catalog(nproc: int):
    result_dict = {}
    catalog = get_catalog(working_only=True)

    with multiprocessing.Pool(processes=nproc) as pool:
        with logging_redirect_tqdm():
            tasks = pool.imap(__build_app_dict, catalog.items())

            for result in tqdm.tqdm(tasks, total=len(catalog.keys()), ascii=" ·#"):
                if result is not None:
                    name, info = result
                    result_dict[name] = info

    return result_dict


def write_catalog_v2(base_catalog, target_dir: Path) -> None:
    result_dict_with_manifest_v1 = copy.deepcopy(base_catalog)
    result_dict_with_manifest_v1 = {
        name: infos
        for name, infos in result_dict_with_manifest_v1.items()
        if float(str(infos["manifest"].get("packaging_format", "")).strip() or "0") < 2
    }
    full_catalog = {
        "apps": result_dict_with_manifest_v1,
        "categories": categories_list(),
        "antifeatures": antifeatures_list(),
    }

    target_file = target_dir / "apps.json"
    target_file.parent.mkdir(parents=True, exist_ok=True)
    target_file.open("w", encoding="utf-8").write(json.dumps(full_catalog, sort_keys=True))


def write_catalog_v3(base_catalog, target_dir: Path) -> None:
    result_dict_with_manifest_v2 = copy.deepcopy(base_catalog)
    for app in result_dict_with_manifest_v2.values():
        packaging_format = float(str(app["manifest"].get("packaging_format", "")).strip() or "0")
        if packaging_format < 2:
            app["manifest"] = convert_v1_manifest_to_v2_for_catalog(app["manifest"])

    # We also remove the app install question and resources parts which aint needed anymore
    # by webadmin etc (or at least we think ;P)
    for app in result_dict_with_manifest_v2.values():
        if "manifest" in app and "install" in app["manifest"]:
            del app["manifest"]["install"]
        if "manifest" in app and "resources" in app["manifest"]:
            del app["manifest"]["resources"]

    logos_dir = target_dir / "logos"
    logos_dir.mkdir(parents=True, exist_ok=True)
    for appid, app in result_dict_with_manifest_v2.items():
        appid = appid.lower()
        logo_source = REPO_APPS_ROOT / "logos" / f"{appid}.png"
        if logo_source.exists():
            logo_hash = subprocess.check_output(["sha256sum", logo_source]).strip().decode("utf-8").split()[0]
            shutil.copyfile(logo_source, logos_dir / f"{logo_hash}.png")
            # FIXME: implement something to cleanup old logo stuf in the builds/.../logos/ folder somehow
        else:
            logo_hash = None
        app["logo_hash"] = logo_hash

    full_catalog = {
        "apps": result_dict_with_manifest_v2,
        "categories": categories_list(),
        "antifeatures": antifeatures_list(),
    }

    target_file = target_dir / "apps.json"
    target_file.parent.mkdir(parents=True, exist_ok=True)
    target_file.open("w", encoding="utf-8").write(json.dumps(full_catalog, sort_keys=True))


def write_catalog_doc(base_catalog, target_dir: Path) -> None:
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
        for k, v in base_catalog.items()
        if v["state"] == "working"
    }
    full_catalog = {
        "apps": result_dict_doc,
        "categories": categories_list()
    }

    target_file = target_dir / "apps.json"
    target_file.parent.mkdir(parents=True, exist_ok=True)
    target_file.open("w", encoding="utf-8").write(json.dumps(full_catalog, sort_keys=True))


def build_app_dict(app, infos):
    # Make sure we have some cache
    this_app_cache = app_cache_folder(app)
    assert this_app_cache.exists(), f"No cache yet for {app}"

    repo = Repo(this_app_cache)

    commits_in_apps_json = Repo(REPO_APPS_ROOT).git.log(
            "-S", f"\"{app}\"", "--first-parent", "--reverse", "--date=unix",
            "--format=%cd", "--", "apps.json").split("\n")
    if len(commits_in_apps_json) > 1:
        first_commit = commits_in_apps_json[0]
    else:
        commits_in_apps_toml = Repo(REPO_APPS_ROOT).git.log(
                "-S", f"[{app}]", "--first-parent", "--reverse", "--date=unix",
                "--format=%cd", "--", "apps.json", "apps.toml").split("\n")
        first_commit = commits_in_apps_toml[0]

    # Assume the first entry we get (= the oldest) is the time the app was added
    infos["added_in_catalog"] = int(first_commit)
    # int(commit_timestamps_for_this_app_in_catalog.split("\n")[0])

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
        relevant_commits = repo.iter_commits(paths=relevant_files, full_history=True, all=True)
        infos["revision"] = next(relevant_commits).hexsha

    # Otherwise, validate commit exists
    else:
        try:
            _ = repo.commit(infos["revision"])
        except ValueError as err:
            raise RuntimeError(f"Revision ain't in history ? {infos['revision']}") from err

    # Find timestamp corresponding to that commit
    timestamp = repo.commit(infos["revision"]).committed_date

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
        "maintained": 'package-not-maintained' not in infos.get('antifeatures', []),
        "high_quality": infos.get("high_quality", False),
        "featured": infos.get("featured", False),
        "category": infos.get("category", None),
        "subtags": infos.get("subtags", []),
        "potential_alternative_to": infos.get("potential_alternative_to", []),
        "antifeatures": list(
            set(list(manifest.get("antifeatures", {}).keys()) + infos.get("antifeatures", []))
        ),
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("target_dir", type=Path, nargs="?",
                        default=REPO_APPS_ROOT / "builds" / "default",
                        help="The directory to write the catalogs to")
    parser.add_argument("-j", "--jobs", type=int, default=multiprocessing.cpu_count(), metavar="N",
                        help="Allow N threads to run in parallel")
    parser.add_argument("-c", "--update-cache", action=argparse.BooleanOptionalAction, default=True,
                        help="Update the apps cache")
    args = parser.parse_args()

    appslib.logging_sender.enable()

    if args.update_cache:
        print("Updating the cache of all the apps directories...")
        apps_cache_update_all(get_catalog(), parallel=args.jobs)

    print("Retrieving all apps' information to build the catalog...")
    catalog = build_base_catalog(args.jobs)

    print(f"Writing the catalogs to {args.target_dir}...")
    write_catalog_v2(catalog, args.target_dir / "v2")
    write_catalog_v3(catalog, args.target_dir / "v3")
    write_catalog_doc(catalog, args.target_dir / "doc_catalog")
    print("Done!")


if __name__ == "__main__":
    main()
