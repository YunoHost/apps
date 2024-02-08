#!/usr/bin/env python3

import sys
import subprocess
from typing import Any, TextIO, Generator
import time
from functools import cache
from pathlib import Path
from git import Repo

import toml

REPO_APPS_ROOT = Path(Repo(__file__, search_parent_directories=True).working_dir)


@cache
def apps_repo_root() -> Path:
    return Path(__file__).parent.parent.parent


def git(cmd: list[str], cwd: Path | None = None) -> str:
    full_cmd = ["git"]
    if cwd:
        full_cmd.extend(["-C", str(cwd)])
    full_cmd.extend(cmd)
    return subprocess.check_output(
        full_cmd,
        # env=my_env,
    ).strip().decode("utf-8")


def git_repo_age(path: Path) -> bool | int:
    for file in [path / ".git" / "FETCH_HEAD", path / ".git" / "HEAD"]:
        if file.exists():
            return int(time.time() - file.stat().st_mtime)
    return False


# Progress bar helper, stolen from https://stackoverflow.com/a/34482761
def progressbar(
        it: list[Any],
        prefix: str = "",
        size: int = 60,
        file: TextIO = sys.stdout) -> Generator[Any, None, None]:
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


@cache
def get_catalog(working_only: bool = False) -> dict[str, dict[str, Any]]:
    """Load the app catalog and filter out the non-working ones"""
    catalog = toml.load((REPO_APPS_ROOT / "apps.toml").open("r", encoding="utf-8"))
    if working_only:
        catalog = {
            app: infos for app, infos in catalog.items()
            if infos.get("state") != "notworking"
        }
    return catalog


@cache
def get_categories() -> dict[str, Any]:
    categories_path = REPO_APPS_ROOT / "categories.toml"
    return toml.load(categories_path)


@cache
def get_antifeatures() -> dict[str, Any]:
    antifeatures_path = REPO_APPS_ROOT / "antifeatures.toml"
    return toml.load(antifeatures_path)


@cache
def get_wishlist() -> dict[str, dict[str, str]]:
    wishlist_path = REPO_APPS_ROOT / "wishlist.toml"
    return toml.load(wishlist_path)


@cache
def get_graveyard() -> dict[str, dict[str, str]]:
    wishlist_path = REPO_APPS_ROOT / "graveyard.toml"
    return toml.load(wishlist_path)

