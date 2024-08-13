#!/usr/bin/env python3

import argparse
import tomlkit
import json
from datetime import datetime
from git import Repo, Commit
from pathlib import Path
import logging
from typing import Callable
import appslib.get_apps_repo as get_apps_repo


def git_bisect(repo: Repo, is_newer: Callable[[Commit], bool]) -> Commit | None:
    # Start with whole repo
    first_commit = repo.git.rev_list("HEAD", reverse=True, max_parents=0)
    repo.git.bisect("reset")
    repo.git.bisect("start", "--no-checkout", "HEAD", first_commit)

    while True:
        try:
            status = "bad" if is_newer(repo.commit("BISECT_HEAD")) else "good"
        except Exception:
            status = "skip"
        result_string = repo.git.bisect(status)
        if "is the first bad commit" in result_string.splitlines()[0]:
            return repo.commit(result_string.splitlines()[0].split(" ", 1)[0])


def get_app_info(commit: Commit, filebase: str, name: str) -> dict | None:
    data = None
    try:
        filestream = commit.tree.join(f"{filebase}.toml")
        filedata = filestream.data_stream.read().decode("utf-8")
        dictdata = tomlkit.loads(filedata)
        data = dictdata[name]
    except KeyError:
        pass
    try:
        filestream = commit.tree.join(f"{filebase}.json")
        filedata = filestream.data_stream.read().decode("utf-8")
        dictdata = json.loads(filedata)
        data = dictdata[name]
    except KeyError:
        pass

    assert isinstance(data, dict) or data is None
    return data


def app_is_present(commit: Commit, name: str) -> bool:
    info = get_app_info(commit, "apps", name)
    # if info is None:
    #     info = get_app_info(commit, "graveyard", name)
    return info is not None


def app_is_deprecated(commit: Commit, name: str) -> bool:
    info = get_app_info(commit, "apps", name)
    if info is None:
        return False

    antifeatures = info.get("antifeatures", [])
    return "deprecated-software" in antifeatures


def date_added(repo: Repo, name: str) -> int | None:
    result = git_bisect(repo, lambda x: app_is_present(x, name))
    print(result)
    return None if result is None else result.committed_date


def date_deprecated(repo: Repo, name: str) -> int | None:
    result = git_bisect(repo, lambda x: app_is_deprecated(x, name))
    print(result)
    return None if result is None else result.committed_date


def add_deprecation_dates(repo: Repo, file: Path) -> None:
    key = "deprecated_date"
    document = tomlkit.load(file.open("r", encoding="utf-8"))
    for app, info in document.items():
        if key in info.keys():
            continue
        if "deprecated-software" not in info.get("antifeatures", []):
            continue
        date = date_deprecated(repo, app)
        if date is None:
            continue
        info[key] = date
        info[key].comment(datetime.fromtimestamp(info[key]).strftime("%Y/%m/%d"))
        info[key].trivia.comment_ws = "  "
    tomlkit.dump(document, file.open("w"))


def date_added_to(repo: Repo, match: str, file: Path) -> int | None:
    commits = repo.git.log(
        "-S",
        match,
        "--first-parent",
        "--reverse",
        "--date=unix",
        "--format=%cd",
        "--",
        str(file),
    ).splitlines()

    if not commits:
        return None
    first_commit = commits[0]
    return int(first_commit)


def add_apparition_dates(repo: Repo, file: Path, key: str) -> None:
    document = tomlkit.load(file.open("r", encoding="utf-8"))
    for app, info in document.items():
        if key in info.keys():
            continue
        date = date_added_to(repo, f"[{app}]", file)
        assert date is not None
        info[key] = date
        info[key].comment(datetime.fromtimestamp(info[key]).strftime("%Y/%m/%d"))
        info[key].trivia.comment_ws = "  "
    tomlkit.dump(document, file.open("w"))


def main() -> None:
    parser = argparse.ArgumentParser()
    get_apps_repo.add_args(parser, allow_temp=False)
    args = parser.parse_args()

    logging.basicConfig(level=logging.DEBUG)

    apps_repo_dir = get_apps_repo.from_args(args)
    apps_repo = Repo(apps_repo_dir)

    add_apparition_dates(apps_repo, apps_repo_dir / "apps.toml", key="added_date")
    add_apparition_dates(apps_repo, apps_repo_dir / "wishlist.toml", key="added_date")
    add_apparition_dates(apps_repo, apps_repo_dir / "graveyard.toml", key="killed_date")

    add_deprecation_dates(apps_repo, apps_repo_dir / "apps.toml")
    add_deprecation_dates(apps_repo, apps_repo_dir / "graveyard.toml")


if __name__ == "__main__":
    main()
