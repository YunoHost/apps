#!/usr/bin/env python3

import re
from enum import Enum
from typing import List

import requests


class RefType(Enum):
    tags = 1
    commits = 2


class GithubAPI:
    def __init__(self, upstream: str, auth: tuple[str, str] = None):
        self.upstream = upstream
        self.upstream_repo = upstream.replace("https://github.com/", "")\
            .strip("/")
        assert (
                len(self.upstream_repo.split("/")) == 2
            ), f"'{upstream}' doesn't seem to be a github repository ?"
        self.auth = auth

    def internal_api(self, uri: str):
        url = f"https://api.github.com/{uri}"
        r = requests.get(url, auth=self.auth)
        assert r.status_code == 200, r
        return r.json()

    def tags(self) -> List[str]:
        """Get a list of tags for project."""
        return self.internal_api(f"repos/{self.upstream_repo}/tags")

    def commits(self) -> List[str]:
        """Get a list of commits for project."""
        return self.internal_api(f"repos/{self.upstream_repo}/commits")

    def releases(self) -> List[str]:
        """Get a list of releases for project."""
        return self.internal_api(f"repos/{self.upstream_repo}/releases")

    def url_for_ref(self, ref: str, ref_type: RefType) -> str:
        """Get a URL for a ref."""
        if ref_type == RefType.tags:
            return f"{self.upstream}/archive/refs/tags/{ref}.tar.gz"
        elif ref_type == RefType.commits:
            return f"{self.upstream}/archive/{ref}.tar.gz"
        else:
            raise NotImplementedError


class GitlabAPI:
    def __init__(self, upstream: str):
        split = re.search("(?P<host>https?://.+)/(?P<group>[^/]+)/(?P<project>[^/]+)/?$", upstream)
        self.upstream = split.group("host")
        self.upstream_repo = f"{split.group('group')}/{split.group('project')}"
        self.project_id = self.find_project_id(self.upstream_repo)

    def find_project_id(self, project: str) -> int:
        project = self.internal_api(f"projects/{project.replace('/', '%2F')}")
        return project["id"]

    def internal_api(self, uri: str):
        url = f"{self.upstream}/api/v4/{uri}"
        r = requests.get(url)
        assert r.status_code == 200, r
        return r.json()

    def tags(self) -> List[str]:
        """Get a list of tags for project."""
        return self.internal_api(f"projects/{self.project_id}/repository/tags")

    def commits(self) -> List[str]:
        """Get a list of commits for project."""
        return [
            {
                "sha": commit["id"],
                "commit": {
                    "author": {
                        "date": commit["committed_date"]
                        }
                    }
            }
            for commit in self.internal_api(f"projects/{self.project_id}/repository/commits")
            ]

    def releases(self) -> List[str]:
        """Get a list of releases for project."""
        releases = self.internal_api(f"projects/{self.project_id}/releases")
        retval = []
        for release in releases:
            r = {
                "tag_name": release["tag_name"],
                "prerelease": False,
                "draft": False,
                "html_url": release["_links"]["self"],
                "assets": [{
                    "name": asset["name"],
                    "browser_download_url": asset["direct_asset_url"]
                    } for asset in release["assets"]["links"]],
                }
            for source in release["assets"]["sources"]:
                r["assets"].append({
                    "name": f"source.{source['format']}",
                    "browser_download_url": source['url']
                })
            retval.append(r)

        return retval

    def url_for_ref(self, ref: str, ref_type: RefType) -> str:
        return f"{self.upstream}/api/v4/projects/{self.project_id}/repository/archive.tar.gz/?sha={ref}"


class GiteaForgejoAPI:
    def __init__(self, upstream: str):
        split = re.search("(?P<host>https?://.+)/(?P<group>[^/]+)/(?P<project>[^/]+)/?$", upstream)
        self.upstream = split.group("host")
        self.upstream_repo = f"{split.group('group')}/{split.group('project')}"
        self.project_id = self.find_project_id(self.upstream_repo)

    def internal_api(self, uri: str):
        url = f"{self.upstream}/api/v1/{uri}"
        r = requests.get(url)
        assert r.status_code == 200, r
        return r.json()

    def tags(self) -> List[str]:
        """Get a list of tags for project."""
        return self.internal_api(f"repos/{self.upstream_repo}/tags")

    def commits(self) -> List[str]:
        """Get a list of commits for project."""
        return self.internal_api(f"repos/{self.upstream_repo}/commits")

    def releases(self) -> List[str]:
        """Get a list of releases for project."""
        return self.internal_api(f"repos/{self.upstream_repo}/releases")

    def url_for_ref(self, ref: str, ref_type: RefType) -> str:
        """Get a URL for a ref."""
        return f"{self.upstream}/{self.upstream_repo}/archive/{ref}.tar.gz"
