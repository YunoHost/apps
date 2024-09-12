#!/usr/bin/env python3

import argparse
import json
import os
import subprocess
import sys
import logging
import time
from typing import Optional, TypeVar, Iterable, Generator
from pathlib import Path

import requests
import tqdm
import toml

from git import Repo, Head, Actor

# add apps/tools to sys.path
sys.path.insert(0, str(Path(__file__).parent.parent))

from app_caches import AppDir
from appslib.utils import (  # noqa: E402 pylint: disable=import-error,wrong-import-position
    get_catalog,
)
import appslib.get_apps_repo as get_apps_repo

TOOLS_DIR = Path(__file__).resolve().parent.parent

my_env = os.environ.copy()
my_env["GIT_TERMINAL_PROMPT"] = "0"

LOGIN = (TOOLS_DIR / ".github_login").open("r", encoding="utf-8").read().strip()
TOKEN = (TOOLS_DIR / ".github_token").open("r", encoding="utf-8").read().strip()
github_api = "https://api.github.com"

PATCHES_PATH = Path(__file__).resolve().parent / "patches"


def apps(min_level=4):
    for app, infos in get_catalog().items():
        if infos.get("state") == "working" and infos.get("level", -1) > min_level:
            infos["id"] = app
            yield infos


class AppToPatch:
    def __init__(self, id: str, path: Path, info: dict) -> None:
        self.id = id
        self.path = path
        self.info = info
        self.patch: Optional[str] = None
        self._repo: Optional[Repo] = None

    @property
    def repo(self) -> Repo:
        if self._repo is None:
            self._repo = Repo(self.path)
        return self._repo

    def cache(self) -> None:
        appdir = AppDir(self.id, self.path)
        appdir.ensure(self.info["url"], self.info.get("branch", "master"), False, False)

    def reset(self) -> None:
        if self.get_diff():
            logging.warning("%s had local changes, they were stashed.", self.id)
            self.repo.git.stash("save")
        self.repo.git.checkout("testing")

    def apply(self, patch: str) -> None:
        current_branch = self.repo.active_branch
        self.repo.head.reset(f"{current_branch}", index=True, working_tree=True)
        subprocess.call([PATCHES_PATH / patch / "patch"], cwd=self.path)

    def get_diff(self) -> str:
        return " ".join(str(d) for d in self.repo.index.diff(None, create_patch=True))

    def diff(self) -> None:
        diff = self.get_diff()
        if not diff:
            return
        print(80 * "=")
        print(f"Changes in : {self.id}")
        print(80 * "=")
        print()
        print(diff)
        print("\n\n\n")

    def on_github(self) -> bool:
        return "github.com/yunohost-apps" in self.info["url"].lower()

    def fork_if_needed(self, session: requests.Session) -> None:
        repo_name = self.info["url"].split("/")[-1]
        r = session.get(github_api + f"/repos/{LOGIN}/{repo_name}")
        if r.status_code == 200:
            return

        fork_repo_name = self.info["url"].split("github.com/")[-1]
        r = session.post(github_api + f"/repos/{fork_repo_name}/forks")
        r.raise_for_status()
        time.sleep(2)  # to avoid rate limiting lol

    def commit(self, patch: str) -> None:
        pr_title = (PATCHES_PATH / patch / "pr_title.md").open().read().strip()
        title = f"[autopatch] {pr_title}"
        self.repo.git.add(all=True)
        self.repo.index.commit(title, author=Actor("Yunohost-Bot", None))

    def push(self, patch: str, session: requests.Session) -> None:
        if not self.get_diff():
            return

        if not self.on_github():
            return

        self.fork_if_needed(session)

        base_branch = self.repo.active_branch
        if patch in self.repo.heads:
            self.repo.delete_head(patch)
        head_branch = self.repo.create_head(patch)
        head_branch.checkout()

        self.commit(patch)

        if "fork" in self.repo.remotes:
            self.repo.delete_remote(self.repo.remote("fork"))
        reponame = self.info["url"].rsplit("/", 1)[-1]
        self.repo.create_remote(
            "fork", url=f"https://{LOGIN}:{TOKEN}@github.com/{LOGIN}/{reponame}"
        )

        self.repo.remote(name="fork").push(progress=None, force=True)

        self.create_pull_request(patch, head_branch, base_branch, session)

    def create_pull_request(
        self, patch: str, head: Head, base: Head, session: requests.Session
    ) -> None:
        pr_title = (PATCHES_PATH / patch / "pr_title.md").open().read().strip()
        pr_body = (PATCHES_PATH / patch / "pr_body.md").open().read().strip()
        PR = {
            "title": f"[autopatch] {pr_title}",
            "body": f"This is an automatic PR\n\n{pr_body}",
            "head": f"{LOGIN}:{head.name}",
            "base": base.name,
            "maintainer_can_modify": True,
        }

        fork_repo_name = self.info["url"].split("github.com/")[-1]
        repo_name = self.info["url"].split("/")[-1]
        r = session.post(github_api + f"/repos/{fork_repo_name}/pulls", json.dumps(PR))
        r.raise_for_status()
        print(json.loads(r.text)["html_url"])
        time.sleep(4)  # to avoid rate limiting lol


IterType = TypeVar("IterType")


def progressbar(elements: list[IterType]) -> Generator[IterType, None, None]:
    return tqdm.tqdm(elements, total=len(elements), ascii=" ·#")


def main() -> None:
    parser = argparse.ArgumentParser()
    get_apps_repo.add_args(parser)
    parser.add_argument(
        "the_patch", type=str, nargs="?", help="The name of the patch to apply"
    )
    parser.add_argument(
        "--cache", "-b", action="store_true", help="Init local git clone for all apps"
    )
    parser.add_argument(
        "--apply", "-a", action="store_true", help="Apply patch on all local clones"
    )
    parser.add_argument(
        "--diff", "-d", action="store_true", help="Inspect diff for all apps"
    )
    parser.add_argument(
        "--push",
        "-p",
        action="store_true",
        help="Push and create pull requests on all apps with non-empty diff",
    )
    args = parser.parse_args()

    get_apps_repo.from_args(args)
    cache_path = get_apps_repo.cache_path(args)
    cache_path.mkdir(exist_ok=True, parents=True)

    if not (args.cache or args.apply or args.diff or args.push):
        parser.error("We required --cache, --apply, --diff or --push.")

    apps_to_patch: list[AppToPatch] = [
        AppToPatch(info["id"], cache_path / info["id"], info) for info in apps()
    ]

    if args.cache:
        print("Caching apps...")
        for app in progressbar(apps_to_patch):
            app.cache()

    if args.apply:
        if not args.the_patch:
            parser.error("--apply requires the patch name to be passed")
        print(f"Applying patch '{args.the_patch}' to apps...")
        for app in progressbar(apps_to_patch):
            app.reset()
            app.apply(args.the_patch)

    if args.diff:
        print("Printing diff of apps...")
        for app in progressbar(apps_to_patch):
            app.diff()

    if args.push:
        if not args.the_patch:
            parser.error("--push requires the patch name to be passed")
        print("Pushing apps...")
        with requests.Session() as session:
            session.headers.update({"Authorization": f"token {TOKEN}"})
            for app in progressbar(apps_to_patch):
                app.push(args.the_patch, session)


if __name__ == "__main__":
    main()
