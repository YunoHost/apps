#!/usr/bin/env python3

import argparse
import shutil
import logging
from itertools import repeat
from multiprocessing import Pool
from pathlib import Path
from typing import Any

import tqdm

from git import Repo
from git.repo.fun import is_git_dir

from appslib.utils import (
    REPO_APPS_ROOT,  # pylint: disable=import-error
    get_catalog,
    git_repo_age,
)


class AppDir:
    def __init__(self, name: str, path: Path) -> None:
        self.name = name
        self.path = path

    def ensure(
        self, remote: str, branch: str, url_ssh: bool, all_branches: bool
    ) -> None:
        # Patch url for ssh clone
        if url_ssh:
            remote = remote.replace("https://github.com/", "git@github.com:")

        op = self._update if is_git_dir(self.path / ".git") else self._clone
        op(remote, all_branches, branch)

    def cleanup(self) -> None:
        logging.warning(f"Cleaning up {self.path}...")
        if self.path.exists():
            if self.path.is_dir():
                shutil.rmtree(self.path)
            else:
                self.path.unlink()

    def _clone(self, remote: str, all_branches: bool, branch: str) -> None:
        logging.info("Cloning %s...", self.name)

        if self.path.exists():
            self.cleanup()
        Repo.clone_from(
            remote,
            to_path=self.path,
            depth=40,
            single_branch=not all_branches,
            branch=branch,
        )

    def _update(self, remote: str, all_branches: bool, branch: str) -> None:
        logging.info("Updating %s...", self.name)
        repo = Repo(self.path)
        repo.remote("origin").set_url(remote)

        if all_branches:
            repo.git.remote("set-branches", "origin", "*")
            repo.remote("origin").fetch()
            repo.remote("origin").pull()
        else:
            if repo.active_branch != branch:
                repo_branches = [str(b) for b in repo.heads]
                if branch in repo_branches:
                    repo.git.checkout(branch, "--force")
                else:
                    repo.git.remote("set-branches", "--add", "origin", branch)
                    repo.remote("origin").fetch(f"{branch}:{branch}")

            repo.remote("origin").fetch(refspec=branch, force=True)
            repo.git.reset("--hard", f"origin/{branch}")


def __appdir_ensure_mapped(data):
    name, path, url, branch, url_ssh, all_branches = data
    try:
        AppDir(name, path).ensure(url, branch, url_ssh, all_branches)
    except Exception as err:
        logging.error("[App caches] Error while updating %s: %s", name, err)


def apps_cache_update_all(
    cache_path: Path,
    apps: dict[str, dict[str, Any]],
    parallel: int = 8,
    url_ssh: bool = False,
    all_branches: bool = False,
) -> None:
    args = (
        (
            app,
            cache_path / app,
            info["url"],
            info.get("branch", "master"),
            url_ssh,
            all_branches,
        )
        for app, info in apps.items()
    )
    with Pool(processes=parallel) as pool:
        tasks = pool.imap_unordered(__appdir_ensure_mapped, args)
        for _ in tqdm.tqdm(tasks, total=len(apps.keys()), ascii=" ·#"):
            pass


def apps_cache_cleanup(cache_path: Path, apps: dict[str, dict[str, Any]]) -> None:
    for element in cache_path.iterdir():
        if element.name not in apps.keys():
            AppDir("", element).cleanup()


def __run_for_catalog():
    parser = argparse.ArgumentParser()
    parser.add_argument("-v", "--verbose", action="store_true")
    parser.add_argument("-j", "--processes", type=int, default=8)
    parser.add_argument(
        "-s",
        "--ssh",
        action=argparse.BooleanOptionalAction,
        default=False,
        help="Use ssh clones instead of https",
    )
    parser.add_argument(
        "-b",
        "--all-branches",
        action=argparse.BooleanOptionalAction,
        default=False,
        help="Download all branches from repo",
    )
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

    cache_path = REPO_APPS_ROOT / ".apps_cache"
    cache_path.mkdir(exist_ok=True, parents=True)

    if args.cleanup:
        apps_cache_cleanup(cache_path, get_catalog())

    apps_cache_update_all(
        cache_path,
        get_catalog(),
        parallel=args.processes,
        url_ssh=args.ssh,
        all_branches=args.all_branches,
    )


if __name__ == "__main__":
    __run_for_catalog()
