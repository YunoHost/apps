import os
import tempfile
import subprocess

from typing import Union
from pathlib import Path

github_webhook_secret = open("github_webhook_secret", "r").read().strip()

login = open("login").read().strip()
token = open("token").read().strip()

weblate_token = open("weblate_token").read().strip()

my_env = os.environ.copy()
my_env["GIT_TERMINAL_PROMPT"] = "0"
my_env["GIT_AUTHOR_NAME"] = "yunohost-bot"
my_env["GIT_AUTHOR_EMAIL"] = "yunohost@yunohost.org"
my_env["GIT_COMMITTER_NAME"] = "yunohost-bot"
my_env["GIT_COMMITTER_EMAIL"] = "yunohost@yunohost.org"
my_env["GITHUB_USER"] = login
my_env["GITHUB_TOKEN"] = token

WORKING_BRANCH = "manifest_toml_i18n"


class Repository:
    def __init__(self, url, branch):
        self.url = url
        self.branch = branch

    def __enter__(self):
        self.temporary_directory = tempfile.TemporaryDirectory()
        self.path = Path(self.temporary_directory.name)
        self.run_command(
            [
                "git",
                "clone",
                self.url,
                "--single-branch",
                "--branch",
                self.branch,
                self.path,
            ]
        )

        return self

    def run_command(
        self, command: Union[str, list], capture_output=False
    ) -> Union[str, int, subprocess.CompletedProcess]:
        if isinstance(command, str):
            kwargs = {
                "args": f"cd {self.path} && {command}",
                "shell": True,
                "env": my_env,
            }

        elif isinstance(command, list):
            kwargs = {"args": command, "cwd": self.path, "env": my_env}

        if capture_output:
            return subprocess.check_output(**kwargs).decode()
        else:
            print(f"\033[1;31m>>\033[0m \033[0;34m{command}\033[0m")
            return subprocess.check_call(**kwargs)

    def run_command_as_if(self, command: Union[str, list]) -> bool:
        if isinstance(command, str):
            kwargs = {
                "args": f"cd {self.path} && {command}",
                "shell": True,
                "env": my_env,
            }

        elif isinstance(command, list):
            kwargs = {"args": command, "cwd": self.path, "env": my_env}

        print(f"\033[1;31m>>\033[0m \033[0;34m{command}\033[0m")
        return subprocess.run(**kwargs).returncode == 0

    def file_exists(self, file_name: str) -> bool:
        return (self.path / file_name).exists()

    def read_file(self, file_name: str) -> str:
        return open((self.path / file_name).resolve(), "r").read()

    def write_file(self, file_name: str, content: str) -> None:
        open((self.path / file_name).resolve(), "w").write(content)

    def remove_file(self, file_name: str) -> None:
        os.remove(self.path / file_name)

    def append_to_file(self, file_name: str, content: str) -> None:
        open((self.path / file_name).resolve(), "a").write(content)

    def __repr__(self):
        return f'<__main__.Repository "{self.url.split("@")[1]}" path="{self.path}">'

    def __exit__(self, *args, **kwargs):
        pass
