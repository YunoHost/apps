#!/usr/bin/env python3

import argparse
import tomlkit
import multiprocessing
import datetime
import json
import sys
from functools import cache
import logging
from pathlib import Path
from typing import Optional

import toml
import tqdm
import github

# add apps/tools to sys.path
sys.path.insert(0, str(Path(__file__).parent.parent))

from appslib.utils import REPO_APPS_ROOT, get_catalog  # noqa: E402 pylint: disable=import-error,wrong-import-position
from app_caches import app_cache_folder  # noqa: E402 pylint: disable=import-error,wrong-import-position
from autoupdate_app_sources.rest_api import GithubAPI, GitlabAPI, GiteaForgejoAPI, RefType  # noqa: E402,E501 pylint: disable=import-error,wrong-import-position


@cache
def get_github() -> tuple[Optional[tuple[str, str]], Optional[github.Github], Optional[github.InputGitAuthor]]:
    try:
        github_login = (REPO_APPS_ROOT / ".github_login").open("r", encoding="utf-8").read().strip()
        github_token = (REPO_APPS_ROOT / ".github_token").open("r", encoding="utf-8").read().strip()
        github_email = (REPO_APPS_ROOT / ".github_email").open("r", encoding="utf-8").read().strip()

        auth = (github_login, github_token)
        github_api = github.Github(github_token)
        author = github.InputGitAuthor(github_login, github_email)
        return auth, github_api, author
    except Exception as e:
        logging.warning(f"Could not get github: {e}")
        return None, None, None



def upstream_last_update_ago(app: str) -> tuple[str, int | None]:
    manifest_toml = app_cache_folder(app) / "manifest.toml"
    manifest_json = app_cache_folder(app) / "manifest.json"

    if manifest_toml.exists():
        manifest = toml.load(manifest_toml.open("r", encoding="utf-8"))
        upstream = manifest.get("upstream", {}).get("code")

    elif manifest_json.exists():
        manifest = json.load(manifest_json.open("r", encoding="utf-8"))
        upstream = manifest.get("upstream", {}).get("code")
    else:
        raise RuntimeError(f"App {app} doesn't have a manifest!")

    if upstream is None:
        raise RuntimeError(f"App {app} doesn't have an upstream code link!")

    api = None
    if upstream.startswith("https://github.com/"):
        api = GithubAPI(upstream, auth=get_github()[0])

    if upstream.startswith("https://gitlab."):
        api = GitlabAPI(upstream)

    if upstream.startswith("https://codeberg.org") or upstream.startswith("https://framagit.org"):
        api = GiteaForgejoAPI(upstream)

    if not api:
        autoupdate = manifest.get("resources", {}).get("sources", {}).get("main", {}).get("autoupdate")
        if autoupdate:
            strat = autoupdate["strategy"]
            if "gitea" in strat or "forgejo" in strat:
                api = GiteaForgejoAPI(upstream)

    if api:
        last_commit = api.commits()[0]
        date = last_commit["commit"]["author"]["date"]
        date = datetime.datetime.fromisoformat(date)
        ago: datetime.timedelta = datetime.datetime.now() - date.replace(tzinfo=None)
        return app, ago.days

    raise RuntimeError(f"App {app} not handled (not github, gitlab or gitea with autoupdate). Upstream is {upstream}")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("apps", nargs="*", type=str,
                        help="If not passed, the script will run on the catalog. Github keys required.")
    parser.add_argument("-j", "--processes", type=int, default=multiprocessing.cpu_count())
    args = parser.parse_args()

    apps_dict = get_catalog()
    if args.apps:
        apps_dict = {app: info for app, info in apps_dict.items() if app in args.apps}

    deprecated: list[str] = []
    not_deprecated: list[str] = []
    # for app, info in apps_dict.items():
    with multiprocessing.Pool(processes=args.processes) as pool:
        tasks = pool.imap_unordered(upstream_last_update_ago, apps_dict.keys())

        for _ in tqdm.tqdm(range(len(apps_dict)), ascii=" ·#"):
            try:
                app, result = next(tasks)
            except Exception as e:
                print(e)
                continue

            if result is None:
                continue

            if result > 365:
                deprecated.append(app)
            else:
                not_deprecated.append(app)

    catalog = tomlkit.load(open("apps.toml"))
    for app, info in catalog.items():
        antifeatures = info.get("antifeatures", [])
        if app in deprecated:
            if "deprecated-software" not in antifeatures:
                antifeatures.append("deprecated-software")
        elif app in not_deprecated:
            if "deprecated-software" in antifeatures:
                antifeatures.remove("deprecated-software")
        else:
            continue
        # unique the keys
        if antifeatures:
            info["antifeatures"] = antifeatures
        else:
            if "antifeatures" in info.keys():
                info.pop("antifeatures")
    tomlkit.dump(catalog, open("apps.toml", "w"))


if __name__ == "__main__":
    main()
