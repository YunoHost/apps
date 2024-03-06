#!/usr/bin/env python3

import tomlkit
from datetime import datetime
from git import Repo
from pathlib import Path
import logging
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    REPO_APPS_ROOT = Path()
else:
    from appslib.utils import REPO_APPS_ROOT


def date_added_to(match: str, file: Path) -> int | None:
    commits = Repo(REPO_APPS_ROOT).git.log(
        "-S", match, "--first-parent", "--reverse",
        "--date=unix", "--format=%cd", "--", str(file)).splitlines()

    if not commits:
        return None
    first_commit = commits[0]
    return int(first_commit)


def add_apparition_dates(file: Path, key: str) -> None:
    document = tomlkit.load(file.open("r", encoding="utf-8"))
    for app, info in document.items():
        if key in info.keys():
            continue
        date = date_added_to(f"[{app}]", file)
        assert date is not None
        info[key] = date
        info[key].comment(datetime.fromtimestamp(info[key]).strftime("%Y/%m/%d"))
        info[key].trivia.comment_ws = "  "
    tomlkit.dump(document, file.open("w"))


def main() -> None:
    logging.basicConfig(level=logging.DEBUG)

    add_apparition_dates(REPO_APPS_ROOT / "apps.toml", key="added_date")
    add_apparition_dates(REPO_APPS_ROOT / "wishlist.toml", key="added_date")
    add_apparition_dates(REPO_APPS_ROOT / "graveyard.toml", key="killed_date")


if __name__ == "__main__":
    main()
