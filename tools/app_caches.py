#!/usr/bin/env python3

import argparse
import shutil
import logging
from multiprocessing import Pool
from pathlib import Path
from typing import Any

import tqdm

from appslib.utils import (
    REPO_APPS_ROOT,  # pylint: disable=import-error
    get_catalog,
    git_repo_age,
)
from git import Repo


APPS_CACHE_DIR = REPO_APPS_ROOT / ".apps_cache"


def app_cache_folder(app: str) -> Path:
    return APPS_CACHE_DIR / app


def app_cache_clone(app: str, infos: dict[str, str]) -> None:
    logging.info("Cloning %s...", app)
    git_depths = {
        "notworking": 5,
        "inprogress": 20,
        "default": 40,
    }
    if app_cache_folder(app).exists():
        shutil.rmtree(app_cache_folder(app))
    Repo.clone_from(
        infos["url"],
        to_path=app_cache_folder(app),
        depth=git_depths.get(infos["state"], git_depths["default"]),
        single_branch=True,
        branch=infos.get("branch", "master"),
    )


def app_cache_clone_or_update(app: str, infos: dict[str, str]) -> None:
    app_path = app_cache_folder(app)

    # Don't refresh if already refreshed during last hour
    age = git_repo_age(app_path)
    if age is False:
        app_cache_clone(app, infos)
        return

    # if age < 3600:
    #     logging.info(f"Skipping {app}, it's been updated recently.")
    #     return

    logging.info("Updating %s...", app)
    repo = Repo(app_path)
    repo.remote("origin").set_url(infos["url"])

    branch = infos.get("branch", "master")
    if repo.active_branch != branch:
        all_branches = [str(b) for b in repo.branches]
        if branch in all_branches:
            repo.git.checkout(branch, "--force")
        else:
            repo.git.remote("set-branches", "--add", "origin", branch)
            repo.remote("origin").fetch(f"{branch}:{branch}")

    repo.remote("origin").fetch(refspec=branch, force=True)
    repo.git.reset("--hard", f"origin/{branch}")


def __app_cache_clone_or_update_mapped(data):
    name, info = data
    try:
        app_cache_clone_or_update(name, info)
    except Exception as err:
        logging.error("Error while updating %s: %s", name, err)


def apps_cache_update_all(apps: dict[str, dict[str, Any]], parallel: int = 8) -> None:
    with Pool(processes=parallel) as pool:
        tasks = pool.imap_unordered(__app_cache_clone_or_update_mapped, apps.items())
        for _ in tqdm.tqdm(tasks, total=len(apps.keys()), ascii=" ·#"):
            pass


def apps_cache_cleanup(apps: dict[str, dict[str, Any]]) -> None:
    for element in APPS_CACHE_DIR.iterdir():
        if element.name not in apps.keys():
            logging.warning(f"Removing {element}...")
            if element.is_dir():
                shutil.rmtree(element)
            else:
                element.unlink()


def __run_for_catalog():
    parser = argparse.ArgumentParser()
    parser.add_argument("-v", "--verbose", action="store_true")
    parser.add_argument("-j", "--processes", type=int, default=8)
    parser.add_argument(
        "-c",
        "--cleanup",
        action="store_true",
        default=False,
        help="Remove unknown directories from the app cache",
    )
    args = parser.parse_args()
    if args.verbose:
        logging.getLogger().setLevel(logging.INFO)

    if args.cleanup:
        apps_cache_cleanup(get_catalog())
    apps_cache_update_all(get_catalog(), parallel=args.processes)


if __name__ == "__main__":
    __run_for_catalog()
