import time
import json

from pathlib import Path
from collections import defaultdict

import wlc
import tomlkit

from base import Repository, login, token, weblate_token


def get_weblate_component(weblate, component_path):
    try:
        weblate.get_component(component_path)
    except wlc.WeblateException:
        return False
    else:
        return True


def extract_strings_to_translate_from_apps(apps, translations_repository):
    weblate = wlc.Weblate(key=weblate_token, url="https://translate.yunohost.org/api/")

    # put all languages used on core by default for each component
    core_languages_list = {x["language_code"] for x in weblate.get("components/yunohost/core/translations/")["results"]}

    for app, infos in apps.items():
        repository_uri = infos["git"]["url"].replace("https://github.com/", "")
        branch = infos["git"]["branch"]

        if "github.com" not in infos["git"]["url"]:
            continue

        if app not in ("gotosocial", "fluffychat", "cinny", "fittrackee", "funkwhale", "photoprism"):
            continue

        print()
        print(app)
        print("=" * len(app))
        print(f"{repository_uri} -> branch '{branch}'")

        with Repository(
            f"https://{login}:{token}@github.com/{repository_uri}", branch
        ) as repository:
            if not repository.file_exists("manifest.toml"):
                continue

            # base our work on the testing branch if it exists
            if repository.run_command_as_if(
                ["git", "rev-parse", "--verify", "origin/testing"]
            ):
                repository.run_command(
                    ["git", "checkout", "-b", "testing", "--track", "origin/testing"]
                )

            manifest = tomlkit.loads(repository.read_file("manifest.toml"))

            translations_path = Path(f"translations/apps/{app}/manifest/")

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
                        json.dumps(translated_strings, indent=4, sort_keys=True, ensure_ascii=False) + "\n",
                    )
            else:
                translations_repository.write_file(
                    translations_path / "en.json",
                    json.dumps(translations["en"], indent=4, sort_keys=True, ensure_ascii=False) + "\n",
                )

                # add strings that aren't already present but don't overwrite existing ones
                for language, translated_strings in translations.items():
                    if language == "en":
                        continue

                    # if the translation file doesn't exist yet, dump it
                    if not translations_repository.file_exists(translations_path / f"{language}.json"):
                        translations_repository.write_file(
                            translations_path / f"{language}.json",
                            json.dumps(translated_strings, indent=4, sort_keys=True, ensure_ascii=False) + "\n",
                        )

                    else:  # if it exists, only add keys that aren't already present
                        language_file = json.loads(translations_repository.read_file(translations_path / f"{language}.json"))

                        if "description" in translated_strings and "description" not in language_file:
                            language_file["description"] = translated_strings["description"]

                        for key, translated_string in translated_strings.items():
                            if key not in language_file:
                                language_file[key] = translated_string

                        translations_repository.write_file(
                            translations_path / f"{language}.json",
                            json.dumps(language_file, indent=4, sort_keys=True, ensure_ascii=False) + "\n",
                        )

            # if something has been modified
            if translations_repository.run_command("git status -s", capture_output=True).strip():
                translations_repository.run_command("git status -s")
                translations_repository.run_command("git diff")
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

            if newly_created_translation or not get_weblate_component(
                weblate, f"yunohost-apps/{app}"
            ):
                print("Creating component on weblate...")
                weblate.create_component(
                    "yunohost-apps",
                    name=app,
                    slug=app,
                    file_format="json",
                    filemask=f"translations/apps/{app}/manifest/*.json",
                    repo="https://github.com/yunohost/apps_translations",
                    new_base=f"translations/apps/{app}/manifest/en.json",
                    template=f"translations/apps/{app}/manifest/en.json",
                    push="git@github.com:yunohost/apps_translations.git",
                )
                print(f"Component created at https://translate.yunohost.org/projects/yunohost-apps/{app}/")

            component_existing_languages = {x["language_code"] for x in weblate.get(f"components/yunohost-apps/{app}/translations/")["results"]}
            for language_code in sorted(core_languages_list - component_existing_languages):
                print(f"Adding available language for translation: {language_code}")
                weblate.post(f"components/yunohost-apps/{app}/translations/", **{"language_code": language_code})

        time.sleep(2)


if __name__ == "__main__":
    apps = json.load(open("../../builds/default/v3/apps.json"))["apps"]

    with Repository(
        f"https://{login}:{token}@github.com/yunohost/apps_translations", "main"
    ) as repository:
        extract_strings_to_translate_from_apps(apps, repository)
