#!/usr/bin/env python3

import argparse
import hashlib
import logging
from typing import Any
import re
import sys
import textwrap
from pathlib import Path
from functools import cache
from datetime import datetime

import requests
import toml
import tqdm
from tqdm.contrib.logging import logging_redirect_tqdm
import github

# add apps/tools to sys.path
sys.path.insert(0, str(Path(__file__).parent.parent))

from rest_api import GithubAPI, GitlabAPI, GiteaForgejoAPI, RefType  # noqa: E402,E501 pylint: disable=import-error,wrong-import-position
from appslib.utils import REPO_APPS_ROOT, get_catalog  # noqa: E402 pylint: disable=import-error,wrong-import-position
from app_caches import app_cache_folder  # noqa: E402 pylint: disable=import-error,wrong-import-position


STRATEGIES = [
    "latest_github_release",
    "latest_github_tag",
    "latest_github_commit",
    "latest_gitlab_release",
    "latest_gitlab_tag",
    "latest_gitlab_commit",
    "latest_gitea_release",
    "latest_gitea_tag",
    "latest_gitea_commit",
    "latest_forgejo_release",
    "latest_forgejo_tag",
    "latest_forgejo_commit",
]


@cache
def get_github() -> tuple[tuple[str, str] | None, github.Github | None, github.InputGitAuthor | None]:
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


def apps_to_run_auto_update_for():
    apps_flagged_as_working_and_on_yunohost_apps_org = [
        app
        for app, infos in get_catalog().items()
        if infos["state"] == "working"
        and "/github.com/yunohost-apps" in infos["url"].lower()
    ]

    relevant_apps = []
    for app in apps_flagged_as_working_and_on_yunohost_apps_org:
        manifest_toml = app_cache_folder(app) / "manifest.toml"
        if manifest_toml.exists():
            manifest = toml.load(manifest_toml.open("r", encoding="utf-8"))
            sources = manifest.get("resources", {}).get("sources", {})
            if any("autoupdate" in source for source in sources.values()):
                relevant_apps.append(app)
    return relevant_apps


def filter_and_get_latest_tag(tags: list[str], app_id: str) -> tuple[str, str]:
    def version_numbers(tag: str) -> list[int] | None:
        filter_keywords = ["start", "rc", "beta", "alpha"]
        if any(keyword in tag for keyword in filter_keywords):
            logging.debug(f"Tag {tag} contains filtered keyword from {filter_keywords}.")
            return None

        t_to_check = tag
        if tag.startswith(app_id + "-"):
            t_to_check = tag.split("-", 1)[-1]
        # Boring special case for dokuwiki...
        elif tag.startswith("release-"):
            t_to_check = tag.split("-", 1)[-1].replace("-", ".")

        if re.match(r"^v?[\d\.]*\-?\d$", t_to_check):
            return list(tag_to_int_tuple(t_to_check))
        print(f"Ignoring tag {t_to_check}, doesn't look like a version number")
        return None

    # sorted will sort by keys
    tags_dict: dict[list[int] | None, str] = dict(sorted({
        version_numbers(tag): tag for tag in tags
    }.items()))
    tags_dict.pop(None, None)
    if not tags_dict:
        raise RuntimeError("No tags were found after sanity filtering!")
    the_tag_list, the_tag = next(iter(tags_dict.items()))
    assert the_tag_list is not None
    return the_tag, ".".join(str(i) for i in the_tag_list)


def tag_to_int_tuple(tag) -> tuple[int, ...]:
    tag = tag.strip("v").replace("-", ".").strip(".")
    int_tuple = tag.split(".")
    assert all(i.isdigit() for i in int_tuple), f"Cant convert {tag} to int tuple :/"
    return tuple(int(i) for i in int_tuple)


def sha256_of_remote_file(url: str) -> str:
    print(f"Computing sha256sum for {url} ...")
    try:
        r = requests.get(url, stream=True)
        m = hashlib.sha256()
        for data in r.iter_content(8192):
            m.update(data)
        return m.hexdigest()
    except Exception as e:
        raise RuntimeError(f"Failed to compute sha256 for {url} : {e}") from e


class LocalOrRemoteRepo:
    def __init__(self, app: str | Path) -> None:
        self.local = False
        self.remote = False

        self.app = app
        if isinstance(app, Path):
            # It's local
            self.local = True
            self.manifest_path = app / "manifest.toml"

            if not self.manifest_path.exists():
                raise RuntimeError(f"{app.name}: manifest.toml doesnt exists?")
            # app is in fact a path
            self.manifest_raw = (app / "manifest.toml").open("r", encoding="utf-8").read()

        elif isinstance(app, str):
            # It's remote
            self.remote = True
            github = get_github()[1]
            assert github, "Could not get github authentication!"
            self.repo = github.get_repo(f"Yunohost-Apps/{app}_ynh")
            self.pr_branch = None
            # Determine base branch, either `testing` or default branch
            try:
                self.base_branch = self.repo.get_branch("testing").name
            except Exception:
                self.base_branch = self.repo.default_branch
            contents = self.repo.get_contents("manifest.toml", ref=self.base_branch)
            assert not isinstance(contents, list)
            self.manifest_raw = contents.decoded_content.decode()
            self.manifest_raw_sha = contents.sha

        else:
            raise TypeError(f"Invalid argument type for app: {type(app)}")

    def edit_manifest(self, content: str):
        self.manifest_raw = content
        if self.local:
            self.manifest_path.open("w", encoding="utf-8").write(content)

    def commit(self, message: str):
        if self.remote:
            author = get_github()[2]
            assert author, "Could not get Github author!"
            assert self.pr_branch is not None, "Did you forget to create a branch?"
            self.repo.update_file(
                "manifest.toml",
                message=message,
                content=self.manifest_raw,
                sha=self.manifest_raw_sha,
                branch=self.pr_branch,
                author=author,
            )

    def new_branch(self, name: str):
        if self.local:
            logging.warning("Can't create branches for local repositories")
            return
        if self.remote:
            self.pr_branch = name
            commit_sha = self.repo.get_branch(self.base_branch).commit.sha
            self.repo.create_git_ref(ref=f"refs/heads/{name}", sha=commit_sha)

    def create_pr(self, branch: str, title: str, message: str):
        if self.local:
            logging.warning("Can't create pull requests for local repositories")
            return
        if self.remote:
            # Open the PR
            pr = self.repo.create_pull(
                title=title, body=message, head=branch, base=self.base_branch
            )
            print("Created PR " + self.repo.full_name + " updated with PR #" + str(pr.id))


class AppAutoUpdater:
    def __init__(self, app_id: str | Path) -> None:
        self.repo = LocalOrRemoteRepo(app_id)
        self.manifest = toml.loads(self.repo.manifest_raw)

        self.app_id = self.manifest["id"]
        self.current_version = self.manifest["version"].split("~")[0]
        self.sources = self.manifest.get("resources", {}).get("sources")
        self.main_upstream = self.manifest.get("upstream", {}).get("code")

        if not self.sources:
            raise RuntimeError("There's no resources.sources in manifest.toml ?")

        self.main_upstream = self.manifest.get("upstream", {}).get("code")

    def run(self, edit: bool = False, commit: bool = False, pr: bool = False) -> bool:
        has_updates = False

        # Default message
        pr_title = commit_msg = "Upgrade sources"
        branch_name = "ci-auto-update-sources"

        for source, infos in self.sources.items():
            update = self.get_source_update(source, infos)
            print(update)
            if update is None:
                continue
            has_updates = True
            version, assets, msg = update

            if source == "main":
                branch_name = f"ci-auto-update-{version}"
                pr_title = commit_msg = f"Upgrade to v{version}"
                if msg:
                    commit_msg += f"\n{msg}"

            self.repo.manifest_raw = self.replace_version_and_asset_in_manifest(
                self.repo.manifest_raw, version, assets, infos, is_main=source == "main",
            )

        if edit:
            self.repo.edit_manifest(self.repo.manifest_raw)
        if pr:
            self.repo.new_branch(branch_name)
        if commit:
            self.repo.commit(commit_msg)
        if pr:
            self.repo.create_pr(branch_name, pr_title, commit_msg)

        return has_updates

    def get_source_update(self, name: str, infos: dict[str, Any]) -> tuple[str, str | dict[str, str], str] | None:
        if "autoupdate" not in infos:
            return None

        print(f"\n  Checking {name} ...")
        asset = infos.get("autoupdate", {}).get("asset", "tarball")
        strategy = infos.get("autoupdate", {}).get("strategy")
        if strategy not in STRATEGIES:
            raise ValueError(f"Unknown update strategy '{strategy}' for '{name}', expected one of {STRATEGIES}")

        result = self.get_latest_version_and_asset(strategy, asset, infos)
        if result is None:
            return None
        new_version, assets, more_info = result

        if name == "main":
            print(f"Current version in manifest: {self.current_version}")
            print(f"Newest  version on upstream: {new_version}")

            # Maybe new version is older than current version
            # Which can happen for example if we manually release a RC,
            # which is ignored by this script
            # Though we wrap this in a try/except pass, because don't want to miserably crash
            # if the tag can't properly be converted to int tuple ...
            if self.current_version == new_version:
                print("Up to date")
                return None
            try:
                if tag_to_int_tuple(self.current_version) > tag_to_int_tuple(new_version):
                    print("Up to date (current version appears more recent than newest version found)")
                    return None
            except (AssertionError, ValueError):
                pass

        if isinstance(assets, dict) and isinstance(infos.get("url"), str) or \
           isinstance(assets, str) and not isinstance(infos.get("url"), str):
            raise RuntimeError(
                "It looks like there's an inconsistency between the old asset list and the new ones... "
                "One is arch-specific, the other is not... Did you forget to define arch-specific regexes? "
                f"New asset url is/are : {assets}"
            )

        if isinstance(assets, str) and infos["url"] == assets:
            print(f"URL for asset {name} is up to date")
            return
        if isinstance(assets, dict) and assets == {k: infos[k]["url"] for k in assets.keys()}:
            print(f"URLs for asset {name} are up to date")
            return
        print(f"Update needed for {name}")
        return new_version, assets, more_info

    @staticmethod
    def find_matching_asset(assets: dict[str, str], regex: str) -> tuple[str, str]:
        matching_assets = {
            name: url for name, url in assets.items() if re.match(regex, name)
        }
        if not matching_assets:
            raise RuntimeError(f"No assets matching regex '{regex}'")
        if len(matching_assets) > 1:
            raise RuntimeError(f"Too many assets matching regex '{regex}': {matching_assets}")
        return next(iter(matching_assets.items()))

    def get_latest_version_and_asset(self, strategy: str, asset: str | dict, infos
                                     ) -> tuple[str, str | dict[str, str], str] | None:
        upstream = (infos.get("autoupdate", {}).get("upstream", self.main_upstream).strip("/"))
        _, remote_type, revision_type = strategy.split("_")

        if remote_type == "github":
            assert (
                upstream and upstream.startswith("https://github.com/")
            ), f"When using strategy {strategy}, having a defined upstream code repo on github.com is required"
            api = GithubAPI(upstream, auth=get_github()[0])
        if remote_type == "gitlab":
            api = GitlabAPI(upstream)
        if remote_type in ["gitea", "forgejo"]:
            api = GiteaForgejoAPI(upstream)

        if revision_type == "release":
            releases: dict[str, dict[str, Any]] = {
                release["tag_name"]: release
                for release in api.releases()
                if not release["draft"] and not release["prerelease"]
            }
            latest_version_orig, latest_version = filter_and_get_latest_tag(list(releases.keys()), self.app_id)
            latest_release = releases[latest_version_orig]
            latest_assets = {
                a["name"]: a["browser_download_url"]
                for a in latest_release["assets"]
                if not a["name"].endswith(".md5")
            }
            if remote_type in ["gitea", "forgejo"] and latest_assets == "":
                # if empty (so only the base asset), take the tarball_url
                latest_assets = latest_release["tarball_url"]
            # get the release changelog link
            latest_release_html_url = latest_release["html_url"]
            if asset == "tarball":
                latest_tarball = api.url_for_ref(latest_version_orig, RefType.tags)
                return latest_version, latest_tarball, latest_release_html_url
            # FIXME
            if isinstance(asset, str):
                try:
                    _, url = self.find_matching_asset(latest_assets, asset)
                    return latest_version, url, latest_release_html_url
                except RuntimeError as e:
                    raise RuntimeError(f"{e}.\nFull release details on {latest_release_html_url}.") from e

            if isinstance(asset, dict):
                new_assets = {}
                for asset_name, asset_regex in asset.items():
                    try:
                        _, url = self.find_matching_asset(latest_assets, asset_regex)
                        new_assets[asset_name] = url
                    except RuntimeError as e:
                        raise RuntimeError(f"{e}.\nFull release details on {latest_release_html_url}.") from e
                return latest_version, new_assets, latest_release_html_url

            return None

        if revision_type == "tag":
            if asset != "tarball":
                raise ValueError("For the latest tag strategies, only asset = 'tarball' is supported")
            tags = [t["name"] for t in api.tags()]
            latest_version_orig, latest_version = filter_and_get_latest_tag(tags, self.app_id)
            latest_tarball = api.url_for_ref(latest_version_orig, RefType.tags)
            return latest_version, latest_tarball, ""

        if revision_type == "commit":
            if asset != "tarball":
                raise ValueError("For the latest commit strategies, only asset = 'tarball' is supported")
            commits = api.commits()
            latest_commit = commits[0]
            latest_tarball = api.url_for_ref(latest_commit["sha"], RefType.commits)
            # Let's have the version as something like "2023.01.23"
            latest_commit_date = datetime.strptime(latest_commit["commit"]["author"]["date"][:10], "%Y-%m-%d")
            version_format = infos.get("autoupdate", {}).get("force_version", "%Y.%m.%d")
            latest_version = latest_commit_date.strftime(version_format)
            return latest_version, latest_tarball, ""

    def replace_version_and_asset_in_manifest(self, content: str, new_version: str, new_assets_urls: str | dict,
                                              current_assets: dict, is_main: bool):
        replacements = []
        if isinstance(new_assets_urls, str):
            replacements = [
                (current_assets["url"], new_assets_urls),
                (current_assets["sha256"], sha256_of_remote_file(new_assets_urls)),
            ]
        if isinstance(new_assets_urls, dict):
            replacements = [
                repl
                for key, url in new_assets_urls.items() for repl in (
                    (current_assets[key]["url"], url),
                    (current_assets[key]["sha256"], sha256_of_remote_file(url))
                )
            ]

        if is_main:
            def repl(m: re.Match) -> str:
                return m.group(1) + new_version + '~ynh1"'
            content = re.sub(r"(\s*version\s*=\s*[\"\'])([\d\.]+)(\~ynh\d+[\"\'])", repl, content)

        for old, new in replacements:
            content = content.replace(old, new)

        return content


def paste_on_haste(data):
    # NB: we hardcode this here and can't use the yunopaste command
    # because this script runs on the same machine than haste is hosted on...
    # and doesn't have the proper front-end LE cert in this context
    SERVER_URL = "http://paste.yunohost.org"
    TIMEOUT = 3
    try:
        url = SERVER_URL + "/documents"
        response = requests.post(url, data=data.encode("utf-8"), timeout=TIMEOUT)
        response.raise_for_status()
        dockey = response.json()["key"]
        return SERVER_URL + "/raw/" + dockey
    except requests.exceptions.RequestException as e:
        logging.error("\033[31mError: {}\033[0m".format(e))
        sys.exit(1)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("app_dir", nargs="?", type=Path)
    parser.add_argument("--edit", action=argparse.BooleanOptionalAction, help="Edit the local files", default=True)
    parser.add_argument("--commit", action=argparse.BooleanOptionalAction, help="Create a commit with the changes")
    parser.add_argument("--pr", action=argparse.BooleanOptionalAction, help="Create a pull request with the changes")
    parser.add_argument("--paste", action="store_true")
    args = parser.parse_args()

    if args.commit and not args.edit:
        parser.error("--commit requires --edit")
    if args.pr and not args.commit:
        parser.error("--pr requires --commit")

    if args.app_dir:
        AppAutoUpdater(args.app_dir).run(edit=args.edit, commit=args.commit, pr=args.pr)
    else:
        apps_failed = {}
        apps_updated = []

        with logging_redirect_tqdm():
            for app in tqdm.tqdm(apps_to_run_auto_update_for(), ascii=" ·#"):
                try:
                    if AppAutoUpdater(app).run(edit=args.edit, commit=args.commit, pr=args.pr):
                        apps_updated.append(app)
                except Exception:
                    import traceback

                    t = traceback.format_exc()
                    apps_failed[app] = t
                    logging.error(t)

        if apps_failed:
            error_log = "\n=========\n".join(
                [
                    f"{app}\n-------\n{trace}\n\n"
                    for app, trace in apps_failed.items()
                ]
            )
            if args.paste:
                paste_url = paste_on_haste(error_log)
                logging.error(textwrap.dedent(f"""
                Failed to run the source auto-update for: {', '.join(apps_failed.keys())}
                Please run manually the `autoupdate_app_sources.py` script on these apps to debug what is happening!
                See the debug log here: {paste_url}"
                """))
            else:
                print(error_log)

        if apps_updated:
            print(f"Apps updated: {', '.join(apps_updated)}")


if __name__ == "__main__":
    main()
