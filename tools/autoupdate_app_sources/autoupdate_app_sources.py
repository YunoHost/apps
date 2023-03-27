import time
import hashlib
import re
import sys
import requests
import toml
import os
import glob

from github import Github, InputGitAuthor

STRATEGIES = ["latest_github_release", "latest_github_tag"]

GITHUB_LOGIN = open(os.path.dirname(__file__) + "/../../.github_login").read().strip()
GITHUB_TOKEN = open(os.path.dirname(__file__) + "/../../.github_token").read().strip()
GITHUB_EMAIL = open(os.path.dirname(__file__) + "/../../.github_email").read().strip()

github = Github(GITHUB_TOKEN)
author = InputGitAuthor(GITHUB_LOGIN, GITHUB_EMAIL)


def apps_to_run_auto_update_for():

    catalog = toml.load(open(os.path.dirname(__file__) + "/../../apps.toml"))

    apps_flagged_as_working_and_on_yunohost_apps_org = [app
                                                        for app, infos in catalog.items()
                                                        if infos["state"] == "working"
                                                        and "/github.com/yunohost-apps" in infos["url"].lower()]

    manifest_tomls = glob.glob(os.path.dirname(__file__) + "/../../.apps_cache/*/manifest.toml")

    apps_with_manifest_toml = [path.split("/")[-2] for path in manifest_tomls]

    relevant_apps = list(sorted(set(apps_flagged_as_working_and_on_yunohost_apps_org) & set(apps_with_manifest_toml)))

    out = []
    for app in relevant_apps:
        manifest = toml.load(os.path.dirname(__file__) + f"/../../.apps_cache/{app}/manifest.toml")
        sources = manifest.get("resources", {}).get("sources", {})
        if any("autoupdate" in source for source in sources.values()):
            out.append(app)
    return out


def filter_and_get_latest_tag(tags):
    filter_keywords = ["start", "rc", "beta", "alpha"]
    tags = [t for t in tags if not any(keyword in t for keyword in filter_keywords)]

    for t in tags:
        if not re.match(r"^v?[\d\.]*\d$", t):
            print(f"Ignoring tag {t}, doesn't look like a version number")
    tags = [t for t in tags if re.match(r"^v?[\d\.]*\d$", t)]

    tag_dict = {t: tag_to_int_tuple(t) for t in tags}
    tags = sorted(tags, key=tag_dict.get)
    return tags[-1]


def tag_to_int_tuple(tag):

    tag = tag.strip("v")
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


class AppAutoUpdater():

    def __init__(self, app_id):

        #if not os.path.exists(app_path + "/manifest.toml"):
        #    raise Exception("manifest.toml doesnt exists?")

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

        self.current_version = manifest["version"].split("~")[0]
        self.sources = manifest.get("resources", {}).get("sources")

        if not self.sources:
            raise Exception("There's no resources.sources in manifest.toml ?")

        self.upstream = manifest.get("upstream", {}).get("code")

    def run(self):

        todos = {}

        for source, infos in self.sources.items():

            if "autoupdate" not in infos:
                continue

            strategy = infos.get("autoupdate", {}).get("strategy")
            if strategy not in STRATEGIES:
                raise Exception(f"Unknown strategy to autoupdate {source}, expected one of {STRATEGIES}, got {strategy}")

            asset = infos.get("autoupdate", {}).get("asset", "tarball")

            print(f"Checking {source} ...")

            new_version, new_asset_urls = self.get_latest_version_and_asset(strategy, asset, infos)

            print(f"Current version in manifest: {self.current_version}")
            print(f"Newest version on upstream: {new_version}")

            if source == "main":
                if self.current_version == new_version:
                    print(f"Version is still {new_version}, no update required for {source}")
                    continue
                else:
                    print(f"Update needed for {source}")
                    todos[source] = {"new_asset_urls": new_asset_urls, "old_assets": infos, "new_version": new_version}
            else:
                if isinstance(new_asset_urls, str) and infos["url"] == new_asset_urls:
                    print(f"URL is still up to date for asset {source}")
                    continue
                elif isinstance(new_asset_urls, dict) and new_asset_urls == {k: infos[k]["url"] for k in new_asset_urls.keys()}:
                    print(f"URLs are still up to date for asset {source}")
                    continue
                else:
                    print(f"Update needed for {source}")
                    todos[source] = {"new_asset_urls": new_asset_urls, "old_assets": infos}

        if not todos:
            return

        if "main" in todos:
            new_version = todos["main"]["new_version"]
            message = f"Upgrade to v{new_version}"
            new_branch = f"ci-auto-update-{new_version}"
        else:
            message = "Upgrade sources"
            new_branch = "ci-auto-update-sources"

        try:
            # Get the commit base for the new branch, and create it
            commit_sha = self.repo.get_branch(self.base_branch).commit.sha
            self.repo.create_git_ref(ref=f"refs/heads/{new_branch}", sha=commit_sha)
        except:
            pass

        manifest_new = self.manifest_raw
        for source, infos in todos.items():
            manifest_new = self.replace_version_and_asset_in_manifest(manifest_new, infos.get("new_version"), infos["new_asset_urls"], infos["old_assets"], is_main=source == "main")

        self.repo.update_file("manifest.toml",
                              message=message,
                              content=manifest_new,
                              sha=self.manifest_raw_sha,
                              branch=new_branch,
                              author=author)

        # Wait a bit to preserve the API rate limit
        time.sleep(1.5)

        # Open the PR
        pr = self.repo.create_pull(title=message, body=message, head=new_branch, base=self.base_branch)

        print("Created PR " + self.repo.full_name + " updated with PR #" + str(pr.id))


    def get_latest_version_and_asset(self, strategy, asset, infos):

        if "github" in strategy:
            assert self.upstream and self.upstream.startswith("https://github.com/"), "When using strategy {strategy}, having a defined upstream code repo on github.com is required"
            self.upstream_repo = self.upstream.replace("https://github.com/", "").strip("/")
            assert len(self.upstream_repo.split("/")) == 2, "'{self.upstream}' doesn't seem to be a github repository ?"

        if strategy == "latest_github_release":
            releases = self.github(f"repos/{self.upstream_repo}/releases")
            tags = [release["tag_name"] for release in releases if not release["draft"] and not release["prerelease"]]
            latest_version = filter_and_get_latest_tag(tags)
            if asset == "tarball":
                latest_tarball = f"{self.upstream}/archive/refs/tags/{latest_version}.tar.gz"
                return latest_version.strip("v"), latest_tarball
            # FIXME
            else:
                latest_release = [release for release in releases if release["tag_name"] == latest_version][0]
                latest_assets = {a["name"]: a["browser_download_url"] for a in latest_release["assets"] if not a["name"].endswith(".md5")}
                if isinstance(asset, str):
                    matching_assets_urls = [url for name, url in latest_assets.items() if re.match(asset, name)]
                    if not matching_assets_urls:
                        raise Exception(f"No assets matching regex '{asset}' for release {latest_version} among {list(latest_assets.keys())}")
                    elif len(matching_assets_urls) > 1:
                        raise Exception(f"Too many assets matching regex '{asset}' for release {latest_version} : {matching_assets_urls}")
                    return latest_version.strip("v"), matching_assets_urls[0]
                elif isinstance(asset, dict):
                    matching_assets_dicts = {}
                    for asset_name, asset_regex in asset.items():
                        matching_assets_urls = [url for name, url in latest_assets.items() if re.match(asset_regex, name)]
                        if not matching_assets_urls:
                            raise Exception(f"No assets matching regex '{asset}' for release {latest_version} among {list(latest_assets.keys())}")
                        elif len(matching_assets_urls) > 1:
                            raise Exception(f"Too many assets matching regex '{asset}' for release {latest_version} : {matching_assets_urls}")
                        matching_assets_dicts[asset_name] = matching_assets_urls[0]
                    return latest_version.strip("v"), matching_assets_dicts

        elif strategy == "latest_github_tag":
            if asset != "tarball":
                raise Exception("For the latest_github_tag strategy, only asset = 'tarball' is supported")
            tags = self.github(f"repos/{self.upstream_repo}/tags")
            latest_version = filter_and_get_latest_tag([t["name"] for t in tags])
            latest_tarball = f"{self.upstream}/archive/refs/tags/{latest_version}.tar.gz"
            return latest_version.strip("v"), latest_tarball

    def github(self, uri):
        #print(f'https://api.github.com/{uri}')
        r = requests.get(f'https://api.github.com/{uri}', auth=(GITHUB_LOGIN, GITHUB_TOKEN))
        assert r.status_code == 200, r
        return r.json()

    def replace_version_and_asset_in_manifest(self, content, new_version, new_assets_urls, current_assets, is_main):

        if isinstance(new_assets_urls, str):
            sha256 = sha256_of_remote_file(new_assets_urls)
        elif isinstance(new_assets_urls, dict):
            sha256 = {url: sha256_of_remote_file(url) for url in new_assets_urls.values()}

        if is_main:
            def repl(m):
                return m.group(1) + new_version + m.group(3)
            content = re.sub(r"(\s*version\s*=\s*[\"\'])([\d\.]+)(\~ynh\d+[\"\'])", repl, content)
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
        x = int(size*j/count)
        file.write("%s[%s%s] %i/%i %s\r" % (prefix, "#"*x, "."*(size-x), j,  count, name))
        file.flush()
    show(0)
    for i, item in enumerate(it):
        yield item
        show(i+1, item)
    file.write("\n")
    file.flush()


if __name__ == "__main__":
    for app in progressbar(apps_to_run_auto_update_for(), "Checking: ", 40):
        AppAutoUpdater(app).run()
