#!/usr/bin/env python3

import re
from enum import Enum
from typing import Any, Optional

import requests


class RefType(Enum):
    tags = 1
    commits = 2


class GithubAPI:
    def __init__(self, upstream: str, auth: Optional[tuple[str, str]] = None):
        self.upstream = upstream
        self.upstream_repo = upstream.replace("https://github.com/", "")\
            .strip("/")
        assert (
                len(self.upstream_repo.split("/")) == 2
            ), f"'{upstream}' doesn't seem to be a github repository ?"
        self.auth = auth

    def internal_api(self, uri: str) -> Any:
        url = f"https://api.github.com/{uri}"
        r = requests.get(url, auth=self.auth)
        r.raise_for_status()
        return r.json()

    def tags(self) -> list[dict[str, str]]:
        """Get a list of tags for project."""
        return self.internal_api(f"repos/{self.upstream_repo}/tags")

    def commits(self) -> list[dict[str, Any]]:
        """Get a list of commits for project."""
        return self.internal_api(f"repos/{self.upstream_repo}/commits")

    def releases(self) -> list[dict[str, Any]]:
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
        # Find gitlab api root...
        self.forge_root = self.get_forge_root(upstream).rstrip("/")
        self.project_path = upstream.replace(self.forge_root, "").lstrip("/")
        self.project_id = self.find_project_id(self.project_path)

    def get_forge_root(self, project_url: str) -> str:
        """A small heuristic based on the content of the html page..."""
        r = requests.get(project_url)
        r.raise_for_status()
        match = re.search(r"const url = `(.*)/api/graphql`", r.text)
        assert match is not None
        return match.group(1)

    def find_project_id(self, project: str) -> int:
        try:
            project = self.internal_api(f"projects/{project.replace('/', '%2F')}")
        except requests.exceptions.HTTPError as err:
            if err.response.status_code != 404:
                raise
            # Second chance for some buggy gitlab instances...
            name = self.project_path.split("/")[-1]
            projects = self.internal_api(f"projects?search={name}")
            project = next(filter(lambda x: x.get("path_with_namespace") == self.project_path, projects))

        assert isinstance(project, dict)
        project_id = project.get("id", None)
        return project_id

    def internal_api(self, uri: str) -> Any:
        url = f"{self.forge_root}/api/v4/{uri}"
        r = requests.get(url)
        r.raise_for_status()
        return r.json()

    def tags(self) -> list[dict[str, str]]:
        """Get a list of tags for project."""
        return self.internal_api(f"projects/{self.project_id}/repository/tags")

    def commits(self) -> list[dict[str, Any]]:
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

    def releases(self) -> list[dict[str, Any]]:
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
        name = self.project_path.split("/")[-1]
        clean_ref = ref.replace("/", "-")
        return f"{self.forge_root}/{self.project_path}/-/archive/{ref}/{name}-{clean_ref}.tar.bz2"


class GiteaForgejoAPI:
    def __init__(self, upstream: str):
        # Find gitea/forgejo api root...
        self.forge_root = self.get_forge_root(upstream).rstrip("/")
        self.project_path = upstream.replace(self.forge_root, "").lstrip("/")

    def get_forge_root(self, project_url: str) -> str:
        """A small heuristic based on the content of the html page..."""
        r = requests.get(project_url)
        r.raise_for_status()
        match = re.search(r"appUrl: '([^']*)',", r.text)
        assert match is not None
        return match.group(1).replace("\\", "")

    def internal_api(self, uri: str):
        url = f"{self.forge_root}/api/v1/{uri}"
        r = requests.get(url)
        r.raise_for_status()
        return r.json()

    def tags(self) -> list[dict[str, Any]]:
        """Get a list of tags for project."""
        return self.internal_api(f"repos/{self.project_path}/tags")

    def commits(self) -> list[dict[str, Any]]:
        """Get a list of commits for project."""
        return self.internal_api(f"repos/{self.project_path}/commits")

    def releases(self) -> list[dict[str, Any]]:
        """Get a list of releases for project."""
        return self.internal_api(f"repos/{self.project_path}/releases")

    def url_for_ref(self, ref: str, ref_type: RefType) -> str:
        """Get a URL for a ref."""
        return f"{self.forge_root}/{self.project_path}/archive/{ref}.tar.gz"
