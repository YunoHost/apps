import os
import time
import json
import tempfile
import subprocess

from typing import Union
from pathlib import Path

import tomlkit

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
    ) -> Union[str, int]:
        if isinstance(command, str):
            kwargs = {"args": f"cd {self.path} && {command}", "shell": True, "env": my_env}

        elif isinstance(command, list):
            kwargs = {"args": command, "cwd": self.path, "env": my_env}

        if capture_output:
            return subprocess.check_output(**kwargs).decode()
        else:
            print(f"\033[1;31m>>\033[0m \033[0;34m{command}\033[0m")
            return subprocess.check_call(**kwargs)

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


def extract_strings_to_translate_from_apps(apps, translations_repository):
    for app, infos in apps.items():
        repository_uri = infos["git"]["url"].replace("https://github.com/", "")
        branch = infos["git"]["branch"]

        if "github.com" not in infos["git"]["url"]:
            continue

        if app not in (
            "gotosocial",
            "fluffychat",
            "cinny",
            "fittrackee",
            "funkwhale",
            "photoprism",
        ):
            continue

        print(app)
        print(f"{repository_uri} -> branch '{branch}'")

        translations_path = Path(f"translations/apps/{app}/")

        if not translations_repository.file_exists(translations_path):
            print(f"App {app} doesn't have translations on github.com/yunohost/apps_translations, skip")
            continue

        with Repository(
            f"https://{login}:{token}@github.com/{repository_uri}", branch
        ) as repository:
            if not repository.file_exists("manifest.toml"):
                continue

            manifest = tomlkit.loads(repository.read_file("manifest.toml"))

            for translation in (translations_repository.path / f"translations/apps/{app}/").glob("*.json"):
                language = translation.name[:-len(".json")]

                # english version is the base, never modify it
                if language == "en":
                    continue

                translation = json.load(open(translation))

                if translation.get("description", "").strip():
                    manifest["description"][language] = translation["description"]

                for question in manifest.get("install", {}):
                    for strings_to_translate in ["ask", "help"]:
                        translation_key = f"install_{question}_{strings_to_translate}"
                        if not translation.get(translation_key, "").strip():
                            continue

                        if strings_to_translate not in manifest["install"][question]:
                            continue

                        manifest["install"][question][strings_to_translate][language] = translation[translation_key]

            repository.write_file("manifest.toml", tomlkit.dumps(manifest))

            if not repository.run_command("git status -s", capture_output=True).strip():
                continue

            # create or update merge request
            repository.run_command("git diff")
            repository.run_command("git add manifest.toml")
            repository.run_command(["git", "commit", "-m", "feat(i18n): update translations for manifest.toml"])
            repository.run_command(["git", "push", "-f", "origin", "master:manifest_toml_i18n"])

            # if no PR exist, create one
            if not repository.run_command("hub pr list -h manifest_toml_i18n", capture_output=True):
                repository.run_command(["hub", "pull-request", "-m", "Update translations for manifest.toml", "-b", branch, "-h", "manifest_toml_i18n", "-p", "-m", f"This pull request is automatically generated by scripts from the [YunoHost/apps](https://github.com/YunoHost/apps) repository.\n\nThe translation is pull from weblate and is located here: https://translate.yunohost.org/projects/yunohost-apps/{app}/\n\nIf you wish to modify the translation (other than in english), please do that directly on weblate since this is now the source of authority for it.\n\nDon't hesitate to reach the YunoHost team on [matrix](https://matrix.to/#/#yunohost:matrix.org) if there is any problem :heart:"])

        time.sleep(2)


if __name__ == "__main__":
    apps = json.load(open("../../builds/default/v3/apps.json"))["apps"]

    with Repository(
        f"https://{login}:{token}@github.com/yunohost/apps_translations", "main"
    ) as repository:
        extract_strings_to_translate_from_apps(apps, repository)
            if not repository.run_command(
                "hub pr list -h manifest_toml_i18n", capture_output=True
            ):
                repository.run_command(
                    [
                        "hub",
                        "pull-request",
                        "-m",
                        "Update translations for manifest.toml",
                        "-b",
                        branch,
                        "-h",
                        "manifest_toml_i18n",
                        "-p",
                        "-m",
                        f"This pull request is automatically generated by scripts from the [YunoHost/apps](https://github.com/YunoHost/apps) repository.\n\nThe translation is pull from weblate and is located here: https://translate.yunohost.org/projects/yunohost-apps/{app}/\n\nIf you wish to modify the translation (other than in english), please do that directly on weblate since this is now the source of authority for it.\n\nDon't hesitate to reach the YunoHost team on [matrix](https://matrix.to/#/#yunohost:matrix.org) if there is any problem :heart:",
                    ]
                )
