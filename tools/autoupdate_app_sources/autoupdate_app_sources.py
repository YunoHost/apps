#!/usr/bin/env python3

import glob
import hashlib
import os
import re
import sys
import time
from datetime import datetime

import requests
import toml
from rest_api import GithubAPI, GitlabAPI, GiteaForgejoAPI, RefType

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
    "latest_forgejo_commit"
    ]

if "--commit-and-create-PR" not in sys.argv:
    dry_run = True
else:
    dry_run = False

args = [arg for arg in sys.argv[1:] if arg != "--commit-and-create-PR"]

if len(args):
    auth = None
else:
    GITHUB_LOGIN = (
        open(os.path.dirname(__file__) + "/../../.github_login").read().strip()
    )
    GITHUB_TOKEN = (
        open(os.path.dirname(__file__) + "/../../.github_token").read().strip()
    )
    GITHUB_EMAIL = (
        open(os.path.dirname(__file__) + "/../../.github_email").read().strip()
    )

    from github import Github, InputGitAuthor

    auth = (GITHUB_LOGIN, GITHUB_TOKEN)
    github = Github(GITHUB_TOKEN)
    author = InputGitAuthor(GITHUB_LOGIN, GITHUB_EMAIL)


def apps_to_run_auto_update_for():
    catalog = toml.load(open(os.path.dirname(__file__) + "/../../apps.toml"))

    apps_flagged_as_working_and_on_yunohost_apps_org = [
        app
        for app, infos in catalog.items()
        if infos["state"] == "working"
        and "/github.com/yunohost-apps" in infos["url"].lower()
    ]

    manifest_tomls = glob.glob(
        os.path.dirname(__file__) + "/../../.apps_cache/*/manifest.toml"
    )

    apps_with_manifest_toml = [path.split("/")[-2] for path in manifest_tomls]

    relevant_apps = list(
        sorted(
            set(apps_flagged_as_working_and_on_yunohost_apps_org)
            & set(apps_with_manifest_toml)
        )
    )

    out = []
    for app in relevant_apps:
        manifest = toml.load(
            os.path.dirname(__file__) + f"/../../.apps_cache/{app}/manifest.toml"
        )
        sources = manifest.get("resources", {}).get("sources", {})
        if any("autoupdate" in source for source in sources.values()):
            out.append(app)
    return out


def filter_and_get_latest_tag(tags, app_id):
    filter_keywords = ["start", "rc", "beta", "alpha"]
    tags = [t for t in tags if not any(keyword in t for keyword in filter_keywords)]

    tag_dict = {}
    for t in tags:
        t_to_check = t
        if t.startswith(app_id + "-"):
            t_to_check = t.split("-", 1)[-1]
        # Boring special case for dokuwiki...
        elif t.startswith("release-"):
            t_to_check = t.split("-", 1)[-1].replace("-", ".")

        if not re.match(r"^v?[\d\.]*\-\d$", t_to_check):
            print(f"Ignoring tag {t_to_check}, doesn't look like a version number")
        else:
            tag_dict[t] = tag_to_int_tuple(t_to_check)

    tags = sorted(list(tag_dict.keys()), key=tag_dict.get)

    return tags[-1], ".".join([str(i) for i in tag_dict[tags[-1]]])


def tag_to_int_tuple(tag):
    tag = tag.strip("v").replace("-", ".").strip(".")
    int_tuple = tag.split(".")
    assert all(i.isdigit() for i in int_tuple), f"Cant convert {tag} to int tuple :/"
    return tuple(int(i) for i in int_tuple)


def sha256_of_remote_file(url):
    print(f"Computing sha256sum for {url} ...")
    try:
        r = requests.get(url, stream=True)
        m = hashlib.sha256()
        for data in r.iter_content(8192):
            m.update(data)
        return m.hexdigest()
    except Exception as e:
        print(f"Failed to compute sha256 for {url} : {e}")
        return None


class AppAutoUpdater:
    def __init__(self, app_id, app_id_is_local_app_dir=False):
        if app_id_is_local_app_dir:
            if not os.path.exists(app_id + "/manifest.toml"):
                raise Exception("manifest.toml doesnt exists?")
            # app_id is in fact a path
            manifest = toml.load(open(app_id + "/manifest.toml"))

        else:
            # We actually want to look at the manifest on the "testing" (or default) branch
            self.repo = github.get_repo(f"Yunohost-Apps/{app_id}_ynh")
            # Determine base branch, either `testing` or default branch
            try:
                self.base_branch = self.repo.get_branch("testing").name
            except:
                self.base_branch = self.repo.default_branch

            contents = self.repo.get_contents("manifest.toml", ref=self.base_branch)
            self.manifest_raw = contents.decoded_content.decode()
            self.manifest_raw_sha = contents.sha
            manifest = toml.loads(self.manifest_raw)

        self.app_id = manifest["id"]
        self.current_version = manifest["version"].split("~")[0]
        self.sources = manifest.get("resources", {}).get("sources")

        if not self.sources:
            raise Exception("There's no resources.sources in manifest.toml ?")

        self.main_upstream = manifest.get("upstream", {}).get("code")

    def run(self):
        todos = {}

        for source, infos in self.sources.items():
            if "autoupdate" not in infos:
                continue

            strategy = infos.get("autoupdate", {}).get("strategy")
            if strategy not in STRATEGIES:
                raise Exception(
                    f"Unknown strategy to autoupdate {source}, expected one of {STRATEGIES}, got {strategy}"
                )

            asset = infos.get("autoupdate", {}).get("asset", "tarball")

            print(f"\n  Checking {source} ...")

            if "_release" in strategy:
                (
                    new_version,
                    new_asset_urls,
                    changelog_url,
                ) = self.get_latest_version_and_asset(strategy, asset, infos, source)
            else:
                (new_version, new_asset_urls) = self.get_latest_version_and_asset(
                    strategy, asset, infos, source
                )

            if source == "main":
                print(f"Current version in manifest: {self.current_version}")
                print(f"Newest  version on upstream: {new_version}")

                # Maybe new version is older than current version
                # Which can happen for example if we manually release a RC,
                # which is ignored by this script
                # Though we wrap this in a try/except pass, because don't want to miserably crash
                # if the tag can't properly be converted to int tuple ...
                try:
                    if tag_to_int_tuple(self.current_version) > tag_to_int_tuple(
                        new_version
                    ):
                        print(
                            "Up to date (current version appears more recent than newest version found)"
                        )
                        continue
                except:
                    pass

                if self.current_version == new_version:
                    print("Up to date")
                    continue

            if (
                isinstance(new_asset_urls, dict) and isinstance(infos.get("url"), str)
            ) or (
                isinstance(new_asset_urls, str)
                and not isinstance(infos.get("url"), str)
            ):
                raise Exception(
                    f"It looks like there's an inconsistency between the old asset list and the new ones ... one is arch-specific, the other is not ... Did you forget to define arch-specific regexes ? ... New asset url is/are : {new_asset_urls}"
                )

            if isinstance(new_asset_urls, str) and infos["url"] == new_asset_urls:
                print(f"URL for asset {source} is up to date")
                continue
            elif isinstance(new_asset_urls, dict) and new_asset_urls == {
                k: infos[k]["url"] for k in new_asset_urls.keys()
            }:
                print(f"URLs for asset {source} are up to date")
                continue
            else:
                print(f"Update needed for {source}")
                todos[source] = {
                    "new_asset_urls": new_asset_urls,
                    "old_assets": infos,
                }

            if source == "main":
                todos[source]["new_version"] = new_version

        if dry_run or not todos:
            return bool(todos)

        if "main" in todos:
            if "_release" in strategy:
                title = f"Upgrade to v{new_version}"
                message = f"Upgrade to v{new_version}\nChangelog: {changelog_url}"
            else:
                title = message = f"Upgrade to v{new_version}"
            new_version = todos["main"]["new_version"]
            new_branch = f"ci-auto-update-{new_version}"
        else:
            title = message = "Upgrade sources"
            new_branch = "ci-auto-update-sources"

        try:
            # Get the commit base for the new branch, and create it
            commit_sha = self.repo.get_branch(self.base_branch).commit.sha
            self.repo.create_git_ref(ref=f"refs/heads/{new_branch}", sha=commit_sha)
        except:
            print("... Branch already exists, skipping")
            return False

        manifest_new = self.manifest_raw
        for source, infos in todos.items():
            manifest_new = self.replace_version_and_asset_in_manifest(
                manifest_new,
                infos.get("new_version"),
                infos["new_asset_urls"],
                infos["old_assets"],
                is_main=source == "main",
            )

        self.repo.update_file(
            "manifest.toml",
            message=message,
            content=manifest_new,
            sha=self.manifest_raw_sha,
            branch=new_branch,
            author=author,
        )

        # Wait a bit to preserve the API rate limit
        time.sleep(1.5)

        # Open the PR
        pr = self.repo.create_pull(
            title=title, body=message, head=new_branch, base=self.base_branch
        )

        print("Created PR " + self.repo.full_name + " updated with PR #" + str(pr.id))

        return bool(todos)

    def get_latest_version_and_asset(self, strategy, asset, infos, source):
        upstream = (
            infos.get("autoupdate", {}).get("upstream", self.main_upstream).strip("/")
        )

        if "github" in strategy:
            assert (
                upstream and upstream.startswith("https://github.com/")
            ), f"When using strategy {strategy}, having a defined upstream code repo on github.com is required"
            api = GithubAPI(upstream, auth=auth)
        elif "gitlab" in strategy:
            api = GitlabAPI(upstream)
        elif "gitea" in strategy or "forgejo" in strategy:
            api = GiteaForgejoAPI(upstream)

        if "_release" in strategy:
            releases = api.releases()
            tags = [
                release["tag_name"]
                for release in releases
                if not release["draft"] and not release["prerelease"]
            ]
            latest_version_orig, latest_version = filter_and_get_latest_tag(
                tags, self.app_id
            )
            latest_release = [
                release
                for release in releases
                if release["tag_name"] == latest_version_orig
            ][0]
            if "github" in strategy or "gitlab" in strategy:
                latest_assets = {
                    a["name"]: a["browser_download_url"]
                    for a in latest_release["assets"]
                    if not a["name"].endswith(".md5")
                }
            elif "gitea" in strategy or "forgejo" in strategy:
               latest_assets = {
                    a["name"]: a["browser_download_url"]
                    for a in latest_release["assets"]
                    if not a["name"].endswith(".md5")
                }
               if latest_assets == "":
                   # if empty (so only the base asset), take the tarball_url
                   latest_assets = latest_release["tarball_url"]
            if strategy == "_release":
                # gitlab's API is different for that
                latest_release_html_url = latest_release["_links"]["self"]
            else:
                latest_release_html_url = latest_release["html_url"]
            if asset == "tarball":
                latest_tarball = (
                    api.url_for_ref(latest_version_orig, RefType.tags)
                )
                return latest_version, latest_tarball, latest_release_html_url
            # FIXME
            else:
                if isinstance(asset, str):
                    matching_assets_urls = [
                        url
                        for name, url in latest_assets.items()
                        if re.match(asset, name)
                    ]
                    if not matching_assets_urls:
                        raise Exception(
                            f"No assets matching regex '{asset}' for release {latest_version} among {list(latest_assets.keys())}. Full release details on {latest_release_html_url}"
                        )
                    elif len(matching_assets_urls) > 1:
                        raise Exception(
                            f"Too many assets matching regex '{asset}' for release {latest_version} : {matching_assets_urls}. Full release details on {latest_release_html_url}"
                        )
                    return (
                        latest_version,
                        matching_assets_urls[0],
                        latest_release_html_url,
                    )
                elif isinstance(asset, dict):
                    matching_assets_dicts = {}
                    for asset_name, asset_regex in asset.items():
                        matching_assets_urls = [
                            url
                            for name, url in latest_assets.items()
                            if re.match(asset_regex, name)
                        ]
                        if not matching_assets_urls:
                            raise Exception(
                                f"No assets matching regex '{asset_regex}' for release {latest_version} among {list(latest_assets.keys())}. Full release details on {latest_release_html_url}"
                            )
                        elif len(matching_assets_urls) > 1:
                            raise Exception(
                                f"Too many assets matching regex '{asset}' for release {latest_version} : {matching_assets_urls}. Full release details on {latest_release_html_url}"
                            )
                        matching_assets_dicts[asset_name] = matching_assets_urls[0]
                    return (
                        latest_version.strip("v"),
                        matching_assets_dicts,
                        latest_release_html_url,
                    )

        elif "_tag" in strategy:
            if asset != "tarball":
                raise Exception(
                    "For the latest tag strategy, only asset = 'tarball' is supported"
                )
            tags = api.tags()
            latest_version_orig, latest_version = filter_and_get_latest_tag(
                [t["name"] for t in tags], self.app_id
            )
            latest_tarball = api.url_for_ref(latest_version_orig, RefType.tags)
            return latest_version, latest_tarball

        elif "_commit" in strategy:
            if asset != "tarball":
                raise Exception(
                    "For the latest release strategy, only asset = 'tarball' is supported"
                )
            commits = api.commits()
            latest_commit = commits[0]
            latest_tarball = api.url_for_ref(latest_commit["sha"], RefType.commits)
            # Let's have the version as something like "2023.01.23"
            latest_commit_date = datetime.strptime(
                latest_commit["commit"]["author"]["date"][:10], "%Y-%m-%d"
            )
            version_format = infos.get("autoupdate", {}).get(
                "force_version", "%Y.%m.%d"
            )
            latest_version = latest_commit_date.strftime(version_format)

            return latest_version, latest_tarball

    def replace_version_and_asset_in_manifest(
        self, content, new_version, new_assets_urls, current_assets, is_main
    ):
        if isinstance(new_assets_urls, str):
            sha256 = sha256_of_remote_file(new_assets_urls)
        elif isinstance(new_assets_urls, dict):
            sha256 = {
                url: sha256_of_remote_file(url) for url in new_assets_urls.values()
            }

        if is_main:

            def repl(m):
                return m.group(1) + new_version + '~ynh1"'

            content = re.sub(
                r"(\s*version\s*=\s*[\"\'])([\d\.]+)(\~ynh\d+[\"\'])", repl, content
            )
        if isinstance(new_assets_urls, str):
            content = content.replace(current_assets["url"], new_assets_urls)
            content = content.replace(current_assets["sha256"], sha256)
        elif isinstance(new_assets_urls, dict):
            for key, url in new_assets_urls.items():
                content = content.replace(current_assets[key]["url"], url)
                content = content.replace(current_assets[key]["sha256"], sha256[url])

        return content


# Progress bar helper, stolen from https://stackoverflow.com/a/34482761
def progressbar(it, prefix="", size=60, file=sys.stdout):
    it = list(it)
    count = len(it)

    def show(j, name=""):
        name += "          "
        x = int(size * j / count)
        file.write(
            "\n%s[%s%s] %i/%i %s\n"
            % (prefix, "#" * x, "." * (size - x), j, count, name)
        )
        file.flush()

    show(0)
    for i, item in enumerate(it):
        show(i + 1, item)
        yield item
    file.write("\n")
    file.flush()


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
        print("\033[31mError: {}\033[0m".format(e))
        sys.exit(1)


if __name__ == "__main__":
    args = [arg for arg in sys.argv[1:] if arg != "--commit-and-create-PR"]

    if len(args):
        AppAutoUpdater(args[0], app_id_is_local_app_dir=True).run()
    else:
        apps_failed = []
        apps_failed_details = {}
        apps_updated = []
        for app in progressbar(apps_to_run_auto_update_for(), "Checking: ", 40):
            try:
                updated = AppAutoUpdater(app).run()
            except Exception as e:
                apps_failed.append(app)
                import traceback

                t = traceback.format_exc()
                apps_failed_details[app] = t
                print(t)
            else:
                if updated:
                    apps_updated.append(app)

        if apps_failed:
            print(f"Apps failed: {', '.join(apps_failed)}")
            if os.path.exists("/usr/bin/sendxmpppy"):
                paste = "\n=========\n".join(
                    [
                        app + "\n-------\n" + trace + "\n\n"
                        for app, trace in apps_failed_details.items()
                    ]
                )
                paste_url = paste_on_haste(paste)
                os.system(
                    f"/usr/bin/sendxmpppy 'Failed to run the source auto-update for : {', '.join(apps_failed)}. Please run manually the `autoupdate_app_sources.py` script on these apps to debug what is happening! Debug log : {paste_url}'"
                )
        if apps_updated:
            print(f"Apps updated: {', '.join(apps_updated)}")
