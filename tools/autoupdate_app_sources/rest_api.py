from enum import Enum
from typing import  List
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
