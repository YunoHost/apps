import re
import sys
import requests
import toml
import os

STRATEGIES = ["latest_github_release", "latest_github_tag"]

GITHUB_LOGIN = open(os.path.dirname(__file__) + "/../../.github_login").read().strip()
GITHUB_TOKEN = open(os.path.dirname(__file__) + "/../../.github_token").read().strip()


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


class AppAutoUpdater():

    def __init__(self, app_path):

        if not os.path.exists(app_path + "/manifest.toml"):
            raise Exception("manifest.toml doesnt exists?")

        manifest = toml.load(open(app_path + "/manifest.toml"))

        self.current_version = manifest["version"].split("~")[0]
        self.sources = manifest.get("resources", {}).get("sources")

        if not self.sources:
            raise Exception("There's no resources.sources in manifest.toml ?")

        self.upstream = manifest.get("upstream", {}).get("code")

    def run(self):

        for source, infos in self.sources.items():

            if "autoupdate" not in infos:
                continue

            strategy = infos.get("autoupdate", {}).get("strategy")
            if strategy not in STRATEGIES:
                raise Exception(f"Unknown strategy to autoupdate {source}, expected one of {STRATEGIES}, got {strategy}")

            asset = infos.get("autoupdate", {}).get("asset", "tarball")

            print(f"Checking {source} ...")

            version, assets = self.get_latest_version_and_asset(strategy, asset, infos)

            print(f"Current version in manifest: {self.current_version}")
            print(f"Newest version on upstream: {version}")
            print(assets)

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


if __name__ == "__main__":
    AppAutoUpdater(sys.argv[1]).run()
