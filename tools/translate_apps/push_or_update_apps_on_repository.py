import os
import time
import json
import tempfile
import subprocess

from collections import defaultdict
from pathlib import Path
from typing import Union

import wlc
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


def get_weblate_component(weblate, component_path):
    try:
        weblate.get_component(component_path)
    except wlc.WeblateException:
        return False
    else:
        return True


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
            kwargs = {"args": f"cd {self.path} && {command}", "shell": True}

        elif isinstance(command, list):
            kwargs = {"args": command, "cwd": self.path}

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
    weblate = wlc.Weblate(key=weblate_token, url="https://translate.yunohost.org/api/")

    for app, infos in apps.items():
        repository_uri = infos["git"]["url"].replace("https://github.com/", "")
        branch = infos["git"]["branch"]

        if "github.com" not in infos["git"]["url"]:
            continue

        print(app)
        print(f"{repository_uri} -> branch '{branch}'")

        with Repository(
            f"https://{login}:{token}@github.com/{repository_uri}", branch
        ) as repository:
            if not repository.file_exists("manifest.toml"):
                continue

            manifest = tomlkit.loads(repository.read_file("manifest.toml"))

            translations_path = Path(f"translations/apps/{app}/")

            newly_created_translation = False
            if not translations_repository.file_exists(translations_path):
                (translations_repository.path / translations_path).mkdir(parents=True)
                newly_created_translation = True

            translations = defaultdict(dict)
            for language, strings_to_translate in manifest.get(
                "description", {}
            ).items():
                translations[language]["description"] = strings_to_translate

            for question in manifest.get("install", {}):
                for strings_to_translate in ["ask", "help"]:
                    for language, message in (
                        manifest["install"][question]
                        .get(strings_to_translate, {})
                        .items()
                    ):
                        translations[language][
                            f"install_{question}_{strings_to_translate}"
                        ] = message

            if newly_created_translation:
                for language, translated_strings in translations.items():
                    translations_repository.write_file(
                        translations_path / f"{language}.json",
                        json.dumps(translated_strings, indent=4, sort_keys=True),
                    )
            else:
                translations_repository.write_file(
                    translations_path / "en.json",
                    json.dumps(translations["en"], indent=4, sort_keys=True),
                )

            # if something has been modified
            if translations_repository.run_command("git status -s", capture_output=True).strip():
                translations_repository.run_command("git status -s")
                translations_repository.run_command(["git", "add", translations_path])
                translations_repository.run_command(
                    [
                        "git",
                        "commit",
                        "-m",
                        f"feat(apps/i18n): extract strings to translate for application {app}",
                    ]
                )
                translations_repository.run_command(["git", "push"])

            if newly_created_translation or not get_weblate_component(weblate, f"yunohost-apps/{app}"):
                print("Creating component on weblate...")
                weblate.create_component(
                    "yunohost-apps",
                    name=app,
                    slug=app,
            if newly_created_translation or not get_weblate_component(
                weblate, f"yunohost-apps/{app}"
            ):
                    filemask=f"translations/apps/{app}/*.json",
                    repo="https://github.com/yunohost/apps_translations",
                    new_base=f"translations/apps/{app}/en.json",
                    template=f"translations/apps/{app}/en.json",
                    push="git@github.com:yunohost/apps_translations.git",
                )
                print(f"Component created at https://translate.yunohost.org/projects/yunohost-apps/{app}/")

        time.sleep(2)


if __name__ == "__main__":
                print(
                    f"Component created at https://translate.yunohost.org/projects/yunohost-apps/{app}/"
                )

    with Repository(
        f"https://{login}:{token}@github.com/yunohost/apps_translations", "main"
    ) as repository:
        extract_strings_to_translate_from_apps(apps, repository)
