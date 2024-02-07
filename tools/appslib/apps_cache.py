#!/usr/bin/env python3

import logging
from pathlib import Path

import utils
from git import Repo


def apps_cache_path() -> Path:
    path = apps_repo_root() / ".apps_cache"
    path.mkdir()
    return path


def app_cache_path(app: str) -> Path:
    path = apps_cache_path() / app
    path.mkdir()
    return path


# def refresh_all_caches(catalog: dict[str, dict[str, str]]):
#     for app, infos
#     pass


def app_cache_clone(app: str, infos: dict[str, str]) -> None:
    git_depths = {
        "notworking": 5,
        "inprogress": 20,
        "default": 40,
    }

    Repo.clone_from(
        infos["url"],
        to_path=app_cache_path(app),
        depth=git_depths.get(infos["state"], git_depths["default"]),
        single_branch=True, branch=infos.get("branch", "master"),
    )


def app_cache_update(app: str, infos: dict[str, str]) -> None:
    app_path = app_cache_path(app)
    age = utils.git_repo_age(app_path)
    if age is False:
        return app_cache_clone(app, infos)

    if age < 3600:
        logging.info(f"Skipping {app}, it's been updated recently.")
        return

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


def cache_all_apps(catalog: dict[str, dict[str, str]]) -> None:
